# %% [markdown]
# # Experimento actividad industrial — Nivel 2: variables sintéticas DERIVADAS DEL OBJETIVO (con fuga)
#
# **Autorizado por la profesora como "data sintética" (instrucciones_16). Las métricas de este nivel NO miden la
# capacidad de pronosticar: usan información del día objetivo (o de días posteriores al origen) que no existe al
# momento de predecir. No se usan en la plataforma ni en los resultados oficiales de la tesis.**
#
# Mismo modelo, cortes, semilla e hiperparámetros que la línea base (E9opt: LSTM + pronóstico meteorológico del
# día objetivo, combinada con Prophet con w y Duan elegidos en validación). Las variables sintéticas del día
# objetivo entran por el mismo canal que el pronóstico meteorológico (vector de cada horizonte).
#   F2a  etiquetas de actividad con ventana centrada (t-3..t+3) en la ventana de entrada (= FUGA de A02)
#   F2b  F2a + estado, intensidad y actividad del DÍA OBJETIVO (ventana centrada en el día objetivo)
#   F2d  F2c + perfil horario de emisión del día objetivo (máximo horario, horas altas, amplitud)
#   F2c  F2b + emisión proxy del día objetivo (media móvil centrada de 3 días del observado, que incluye el día
#        objetivo), indicador de pico (observado > P90 del entrenamiento) y magnitud del pico
# Ejecutar por fuente: WAYRA_FUENTE=combinada y WAYRA_FUENTE=pasco_moquegua.

# %%
import json
import os
import sys
import time
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
BASE = os.path.join(wc.RAIZ, "modelo_hibrido")
DATASET = pd.read_pickle(os.path.join(BASE, "datos", "dataset_combinado_enriquecido.pkl"))
ESTADOS = ["A", "I", "T", "D"]
_futuro_original = mt.futuro_externo


def sinteticas_objetivo(est, nivel, fin_train):
    """Columnas sintéticas del día objetivo (con fuga), por fecha."""
    d = DATASET[DATASET["estacion"] == est]
    obs = d["OBJETIVO"].where(d["relleno_tipo"].isin(["observado", "estacion_vecina"]))
    x = pd.DataFrame(index=d.index)
    x["obj_intensidad"] = d["intensidad_operacion_FUGA"]
    x["obj_actividad"] = d["actividad_industrial_FUGA"]
    for e in ESTADOS:
        x[f"obj_estado_{e}"] = (d["estado_operacion_FUGA"] == e).astype(float)
    if nivel == "F2d":      # perfil horario de emisión del día objetivo (máximo horario, horas altas, amplitud)
        x["obj_max_horario"] = np.log1p(d["MAXIMO_HORARIO"].where(d["MAXIMO_HORARIO_rellenado"] == 0))
        x["obj_horas_altas"] = d["horas_altas"] / 24
        x["obj_amplitud"] = np.log1p(d["amplitud_diaria"])
    if nivel in ("F2c", "F2d"):
        p90 = obs[d.index <= fin_train].quantile(0.90)
        x["obj_emision_proxy"] = np.log1p(obs.rolling(3, center=True, min_periods=1).mean())
        x["obj_flag_pico"] = (obs > p90).astype(float).where(obs.notna())
        x["obj_magnitud_pico"] = np.log1p((obs - p90).clip(lower=0))
    return x


def futuro_con_fuga(D, tipo, modelo="best_match"):
    """Vector del día objetivo = pronóstico meteorológico (como E9) + columnas sintéticas con fuga."""
    f_meteo, inicio = _futuro_original(D, "meteo_pron", modelo)
    x = sinteticas_objetivo(D["est"], tipo, D["fin_train"])
    tr = x[x.index <= D["fin_train"]]
    mu, sd = tr.mean(), tr.std().replace(0, 1).fillna(1)
    xs = ((x - mu) / sd)

    def f(t):
        partes = [f_meteo(t)]
        for h in mt.H:
            fila = xs.reindex([t + pd.Timedelta(days=h)]).iloc[0]
            partes.append(fila.fillna(0).to_numpy())
            partes.append([float(fila.isna().any())])
        return np.concatenate(partes).astype("float32")
    return f, inicio


mt.futuro_externo = futuro_con_fuga


def extras_fuga(est, indice):
    d = DATASET[DATASET["estacion"] == est].reindex(indice)
    x = pd.DataFrame(index=indice)
    x["act_intensidad"] = d["intensidad_operacion_FUGA"]
    x["act_actividad"] = d["actividad_industrial_FUGA"]
    for e in ESTADOS:
        x[f"act_estado_{e}"] = (d["estado_operacion_FUGA"] == e).astype(float).where(d["estado_operacion_FUGA"].notna())
    return x


resumen = []
for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    est = cfg["estacion"]
    print(f"\n===== {est}")
    carpeta = os.path.join(BASE, "modelos", est)
    ds = wc.cargar_dataset(clave)
    wf = wh.walk_forward_prophet(ds, clave, wp.params_prophet(clave))
    sel = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_hibrido_seleccionado_walkforward_{clave}.pkl"))
    sel = sel[sel["particion"].isin(["val", "test"])]
    meta = json.load(open(os.path.join(wc.CARPETA_MODELOS, f"{clave}_hibrido_v2", "metadatos.json"), encoding="utf-8"))
    D = {"clave": clave, "cfg": cfg, "ds": ds, "est": est, "tag": est,
         "fin_train": pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1),
         "fin_val": pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1), "wf": wf, "sel": sel,
         "q_movil": meta.get("cuantil_alerta_origen_movil"), "p_lstm": None, "carpeta": carpeta}
    oficial = pd.read_pickle(os.path.join(wc.RAIZ, "experimento_2", "modelos", est, "E9opt.pkl"))
    params, fuente = oficial["info"]["params"], oficial["info"]["fuente_meteo"]
    v_fuga = mt.variables_base(D, extras_fuga(est, ds.index))
    for nivel in ["F2b", "F2c", "F2d"]:
        ruta = os.path.join(carpeta, f"{nivel}.pkl")
        if os.path.exists(ruta):
            r = pd.read_pickle(ruta)
        else:
            t0 = time.time()
            wl.fijar_semillas_keras()
            pred, info = mt.correr_lstm(D, v_fuga, params, nivel, fuente)
            t, el = mt.elegir_y_aplicar(D, mt.tabla_larga(D, pred))
            t["variante"] = nivel
            r = {"pred": t, "info": {**info, "params": params, "eleccion_val": el, "fuente_meteo": fuente, "esquema": nivel}}
            pd.to_pickle(r, ruta)
            print(f"   {nivel}: {time.time() - t0:.0f} s | RMSE val por h = {[el[h]['rmse_val'] for h in mt.H]}")
        resumen.append({"estacion": est, "esquema": nivel,
                        **{f"rmse_val_h{h}": r["info"]["eleccion_val"][h]["rmse_val"] for h in mt.H},
                        **{f"w_prophet_h{h}": r["info"]["eleccion_val"][h]["w_prophet"] for h in mt.H}})
out = pd.DataFrame(resumen)
out.to_csv(os.path.join(BASE, "resultados", f"B7_validacion_fuga_{wc.FUENTE_DATOS}.csv"), sep=";", index=False, encoding="utf-8-sig")
print(out.to_string(index=False))
