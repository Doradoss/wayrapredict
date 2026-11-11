# %% [markdown]
# # 09a - Pronóstico a 1, 2 y 3 días desde el último día con datos de cada estación
#
# Auxiliar de `09-EXPORTAR_PLATAFORMA.py`. **No cambia ningún modelo, selección ni resultado**: solo produce
# pronósticos con los modelos y elecciones ya guardados, para los orígenes que no tienen pronóstico guardado.
# Se ejecuta UNA VEZ POR FUENTE (09 lo lanza solo si falta su salida):
#   WAYRA_FUENTE=combinada       python 09a-PRONOSTICO_ULTIMO_DATO.py   (Junín SO2)
#   WAYRA_FUENTE=pasco_moquegua  python 09a-PRONOSTICO_ULTIMO_DATO.py   (Pasco y Moquegua PM10)
#
# Qué falta y cómo se completa:
# - Junín (CA-CC-01): último dato 28/06/2026. La h = 1 y 2 de ese origen ya están guardadas (v1 y v2). La h = 3
#   (01/07/2026) no existe porque la serie termina el 30/06/2026. v1 a h = 3 es "Residuos con alfa = 0" = Prophet
#   ajustado: se reproduce el ajuste del walk-forward (mismo bloque de 7 días, mismos hiperparámetros, OPERACION =
#   último estado conocido) y se comprueba contra h = 1 y 2 guardadas. La v2 a h = 3 (E8 y E7 del experimento 1)
#   no se puede reproducir: esos modelos no se guardaron -> se usa v1 (regla de instrucciones_8).
# - Pasco (CA-HUAR-01): último dato 30/06/2026. v1 ya tiene h = 1-3 (días extendidos). v2 (EF2) combina E9 con
#   cuatro fuentes meteorológicas; sus pronósticos se cortaron el 30/06/2026 porque Previous Runs se descargó hasta
#   esa fecha. Se descarga Previous Runs del 01-03/07/2026 (emitido el 30/06/2026), se reentrena cada componente
#   con SUS hiperparámetros y semilla (mismo procedimiento A/B; el resultado en la prueba se compara con lo
#   guardado) y se aplican la elección de validación y los pesos EF2 guardados. Si la descarga falla -> v1.
# - Moquegua (CA-ILO-02): vigente v1, ya tiene h = 1-3 desde el último dato (31/05/2026). No usa la API.
# Salidas: plataforma/intermedio/09a_futuro_<fuente>.pkl y plataforma/intermedio/meteo_futuro/ (JSON crudos).

# %%
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("experimento_2"))
import wayra_comun as wc
import wayra_prophet as wp
import wayra_hibrido as wh

warnings.filterwarnings("ignore")
PLAT = os.path.join(wc.RAIZ, "plataforma")
DIR_INT = os.path.join(PLAT, "intermedio")
DIR_MET = os.path.join(DIR_INT, "meteo_futuro")
os.makedirs(DIR_MET, exist_ok=True)
H = wc.HORIZONTES
EXP2 = os.path.join(wc.RAIZ, "experimento_2")
COORD = {"CA-CC-01": (-11.51995, -75.90088), "CA-HUAR-01": (-10.79368, -76.29212), "CA-ILO-02": (-17.61076, -71.34065)}
VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m", "precipitation", "cloud_cover"]
MODELOS_MET = ["best_match", "gfs_seamless", "jma_seamless", "icon_seamless", "ecmwf_ifs025"]


def ultimo_dato(ds):
    return ds["OBJETIVO"].last_valid_index()


def seleccion_principal(clave):
    sel = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_hibrido_seleccionado_walkforward_{clave}.pkl"))
    col = "limite_alerta_movil" if "limite_alerta_movil" in sel else "limite_alerta"
    return sel, col


resultado = {}

# %% [markdown]
# ## Junín: v1 a h = 3 reproduciendo el bloque de Prophet del walk-forward

