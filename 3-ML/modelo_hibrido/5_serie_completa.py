# %% [markdown]
# # Versión 3 — híbrido con la serie rellenada como entrada (sin huecos en los pronósticos)
#
# Igual que F2c_h (mismas variables, semilla, hiperparámetros y restricción w_prophet >= 0,05), pero:
# - la serie del contaminante que entra a la LSTM es la del dataset rellenado (los días sin medición llevan la
#   mediana del mismo mes del entrenamiento) y la entrada y_falta marca esos días (dato_rellenado);
# - se usan todas las ventanas (wl.MIN_FRACCION_OBSERVADA = 0) y se pronostica desde TODOS los orígenes de
#   validación y prueba del walk-forward de Prophet, también en los tramos sin medición.
# Los objetivos de entrenamiento y las métricas siguen siendo SOLO días con medición real (la pérdida ignora
# los faltantes). Salida: modelos/<estación>/F2c_r.pkl
# Ejecutar por fuente (correr_A14.bat): WAYRA_FUENTE=combinada y WAYRA_FUENTE=pasco_moquegua.

# %%
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("modelo_hibrido"))
import wayra_comun as wc
import wayra_prophet as wp
import wayra_lstm as wl
import wayra_hibrido as wh
import motor as mt
import v3_entradas as ve

warnings.filterwarnings("ignore")
BASE = os.path.join(wc.RAIZ, "modelo_hibrido")
NOMBRE = "F2c_r"
W_MIN = 0.05
mt.GRILLA = mt.GRILLA[mt.GRILLA >= W_MIN - 1e-9]
wl.MIN_FRACCION_OBSERVADA = 0.0
_futuro_original = mt.futuro_externo
mt.futuro_externo = lambda D, tipo, modelo="best_match": ve.futuro(D, "F2c", modelo, _futuro_original)

for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    est = cfg["estacion"]
    ruta = os.path.join(BASE, "modelos", est, f"{NOMBRE}.pkl")
    if os.path.exists(ruta):
        print(f"{est}: ya existe {ruta}")
        continue
    ds = wc.cargar_dataset(clave)
    wf = wh.walk_forward_prophet(ds, clave, wp.params_prophet(clave))
    # base de pares (origen, horizonte) = todos los del walk-forward con objetivo en validación o prueba
    sel = wf[["origen", "horizonte", "fecha_objetivo", "yhat"]].copy()
    sel["particion"] = wc.asignar_particion(pd.DatetimeIndex(sel["fecha_objetivo"]), clave).to_numpy()
    sel = sel[sel["particion"].isin(["val", "test"])]
    sel["observado"] = ds["OBJETIVO"].reindex(sel["fecha_objetivo"]).to_numpy()
    sel["valor"] = np.expm1(sel["yhat"])
    meta = json.load(open(os.path.join(wc.CARPETA_MODELOS, f"{clave}_hibrido_v2", "metadatos.json"), encoding="utf-8"))
    D = {"clave": clave, "cfg": cfg, "ds": ds, "est": est, "tag": est,
         "fin_train": pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1),
         "fin_val": pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1), "wf": wf, "sel": sel.drop(columns="yhat"),
         "q_movil": meta.get("cuantil_alerta_origen_movil"), "p_lstm": None, "carpeta": os.path.join(BASE, "modelos", est)}
    oficial = pd.read_pickle(os.path.join(wc.RAIZ, "v2", "modelos", est, "E9opt.pkl"))
    params, fuente = oficial["info"]["params"], oficial["info"]["fuente_meteo"]
    v = mt.variables_base(D, ve.extras(est, ds.index))
    rel = ve.DATASET[ve.DATASET["estacion"] == est].reindex(ds.index)
    v["y_log"] = np.log1p(rel["OBJETIVO"])                       # serie rellenada (sin huecos)
    v["y_falta"] = (rel["relleno_tipo"] == "climatologia_mensual_train").astype(float)   # 1 = día sin medición (rellenado)
    t0 = time.time()
    wl.fijar_semillas_keras()
    pred, info = mt.correr_lstm(D, v, params, NOMBRE, fuente)
    t, el = mt.elegir_y_aplicar(D, mt.tabla_larga(D, pred))
    t["variante"] = NOMBRE
    pd.to_pickle({"pred": t, "info": {**info, "params": params, "eleccion_val": el, "fuente_meteo": fuente, "esquema": NOMBRE,
                                      "w_minimo_prophet": W_MIN, "serie_rellenada": True}}, ruta)
    n_ok = t.dropna(subset=["valor"]).groupby("particion").size().to_dict()
    print(f"{est}: {time.time() - t0:.0f} s | RMSE val = {[el[h]['rmse_val'] for h in mt.H]} | w = {[el[h]['w_prophet'] for h in mt.H]} | "
          f"pronósticos {n_ok}", flush=True)
