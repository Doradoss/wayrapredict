# %% [markdown]
# # Versión 3 — restricción de diseño del híbrido: peso mínimo de Prophet
#
# Restricción fijada ANTES de ver la prueba de esta variante: el híbrido siempre combina Prophet y LSTM,
# con w_prophet >= 0,05 (el primer valor de la grilla distinto de 0). Dentro de esa restricción, w y la
# corrección de Duan se eligen con la validación (motor.elegir_y_aplicar), como antes. La LSTM es la misma
# del componente F2c (no se reentrena). Salida: modelos/<estación>/F2c_h.pkl y, si los modelos ya están
# guardados, actualiza version_final/modelos/<estación>/config_hibrido.json y predicciones.csv.
# Ejecutar por fuente: WAYRA_FUENTE=combinada y WAYRA_FUENTE=pasco_moquegua.

# %%
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
import wayra_comun as wc
import wayra_prophet as wp
import wayra_hibrido as wh
import motor as mt

warnings.filterwarnings("ignore")
BASE = os.path.join(wc.RAIZ, "modelo_hibrido")
W_MIN = 0.05
mt.GRILLA = mt.GRILLA[mt.GRILLA >= W_MIN - 1e-9]
COLS = ["origen", "horizonte", "fecha_objetivo", "particion", "observado", "valor_principal", "var_log", "yhat", "yhat_lower",
        "yhat_upper", "obs_log"]
for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    est = cfg["estacion"]
    ds = wc.cargar_dataset(clave)
    wf = wh.walk_forward_prophet(ds, clave, wp.params_prophet(clave))
    sel = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_hibrido_seleccionado_walkforward_{clave}.pkl"))
    meta = json.load(open(os.path.join(wc.CARPETA_MODELOS, f"{clave}_hibrido_v2", "metadatos.json"), encoding="utf-8"))
    D = {"clave": clave, "cfg": cfg, "ds": ds, "est": est, "tag": est,
         "fin_train": pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1),
         "fin_val": pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1), "wf": wf, "sel": sel[sel["particion"].isin(["val", "test"])],
         "q_movil": meta.get("cuantil_alerta_origen_movil"), "p_lstm": None}
    base = pd.read_pickle(os.path.join(BASE, "modelos", est, "F2c.pkl"))
    t, el = mt.elegir_y_aplicar(D, base["pred"][COLS].copy())
    t["variante"] = "F2c_h"
    info = {**base["info"], "eleccion_val": el, "esquema": "F2c_h", "w_minimo_prophet": W_MIN}
    pd.to_pickle({"pred": t, "info": info}, os.path.join(BASE, "modelos", est, "F2c_h.pkl"))
    antes = base["info"]["eleccion_val"]
    print(f"{est}: w antes {[antes[h]['w_prophet'] for h in mt.H]} -> ahora {[el[h]['w_prophet'] for h in mt.H]} | "
          f"Duan {[el[h]['duan'] for h in mt.H]} | RMSE val antes {[antes[h]['rmse_val'] for h in mt.H]} -> {[el[h]['rmse_val'] for h in mt.H]}")
    destino = os.path.join(BASE, "version_final", "modelos", est)
    ruta_cfg = os.path.join(destino, "config_hibrido.json")
    if os.path.exists(ruta_cfg):
        c = json.load(open(ruta_cfg, encoding="utf-8"))
        c.update({"esquema": "F2c_h", "por_horizonte": {str(h): el[h] for h in el}, "w_minimo_prophet": W_MIN})
        json.dump(c, open(ruta_cfg, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        t[["origen", "horizonte", "fecha_objetivo", "particion", "observado", "valor", "limite_inferior", "limite_superior",
           "limite_alerta"]].to_csv(os.path.join(destino, "predicciones.csv"), sep=";", index=False, encoding="utf-8-sig")
