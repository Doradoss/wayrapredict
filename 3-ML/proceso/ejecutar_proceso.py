# =====================================================================================================
# WayraPredict · Proceso de predicción (se ejecuta en Azure Container Instances desde la imagen Docker)
#
# 1. Ejecuta la cadena del modelo híbrido vigente (v3) con los datos de esta carpeta: dataset, entrenamiento
#    de los componentes, combinación Prophet + LSTM, serie completa, pronóstico de 1 a 3 días y archivos para la base.
# 2. Según la variable MODO:
#    - "verificar" (por defecto): compara los pronósticos generados con los que ya están en la base. NO escribe
#      nada; sirve para comprobar el proceso en la nube sin cambiar lo que muestra la plataforma.
#    - "cargar": carga los resultados en la base con 10-CARGAR_BD.py (una sola transacción, repetible).
#
# Variables de entorno: MODO, WAYRA_DB_HOST, WAYRA_DB_PORT, WAYRA_DB_NAME, WAYRA_DB_USER, WAYRA_DB_PASSWORD.
# Se ejecuta desde la carpeta 3-ML:  python proceso/ejecutar_proceso.py
# =====================================================================================================
import os
import subprocess
import sys
import time
from datetime import datetime

import pandas as pd
import psycopg2

MODO = os.environ.get("MODO", "verificar").strip().lower()
PLAT = os.path.join("modelo_hibrido", "version_final", "plataforma")
PASOS = ["2_entrenar_componentes", "3_guardar_modelos", "4_combinar_prophet_lstm", "5_serie_completa",
         "6_pronostico_futuro"]
RUIDO = ("WARNING: All log messages", "E0000", "W0000", "I0000", "oneDNN", "cpu_feature_guard", "To enable the following",
         "tf.reset_default_graph", "absl::InitializeLog", "node_def_util", "cmdstanpy", "Epoch ", "━")
inicio_total = time.time()


def log(texto):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {texto}", flush=True)


