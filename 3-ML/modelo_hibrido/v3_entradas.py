"""Entradas de la LSTM de la versión 3 (compartido por A09 y A12).

- extras(est, indice): variables de actividad de la fuente en la ventana de entrada.
- futuro(D, esquema, fuente_meteo, futuro_original): vector de cada horizonte.
  - F2c: meteorología pronosticada + actividad del día objetivo.
  - F2c_cas: lo mismo + pronóstico walk-forward de Prophet para ese origen y horizonte (yhat, tendencia,
    estacionalidad semanal y anual).
Debe ser idéntico a A04 (F2c) y A11 (F2c_cas).
"""
import os

import numpy as np
import pandas as pd

import wayra_comun as wc

BASE = os.path.join(wc.RAIZ, "modelo_hibrido")
DATASET = pd.read_pickle(os.path.join(BASE, "datos", "dataset_combinado_enriquecido.pkl"))
ESTADOS = ["A", "I", "T", "D"]
H = wc.HORIZONTES
NH = len(H)


def sinteticas_objetivo(est, fin_train):
    d = DATASET[DATASET["estacion"] == est]
    obs = d["OBJETIVO"].where(d["relleno_tipo"].isin(["observado", "estacion_vecina"]))
    x = pd.DataFrame(index=d.index)
    x["obj_intensidad"] = d["intensidad_operacion_FUGA"]
    x["obj_actividad"] = d["actividad_industrial_FUGA"]
    for e in ESTADOS:
        x[f"obj_estado_{e}"] = (d["estado_operacion_FUGA"] == e).astype(float)
    p90 = obs[d.index <= fin_train].quantile(0.90)
    x["obj_emision_proxy"] = np.log1p(obs.rolling(3, center=True, min_periods=1).mean())
    x["obj_flag_pico"] = (obs > p90).astype(float).where(obs.notna())
    x["obj_magnitud_pico"] = np.log1p((obs - p90).clip(lower=0))
    return x


def extras(est, indice):
    d = DATASET[DATASET["estacion"] == est].reindex(indice)
    x = pd.DataFrame(index=indice)
    x["act_intensidad"] = d["intensidad_operacion_FUGA"]
    x["act_actividad"] = d["actividad_industrial_FUGA"]
    for e in ESTADOS:
        x[f"act_estado_{e}"] = (d["estado_operacion_FUGA"] == e).astype(float).where(d["estado_operacion_FUGA"].notna())
    return x


def futuro(D, esquema, fuente_meteo, futuro_original):
    f_meteo, inicio = futuro_original(D, "meteo_pron", fuente_meteo)
    x = sinteticas_objetivo(D["est"], D["fin_train"])
    tr = x[x.index <= D["fin_train"]]
    xs = (x - tr.mean()) / tr.std().replace(0, 1).fillna(1)
    cascada = esquema == "F2c_cas"
    if cascada:
        cp = ["yhat", "trend", "weekly", "yearly"]
        wf = D["wf"].set_index(["origen", "horizonte"])[cp]
        ref = wf[wf.index.get_level_values("origen") + pd.Timedelta(days=NH) <= D["fin_train"]]
        wfs = (wf - ref.mean()) / ref.std().replace(0, 1).fillna(1)

    def f(t):
        partes = [f_meteo(t)]
        for h in H:
            fila = xs.reindex([t + pd.Timedelta(days=h)]).iloc[0]
            partes.append(fila.fillna(0).to_numpy())
            partes.append([float(fila.isna().any())])
            if cascada:
                pr = wfs.loc[(t, h)] if (t, h) in wfs.index else pd.Series(np.nan, index=cp)
                partes.append(pr.fillna(0).to_numpy())
                partes.append([float(pr.isna().any())])
        return np.concatenate(partes).astype("float32")
    return f, inicio
