# %% [markdown]
# # Versión 3 — CSV de la plataforma para cargar en la base (10-CARGAR_BD.py)
#
# Parte de los CSV oficiales de plataforma/ (no los modifica) y escribe en version_final/plataforma/:
# - modelo.csv: v1 y v2 sin cambios pero NO vigentes; v3 vigente en las tres estaciones (RMSE, MAE y R² de la
#   prueba a h = 1 con todos sus pares; en Pasco, solo días propios).
# - Día actual de la plataforma = 3 días antes del último día con medición (decisión del usuario): las mediciones
#   del contaminante se cargan hasta ese día (la fecha de referencia del backend es la última medición con
#   origen 'estacion'); los 3 días siguientes quedan fuera de la carga (siguen en los CSV oficiales y el respaldo).
# - prediccion.csv: ejecución 2 = h = 1 de la v3 en la prueba hasta el día actual; ejecución 3 ("Próximos días")
#   = v3 desde el día actual a 1, 2 y 3 días (esos días tienen todas sus variables). Reemplazan a las de la v2.
# - estacion y ejecucion_proceso: copias sin cambios. Los días rellenados NO se cargan.
# Cargar con:  WAYRA_RAIZ=modelo_hibrido/version_final  python 10-CARGAR_BD.py

# %%
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
import wayra_comun as wc

BASE = os.path.join(wc.RAIZ, "modelo_hibrido")
ORIG = os.path.join(wc.RAIZ, "plataforma")
DEST = os.path.join(BASE, "version_final", "plataforma")
os.makedirs(DEST, exist_ok=True)
COMPONENTE = json.load(open(os.path.join(BASE, "resultados", "B12_version_final.json"), encoding="utf-8"))
SERIES = {"CA-CC-01": ("CA-CC-01_DIOXIDO_AZUFRE", "combinada", "SO2", "DIOXIDO_AZUFRE"),
          "CA-HUAR-01": ("CA-HUAR-01_PM10", "pasco_moquegua", "PM10", "PM10"),
          "CA-ILO-02": ("CA-ILO-02_PM10", "pasco_moquegua", "PM10", "PM10")}
leer = lambda n: pd.read_csv(os.path.join(ORIG, f"{n}.csv"), sep=";", encoding="utf-8", keep_default_na=False, na_values=[""])
shutil.copy(os.path.join(ORIG, "estacion.csv"), os.path.join(DEST, "estacion.csv"))
# ejecuciones 2 y 3 (predicciones de la v3): fecha de esta carga ("Última actualización de predicciones")
ejec = leer("ejecucion_proceso")
ahora_txt = pd.Timestamp.now().floor("s").strftime("%Y-%m-%d %H:%M:%S")
ejec.loc[ejec["id_ejecucion"].isin([2, 3]), ["fecha_inicio", "fecha_fin"]] = ahora_txt
ejec.to_csv(os.path.join(DEST, "ejecucion_proceso.csv"), sep=";", index=False, encoding="utf-8")
modelo, pred = leer("modelo"), leer("prediccion")
med = leer("medicion_diaria")
ultimo = med[med["origen"] == "estacion"].groupby(["id_estacion", "id_variable"])["fecha"].max()
DIAS_ATRAS = 3
ref = pd.to_datetime(ultimo) - pd.Timedelta(days=DIAS_ATRAS)     # día actual de la plataforma
quitar = pd.Series(False, index=med.index)
for (e_, v_), f_ in ref.items():
    if e_ in ("CA-CC-01", "CA-HUAR-01", "CA-ILO-02") and v_ in ("SO2", "PM10"):
        quitar |= (med["id_estacion"] == e_) & (med["id_variable"] == v_) & (pd.to_datetime(med["fecha"]) > f_)
print("Mediciones del contaminante posteriores al día actual (no se cargan):", int(quitar.sum()))
# meteorología pronosticada (ejecución 6) de los días posteriores al último dato: ya no corresponde a los días
# pronosticados por la v3 (que tienen meteorología medida), así que no se carga
pron = med["origen"] == "pronostico_meteo"
print("Meteorología pronosticada que ya no corresponde (no se carga):", int(pron.sum()))
quitar |= pron
med[~quitar].to_csv(os.path.join(DEST, "medicion_diaria.csv"), sep=";", index=False, encoding="utf-8")