def paso(script, fuente=None):
    env = {**os.environ, "MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8"}
    env.pop("WAYRA_RAIZ", None)
    if fuente:
        env["WAYRA_FUENTE"] = fuente
    else:
        env.pop("WAYRA_FUENTE", None)
    etiqueta = f"{script}" + (f" (fuente {fuente})" if fuente else "")
    log(f"▶ {etiqueta}")
    t0 = time.time()
    proc = subprocess.Popen([sys.executable, "-u", "-X", "utf8", os.path.join("modelo_hibrido", f"{script}.py")],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace")
    for linea in proc.stdout:
        if linea.strip() and not any(r in linea for r in RUIDO):
            print("    " + linea.rstrip()[:220], flush=True)
    if proc.wait() != 0:
        log(f"✗ FALLÓ {etiqueta} (código {proc.returncode})")
        sys.exit(1)
    log(f"✓ {etiqueta} en {time.time() - t0:.0f} s")


def conectar():
    falta = [v for v in ("WAYRA_DB_HOST", "WAYRA_DB_PORT", "WAYRA_DB_NAME", "WAYRA_DB_USER", "WAYRA_DB_PASSWORD")
             if not os.environ.get(v)]
    if falta:
        log(f"✗ Faltan variables de conexión: {', '.join(falta)}")
        sys.exit(1)
    return psycopg2.connect(host=os.environ["WAYRA_DB_HOST"], port=os.environ["WAYRA_DB_PORT"],
                            dbname=os.environ["WAYRA_DB_NAME"], user=os.environ["WAYRA_DB_USER"],
                            password=os.environ["WAYRA_DB_PASSWORD"], sslmode="require", connect_timeout=30)


def verificar():
    nuevo = pd.read_csv(os.path.join(PLAT, "prediccion.csv"), sep=";", encoding="utf-8")
    nuevo["fecha_objetivo"] = pd.to_datetime(nuevo["fecha_objetivo"]).dt.date
    with conectar() as con:
        base = pd.read_sql("""
            SELECT e.codigo || '|' || v.codigo || '|' || m.version AS id_modelo, p.id_ejecucion, p.fecha_objetivo,
                   p.valor::float AS valor_base
            FROM prediccion p JOIN modelo m ON m.id_modelo = p.id_modelo
            JOIN estacion e ON e.id_estacion = m.id_estacion JOIN variable v ON v.id_variable = m.id_variable
            WHERE m.version = 'v3'""", con)
    llave = ["id_modelo", "id_ejecucion", "fecha_objetivo"]
    cruce = nuevo.merge(base, on=llave, how="outer", indicator=True)
    comunes = cruce[cruce["_merge"] == "both"].copy()
    comunes["dif"] = (comunes["valor"] - comunes["valor_base"]).abs()
    log(f"Predicciones de la v3: generadas {len(nuevo)}, en la base {len(base)}, en ambas {len(comunes)}, "
        f"solo generadas {int((cruce['_merge'] == 'left_only').sum())}, solo en la base {int((cruce['_merge'] == 'right_only').sum())}")
    for (mod, ej), g in comunes.groupby(["id_modelo", "id_ejecucion"]):
        log(f"   {mod:22s} ejecución {ej}: {len(g):4d} predicciones, diferencia máxima {g['dif'].max():.3f} µg/m³")
    futuro = comunes[comunes["id_ejecucion"] == 3].sort_values(["id_modelo", "fecha_objetivo"])
    log("Pronóstico de los próximos días (generado en la nube vs. el de la base):")
    for r in futuro.itertuples():
        log(f"   {r.id_modelo:22s} {r.fecha_objetivo}  {r.valor:8.3f}  vs  {r.valor_base:8.3f} µg/m³")
    # Resumen por estación: idéntico (diferencia <= 0,05 µg/m³) o equivalente (misma categoría INCA en el pronóstico)
    eca = {"SO2": 250.0, "PM10": 100.0}
    def categoria(v, cont):
        inca = v / eca[cont] * 100
        return "Buena" if inca <= 50 else "Moderada" if inca <= 100 else "Mala"
    log("RESULTADO por estación:")
    for mod, g in comunes.groupby("id_modelo"):
        f = futuro[futuro["id_modelo"] == mod]
        cont = mod.split("|")[1]
        misma = all(categoria(a, cont) == categoria(b, cont) for a, b in zip(f["valor"], f["valor_base"]))
        if g["dif"].max() <= 0.05:
            log(f"   {mod:22s} IDÉNTICO a la base (diferencia máxima {g['dif'].max():.3f} µg/m³)")
        else:
            rel = (f["dif"] / f["valor_base"]).max() * 100
            log(f"   {mod:22s} DIFERENTE: hasta {g['dif'].max():.1f} µg/m³ en la serie; en el pronóstico hasta "
                f"{f['dif'].max():.2f} µg/m³ ({rel:.1f} %), {'misma' if misma else 'distinta'} categoría INCA")
    return len(comunes) == len(nuevo) == len(base)


def cargar():
    env = {**os.environ, "WAYRA_RAIZ": os.path.join("modelo_hibrido", "version_final"), "PYTHONIOENCODING": "utf-8"}
    log("▶ 10-CARGAR_BD.py (carga en una sola transacción)")
    r = subprocess.run([sys.executable, "-u", "-X", "utf8", "10-CARGAR_BD.py"], env=env)
    if r.returncode != 0:
        log("✗ FALLÓ la carga en la base")
        sys.exit(1)
    log("✓ Carga terminada")


if __name__ == "__main__":
    if MODO not in ("verificar", "cargar"):
        log(f"✗ MODO desconocido: {MODO} (use verificar o cargar)")
        sys.exit(1)
    log(f"WayraPredict · proceso de predicción · modo {MODO} · Python {sys.version.split()[0]} · "
        f"oneDNN {'desactivado' if os.environ.get('TF_ENABLE_ONEDNN_OPTS') == '0' else 'por defecto'}")
    with conectar() as con, con.cursor() as cur:       # se comprueba la conexión antes de entrenar
        cur.execute("SELECT current_user, current_database(), (SELECT COUNT(*) FROM estacion)")
        usuario, base, n = cur.fetchone()
        log(f"Conexión a PostgreSQL correcta: base {base}, usuario {usuario}, {n} estaciones")
    paso("1_dataset")
    for script in PASOS:
        for fuente in ("combinada", "pasco_moquegua"):
            paso(script, fuente)
    paso("7_exportar_plataforma")
    ok = verificar() if MODO == "verificar" else (cargar() or True)
    log(f"Proceso terminado en {(time.time() - inicio_total) / 60:.1f} min")
    sys.exit(0 if ok else 2)      # 2 = faltan o sobran predicciones respecto de la base