# %%
if wc.FUENTE_DATOS == "combinada":
    clave = "CA-CC-01_DIOXIDO_AZUFRE"
    cfg = wc.SERIES[clave]
    ds = wc.cargar_dataset(clave)
    t0 = ultimo_dato(ds)
    sel, _ = seleccion_principal(clave)
    params = wp.params_prophet(clave)
    # bloque de 7 días que contiene el origen (misma aritmética que wh.walk_forward_prophet)
    fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
    desde = ds.index.min() + pd.Timedelta(days=wh.DIAS_CALENTAMIENTO)
    k = int(np.ceil((fin_train - desde).days / wp.REENTRENAR_CADA))
    inicio = fin_train - pd.Timedelta(days=k * wp.REENTRENAR_CADA)
    bloque0 = inicio + pd.Timedelta(days=((t0 - inicio).days // wp.REENTRENAR_CADA) * wp.REENTRENAR_CADA)
    estado = float(ds["OPERACION_CAUSAL"].ffill().loc[t0])
    m = wp.ajustar_prophet(ds, bloque0, True, params)
    fechas = pd.date_range(t0 + pd.Timedelta(days=1), periods=len(H))
    pr = wp.predecir(m, fechas, estado, True)
    guard = sel[(sel["origen"] == t0)].set_index("horizonte")
    control = {h: (float(pr["yhat"].iloc[h - 1]), float(guard.at[h, "prophet_log"])) for h in H if h in guard.index}
    print(f"Junín: último dato {t0.date()} | bloque de Prophet ajustado con datos <= {bloque0.date()} | OPERACION = {estado}")
    print("   control yhat (log) reproducido vs guardado:", {h: (round(a, 5), round(b, 5)) for h, (a, b) in control.items()})
    dif = max(abs(a - b) for a, b in control.values())
    assert dif < 1e-6, f"El ajuste de Prophet no reproduce el walk-forward guardado (dif {dif})"
    filas = []
    for h in H:
        if h in guard.index:     # ya guardado (v1)
            g = guard.loc[h]
            filas.append({"origen": t0, "horizonte": h, "fecha_objetivo": g["fecha_objetivo"], "valor": g["valor"],
                          "limite_inferior": g["limite_inferior"], "limite_superior": g["limite_superior"], "fuente": "guardado"})
        else:                    # h = 3: selección "Residuos" con alfa = 0 y sin Duan = Prophet ajustado
            f = fechas[h - 1]
            filas.append({"origen": t0, "horizonte": h, "fecha_objetivo": f, "valor": float(np.expm1(pr.at[f, "yhat"])),
                          "limite_inferior": float(np.expm1(pr.at[f, "yhat_lower"])),
                          "limite_superior": float(np.expm1(pr.at[f, "yhat_upper"])), "fuente": "Prophet reproducido (alfa = 0)"})
    resultado[clave] = {"ultimo_dato": t0, "v1": pd.DataFrame(filas), "v2": None,
                        "nota_v2": "h = 1-2 guardadas en los componentes; h = 3 no disponible (E8 y E7 del experimento 1 sin modelo guardado)"}
    print(pd.DataFrame(filas).to_string(index=False))

# %% [markdown]
# ## Pasco: componentes de la versión 2 con Previous Runs emitido el día del último dato

# %%
def descargar_pr(est, modelo, a, b, lag):
    lat, lon = COORD[est]
    params = {"latitude": lat, "longitude": lon, "timezone": "America/Lima", "start_date": a, "end_date": b,
              "hourly": ",".join(f"{v}_previous_day{lag}" for v in VARS)}
    if modelo != "best_match":
        params["models"] = modelo
    ruta = os.path.join(DIR_MET, f"pr{lag}_{modelo}_{est}_{a}_{b}.json")
    if os.path.exists(ruta):
        return json.load(open(ruta, encoding="utf-8"))
    for i in range(4):
        try:
            r = requests.get("https://previous-runs-api.open-meteo.com/v1/forecast", params=params, timeout=120)
            if r.status_code == 200:
                json.dump(r.json(), open(ruta, "w", encoding="utf-8"))
                time.sleep(0.5)
                return r.json()
            print("  ", modelo, lag, r.status_code, r.text[:120])
        except Exception as ex:
            print("  ", modelo, lag, type(ex).__name__)
        time.sleep(5 * (i + 1))
    return None


def diario(d, lag):
    """Misma agregación diaria que experimento_mejoras/E01 y experimento_2/F3a."""
    h = pd.DataFrame(d["hourly"])
    h["time"] = pd.to_datetime(h["time"])
    h = h.set_index("time").apply(pd.to_numeric, errors="coerce")
    v = lambda n: f"{n}_previous_day{lag}"
    g = h.groupby(h.index.floor("D"))
    out = pd.DataFrame(index=g.size().index)
    out["temp"] = g[v("temperature_2m")].mean()
    out["hr"] = g[v("relative_humidity_2m")].mean()
    out["viento"] = g[v("wind_speed_10m")].mean() / 3.6
    rad = np.deg2rad(h[v("wind_direction_10m")])
    out["viento_sin"] = np.sin(rad).groupby(h.index.floor("D")).mean()
    out["viento_cos"] = np.cos(rad).groupby(h.index.floor("D")).mean()
    out["precip"] = g[v("precipitation")].sum(min_count=20)
    out["nubes"] = g[v("cloud_cover")].mean()
    return out.where(g[v("temperature_2m")].count() >= 20)


if wc.FUENTE_DATOS == "pasco_moquegua":
    import motor as mt
    import wayra_lstm as wl
    # Moquegua: vigente v1, ya guardado desde el último dato
    for clave in ("CA-ILO-02_PM10", "CA-HUAR-01_PM10"):
        ds = wc.cargar_dataset(clave)
        t0 = ultimo_dato(ds)
        sel, _ = seleccion_principal(clave)
        g = sel[sel["origen"] == t0].sort_values("horizonte")
        v1 = g[["origen", "horizonte", "fecha_objetivo", "valor", "limite_inferior", "limite_superior"]].assign(fuente="guardado")
        assert len(v1) == len(H), f"{clave}: faltan horizontes de v1 desde {t0.date()}"
        resultado[clave] = {"ultimo_dato": t0, "v1": v1.reset_index(drop=True), "v2": None, "nota_v2": "no aplica (vigente v1)"}
        print(f"{clave}: último dato {t0.date()} | v1 guardado h = 1-3")

    clave, est = "CA-HUAR-01_PM10", "CA-HUAR-01"
    ds = wc.cargar_dataset(clave)
    t0 = resultado[clave]["ultimo_dato"]
    a, b = (t0 + pd.Timedelta(days=1)).date().isoformat(), (t0 + pd.Timedelta(days=len(H))).date().isoformat()
    versiones = json.load(open(os.path.join(EXP2, "resultados", "F4_versiones.json"), encoding="utf-8"))[clave]
    pesos = {int(h): w for h, w in versiones["pesos_EF2"].items()}
    componentes = sorted({n for w in pesos.values() for n, x in w.items() if x > 0 and n != "Principal"})
    print(f"\nPasco v2 (EF2): componentes con peso > 0 = {componentes}")
    # Componentes que se pueden regenerar con sus hiperparámetros, semilla y elección de validación GUARDADOS:
    # E9m_<modelo> y E9opt (LSTM + pronóstico meteorológico) y E7_combinacion (pesos guardados sobre Prophet, LSTM
    # local, LSTM global y persistencia). Un horizonte con otro componente queda sin v2 (09 usa v1 ahí).

    def ruta_comp(n):
        return os.path.join(wc.RAIZ, "experimento_mejoras" if n.startswith("x1_") else "experimento_2", "modelos", est, f"{n[3:]}.pkl")

    def fuente_meteo(n):
        if n.startswith("x2_E9m_"):
            return n.replace("x2_E9m_", "")
        return pd.read_pickle(ruta_comp(n))["info"]["fuente_meteo"] if n == "x2_E9opt" else None

    regenerables = [n for n in componentes if n.startswith("x2_E9m_") or n in ("x2_E9opt", "x1_E7_combinacion")]
    print(f"   regenerables: {regenerables} | no regenerables: {sorted(set(componentes) - set(regenerables))}")
    # 1) Previous Runs emitido el día de origen para los modelos meteorológicos que se usan
    datos = pd.read_pickle(os.path.join(EXP2, "datos_externos", f"{est}_meteo_multimodelo.pkl"))
    fuentes = {fuente_meteo(n) for n in regenerables} - {None}
    necesarios = set(MODELOS_MET) if "promedio" in fuentes else fuentes
    falta = []
    for mdl in sorted(necesarios):
        for lag in H:
            d = descargar_pr(est, mdl, a, b, lag)
            if d is None:
                falta.append((mdl, lag))
                continue
            nuevo = diario(d, lag)
            base = datos[mdl]["pr"][lag]
            datos[mdl]["pr"][lag] = pd.concat([base[base.index < nuevo.index.min()], nuevo.reindex(columns=base.columns)])
    ok_meteo = not any(mdl in necesarios for mdl, _ in falta)
    # comprobar que el pronóstico de cada horizonte existe para su fecha objetivo
    for mdl in necesarios:
        for h in H:
            f = t0 + pd.Timedelta(days=h)
            if datos[mdl]["pr"][h].reindex([f])["temp"].isna().any():
                ok_meteo = False
                print(f"   sin pronóstico {mdl} previous_day{h} para {f.date()}")
    if not ok_meteo:
        print("   Pronóstico meteorológico NO disponible -> el pronóstico de Pasco se asigna a v1")
        resultado[clave]["nota_v2"] = "Previous Runs no disponible: se usa v1"
    else:
        pd.to_pickle(datos, os.path.join(DIR_INT, f"{est}_meteo_multimodelo_extendido.pkl"))

        def meteo_fuente(D, modelo):     # misma lógica que motor.meteo_fuente, con los datos extendidos
            if modelo != "promedio":
                return datos[modelo]["hf"], datos[modelo]["pr"]
            disp = [m for m, d in datos.items() if d["hf"] is not None]
            hf = pd.concat([datos[m]["hf"] for m in disp]).groupby(level=0).mean()
            pr = {h: pd.concat([datos[m]["pr"][h] for m in disp if datos[m]["pr"][h] is not None]).groupby(level=0).mean() for h in H}
            return hf, pr
        mt.meteo_fuente = meteo_fuente

        cfg = wc.SERIES[clave]
        sel, col_al = seleccion_principal(clave)
        wf = wh.walk_forward_prophet(ds, clave, wp.params_prophet(clave))      # caché existente (solo lectura)
        D = {"clave": clave, "cfg": cfg, "ds": ds, "est": est, "tag": est,
             "fin_train": pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1),
             "fin_val": pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1), "wf": wf, "sel": sel, "q_movil": None}
        v0 = mt.variables_base(D)
        comp, control = {}, {}
        for n in regenerables:
            guardado = pd.read_pickle(ruta_comp(n))
            info = guardado["info"]
            if n == "x1_E7_combinacion":       # pesos guardados sobre componentes que ya llegan al último dato
                tabs = {"Prophet": f"04_prophet_walkforward_{clave}.pkl", "LSTM local": f"05_lstm_walkforward_{clave}.pkl",
                        "LSTM global": f"05_lstm_global_walkforward_{clave}.pkl"}
                serie = {}
                for h in H:
                    v = 0.0
                    for nombre, x in info["eleccion_val"][int(h)].items():
                        if nombre in ("rmse_val", "cuantil_alerta") or x == 0:
                            continue
                        if nombre == "Persistencia":
                            val = ds["OBJETIVO"].ffill().get(t0, np.nan)
                        else:
                            tab = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, tabs[nombre]))
                            fila = tab[(tab["origen"] == t0) & (tab["horizonte"] == h)]
                            val = float(fila["valor"].iloc[0]) if len(fila) else np.nan
                        v += x * val
                    serie[(t0, h)] = v
                comp[n] = pd.Series(serie)
                control[n] = {"nota": "pesos guardados", "valores": {f"h{k[1]}": round(x, 3) for k, x in serie.items()}}
                print(f"   {n}: {control[n]}")
                continue
            wl.fijar_semillas_keras()
            pred, _ = mt.correr_lstm(D, v0, info["params"], "meteo_pron", fuente_meteo(n))
            t = mt.tabla_larga(D, pred)
            partes = []
            for h, g in t.groupby("horizonte"):
                e = info["eleccion_val"][int(h)]          # elección de validación GUARDADA (no se reelige)
                centro = e["w_prophet"] * g["yhat"] + (1 - e["w_prophet"]) * g["var_log"]
                g = g.assign(valor=np.exp(centro) * e["factor_duan"] - 1 if e["duan"] else np.expm1(centro))
                partes.append(g)
            t = pd.concat(partes)
            comp[n] = t.set_index(["origen", "horizonte"])["valor"]
            ref = guardado["pred"].set_index(["origen", "horizonte"])["valor"]
            comun = ref.index.intersection(comp[n].index)
            dif = (comp[n].reindex(comun) - ref.reindex(comun)).abs()
            # los orígenes de los últimos 2 días antes del último dato SÍ cambian: antes les faltaba el pronóstico
            # meteorológico de julio (entrada "faltante"), ahora lo tienen. El resto debe coincidir.
            recientes = dif.index.get_level_values("origen") >= t0 - pd.Timedelta(days=len(H) - 1)
            control[n] = {"pares_comparados": int(dif[~recientes].notna().sum()), "dif_max": float(dif[~recientes].max()),
                          "dif_max_origenes_recientes": float(dif[recientes].max())}
            print(f"   {n}: reproducción frente a lo guardado -> {control[n]}")
        # 2) EF2 con los pesos guardados; intervalo = el del principal desplazado (como en experimento_2/F4)
        filas = []
        for h in H:
            f = t0 + pd.Timedelta(days=h)
            w = {n: x for n, x in pesos[h].items() if x > 0}
            p = sel[(sel["origen"] == t0) & (sel["horizonte"] == h)].iloc[0]
            valor = sum(x * (p["valor"] if n == "Principal" else comp[n].get((t0, h), np.nan) if n in comp else np.nan)
                        for n, x in w.items())
            d_log = np.log1p(max(valor, 0)) - np.log1p(max(p["valor"], 0)) if pd.notna(valor) else np.nan
            filas.append({"origen": t0, "horizonte": h, "fecha_objetivo": f, "valor": float(valor),
                          "limite_inferior": float(np.expm1(np.log1p(p["limite_inferior"]) + d_log)),
                          "limite_superior": float(np.expm1(np.log1p(p["limite_superior"]) + d_log)),
                          "fuente": "EF2 regenerado (Previous Runs emitido el " + str(t0.date()) + ")",
                          "componentes": json.dumps({n: (round(float(p["valor"] if n == "Principal" else comp[n].get((t0, h), np.nan)), 3)
                                                         if n == "Principal" or n in comp else None) for n in w})})
        v2 = pd.DataFrame(filas)
        resultado[clave]["v2"] = v2          # horizonte con NaN = componente no regenerable -> 09 usa v1 ahí
        resultado[clave]["control_reproduccion"] = control
        resultado[clave]["nota_v2"] = "EF2 regenerado con Previous Runs del día de origen"
        print(v2.to_string(index=False))

pd.to_pickle(resultado, os.path.join(DIR_INT, f"09a_futuro_{wc.FUENTE_DATOS}.pkl"))
print("\nGuardado:", os.path.join(DIR_INT, f"09a_futuro_{wc.FUENTE_DATOS}.pkl"))