def categoria(valor, eca):
    inca = valor / eca * 100
    return "Buena" if inca <= 50 else ("Moderada" if inca <= 100 else "Mala")


modelo["vigente"] = False
filas_m, filas_p = [], []
ahora = pd.Timestamp.now().floor("s")
for est, (clave, fuente, var, cont) in SERIES.items():
    comp = pd.read_pickle(os.path.join(BASE, "modelos", est, f"{COMPONENTE[est]}.pkl"))["pred"]
    ds = wc.cargar_dataset(clave, fuente)
    rell = set(ds.index[ds["RELLENO"] == 1]) if "RELLENO" in ds else set()
    g = comp[(comp["particion"] == "test") & (comp["horizonte"] == 1)].dropna(subset=["valor"]).copy()
    ev = g[~g["fecha_objetivo"].isin(rell)].dropna(subset=["observado"])
    m = wc.metricas_regresion(ev["observado"], ev["valor"])
    idm = f"{est}|{var}|v3"
    filas_m.append({"id_modelo": idm, "id_estacion": est, "id_variable": var, "version": "v3", "ruta_blob": f"modelos/{est}/v3/",
                    "fecha_entrenamiento": ahora, "rmse": round(m["RMSE"], 4), "mae": round(m["MAE"], 4), "r2": round(m["R2"], 4),
                    "vigente": True})
    fref = pd.Timestamp(ref.loc[(est, var)])
    fut = comp[(comp["origen"] == fref)].dropna(subset=["valor"]).sort_values("horizonte")
    g = g[g["fecha_objetivo"] <= fref]
    eca = wc.ECA_24H[cont]
    for r in g.sort_values("fecha_objetivo").itertuples():
        filas_p.append({"id_modelo": idm, "id_ejecucion": 2, "fecha_objetivo": r.fecha_objetivo.date(), "valor": round(r.valor, 3),
                        "limite_inferior": round(r.limite_inferior, 3), "limite_superior": round(r.limite_superior, 3),
                        "id_categoria": categoria(r.valor, eca), "verificado": False, "verificado_por": None, "fecha_verificacion": None})
    for r in fut.itertuples():
        filas_p.append({"id_modelo": idm, "id_ejecucion": 3, "fecha_objetivo": r.fecha_objetivo.date(), "valor": round(r.valor, 3),
                        "limite_inferior": round(r.limite_inferior, 3), "limite_superior": round(r.limite_superior, 3),
                        "id_categoria": categoria(r.valor, eca), "verificado": False, "verificado_por": None, "fecha_verificacion": None})
    print(f"{est}: día actual {fref.date()} | próximos días v3: " +
          ", ".join(f"{r.fecha_objetivo.date()} = {r.valor:.1f} (obs. {r.observado:.1f})" for r in fut.itertuples()))
    print(f"{est}: v3 = {COMPONENTE[est]} | RMSE {m['RMSE']:.2f}, MAE {m['MAE']:.2f}, R² {m['R2']:.3f} (n = {m['n']}) | "
          f"predicciones ejecución 2: {len(g)} (hasta {fref.date()})")
modelo = pd.concat([modelo, pd.DataFrame(filas_m)], ignore_index=True)
pred = pd.concat([pred[~pred["id_ejecucion"].isin([2, 3])], pd.DataFrame(filas_p)], ignore_index=True)
modelo.to_csv(os.path.join(DEST, "modelo.csv"), sep=";", index=False, encoding="utf-8")
pred.to_csv(os.path.join(DEST, "prediccion.csv"), sep=";", index=False, encoding="utf-8")
print(modelo[["id_modelo", "rmse", "mae", "r2", "vigente"]].to_string(index=False))
print(pred.groupby(["id_ejecucion", "id_modelo"]).size().to_string())
print(pred[pred["id_ejecucion"] == 2]["id_categoria"].value_counts().to_string())
