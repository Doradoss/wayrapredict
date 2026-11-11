# %% [markdown]
# # Versión 3 — guardar los modelos entrenados (LSTM .keras, Prophet y configuración del híbrido)
#
# Reentrena la LSTM del componente elegido (resultados/componente_final.json) con la misma semilla, datos e hiperparámetros (reproduce las
# predicciones guardadas) y guarda en version_final/modelos/<estación>/:
#   lstm_A.keras (entrenada con train; pronostica validación), lstm_B.keras (train + val; pronostica la prueba),
#   prophet.json (Prophet ajustado hasta el fin de la prueba), config_hibrido.json (w, Duan, cuantil de alerta,
#   hiperparámetros y normalización) y predicciones.csv (val y prueba).
# Ejecutar por fuente: WAYRA_FUENTE=combinada y WAYRA_FUENTE=pasco_moquegua (lanzador correr_A09.bat).

# %%
import json
import os
import shutil
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
import wayra_comun as wc
import wayra_prophet as wp
import wayra_lstm as wl
import wayra_hibrido as wh
import motor as mt

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.abspath("modelo_hibrido"))
import v3_entradas as ve

BASE = os.path.join(wc.RAIZ, "modelo_hibrido")
COMPONENTE = json.load(open(os.path.join(BASE, "resultados", "componente_final.json"), encoding="utf-8"))


for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    est = cfg["estacion"]
    destino = os.path.join(BASE, "version_final", "modelos", est)
    os.makedirs(destino, exist_ok=True)
    ds = wc.cargar_dataset(clave)
    wf = wh.walk_forward_prophet(ds, clave, wp.params_prophet(clave))
    sel = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_hibrido_seleccionado_walkforward_{clave}.pkl"))
    sel = sel[sel["particion"].isin(["val", "test"])]
    meta = json.load(open(os.path.join(wc.CARPETA_MODELOS, f"{clave}_hibrido_v2", "metadatos.json"), encoding="utf-8"))
    D = {"clave": clave, "cfg": cfg, "ds": ds, "est": est, "tag": est,
         "fin_train": pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1),
         "fin_val": pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1), "wf": wf, "sel": sel,
         "q_movil": meta.get("cuantil_alerta_origen_movil"), "p_lstm": None, "carpeta": destino}
    oficial = pd.read_pickle(os.path.join(wc.RAIZ, "v2", "modelos", est, "E9opt.pkl"))
    p, fuente = oficial["info"]["params"], oficial["info"]["fuente_meteo"]
    esquema = "F2c"   # LSTM base de la v3: los pasos siguientes (F2c_h, F2c_r, F2c_hc) la combinan con Prophet
    v = mt.variables_base(D, ve.extras(est, ds.index))
    # mismo cálculo que mt.correr_lstm, pero conservando los modelos
    wl.fijar_semillas_keras()
    fut, inicio = ve.futuro(D, esquema, fuente, mt.futuro_externo)
    M = mt.muestras(D, v, p, fut, inicio)
    s = M["sel"]
    nf = M["F"].shape[1] if M["F"] is not None else 0
    mt.liberar()
    mA, mB, ep = mt.entrenar_AB(mt._entrada(M, s["train"]), M["Y"][s["train"]], mt._entrada(M, s["val"]), M["Y"][s["val"]],
                                mt._entrada(M, s["tv"]), M["Y"][s["tv"]], p, M["X"].shape[2], nf)
    usaB = np.asarray(M["O"] >= D["fin_val"])
    pred = np.empty((len(M["O"]), mt.NH))
    for mod, m in ((mA, ~usaB), (mB, usaB)):
        if m.any():
            pred[m] = mod.predict(mt._entrada(M, m), verbose=0) * M["sd"] + M["mu"]
    mA.save(os.path.join(destino, "lstm_A.keras"))
    mB.save(os.path.join(destino, "lstm_B.keras"))
    # comprobación: reproduce las predicciones guardadas del componente F2c
    guardado = pd.read_pickle(os.path.join(BASE, "modelos", est, f"{esquema}.pkl"))
    t = guardado["pred"].set_index(["origen", "horizonte"])["var_log"]
    nuevo = pd.DataFrame(pred, index=M["O"], columns=mt.H).stack()
    nuevo.index.names = ["origen", "horizonte"]
    dif = (nuevo.reindex(t.index) - t).abs().max()
    el = guardado["info"]["eleccion_val"]
    json.dump({"estacion": est, "contaminante": cfg["contaminante"], "version": "v3", "esquema": esquema,
               "combinacion": "valor = expm1(w * yhat_prophet_log + (1 - w) * lstm_log), multiplicado por factor_duan si duan",
               "por_horizonte": {str(h): el[h] for h in el}, "hiperparametros_lstm": p, "fuente_meteorologica": fuente,
               "normalizacion_objetivo": {"media": float(M["mu"]), "desviacion": float(M["sd"])}, "epocas": ep,
               "cortes": {"fin_entrenamiento": str(D["fin_train"].date()), "fin_validacion": str(D["fin_val"].date())},
               "lstm_A": "lstm_A.keras: entrenada con el entrenamiento; pronostica la validación",
               "lstm_B": "lstm_B.keras: entrenada con entrenamiento + validación; pronostica la prueba",
               "prophet": "prophet.json: ajuste con todos los datos hasta el fin de la prueba (el walk-forward reajusta en cada origen)",
               "max_diferencia_reproduccion_log": float(dif)},
              open(os.path.join(destino, "config_hibrido.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.copy(os.path.join(wc.CARPETA_MODELOS, f"{clave}_prophet_v1", "prophet_hasta_fin_test.json"), os.path.join(destino, "prophet.json"))
    guardado["pred"][["origen", "horizonte", "fecha_objetivo", "particion", "observado", "valor", "limite_inferior", "limite_superior",
                      "limite_alerta"]].to_csv(os.path.join(destino, "predicciones.csv"), sep=";", index=False, encoding="utf-8-sig")
    print(f"{est}: modelos guardados en {destino} | diferencia máxima con lo guardado (log) = {dif:.6f}", flush=True)
    del mA, mB
    mt.liberar()
