# -*- coding: utf-8 -*-
"""
WayraPredict - utilidades de Prophet compartidas por 02-PROPHET, 04-HIBRIDO y 05-HIPERPARAMETROS.

- Escala del modelo: log(1 + x) (ver wayra_comun).
- En series con régimen (CA-CC-01) se agrega OPERACION como regresor aditivo. Se AJUSTA con la
  OPERACION del propio día (centrada) y, al PRONOSTICAR, se usa el último estado conocido en el
  origen (OPERACION_CAUSAL), supuesto constante durante el horizonte.
"""
import logging

import numpy as np
import pandas as pd
from prophet import Prophet

import wayra_comun as wc

logging.getLogger("cmdstanpy").disabled = True  # silencia "Chain [1] start/done processing"
logging.getLogger("prophet").setLevel(logging.WARNING)

# ------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------
REENTRENAR_CADA = 7           # días entre reentrenamientos en el walk-forward
INTERVALO = 0.80              # nivel del intervalo de incertidumbre
MUESTRAS_INCERTIDUMBRE = 1000
# Hiperparámetros por defecto (se ajustarán en 05-HIPERPARAMETROS.py)
PARAMS_PROPHET = {
    "changepoint_prior_scale": 0.05,
    "seasonality_prior_scale": 10.0,
    "seasonality_mode": "additive",
}


def crear_prophet(regimen: bool, params: dict = PARAMS_PROPHET) -> Prophet:
    m = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False,
                interval_width=INTERVALO, uncertainty_samples=MUESTRAS_INCERTIDUMBRE, **params)
    if regimen:
        m.add_regressor("OPERACION", mode="additive")
    return m


def datos_ajuste(ds: pd.DataFrame, hasta: pd.Timestamp, regimen: bool) -> pd.DataFrame:
    """Tabla ds/y (y en log(1+x)) con los días <= hasta que tienen dato."""
    d = ds.loc[:hasta]
    df = pd.DataFrame({"ds": d.index, "y": wc.a_escala_modelo(d["OBJETIVO"]).to_numpy()})
    if regimen:
        df["OPERACION"] = d["OPERACION"].to_numpy()
    return df.dropna().reset_index(drop=True)


def ajustar_prophet(ds, hasta, regimen, params=PARAMS_PROPHET) -> Prophet:
    np.random.seed(wc.SEMILLA)
    m = crear_prophet(regimen, params)
    m.fit(datos_ajuste(ds, hasta, regimen))
    return m


def params_prophet(clave: str) -> dict:
    """Hiperparámetros de Prophet para la serie (05-HIPERPARAMETROS.py o por defecto)."""
    return wc.hiperparametros(clave, "prophet", PARAMS_PROPHET)


def predecir(m: Prophet, fechas, operacion=None, con_intervalo: bool = True) -> pd.DataFrame:
    """Predicción con componentes. con_intervalo=False omite el muestreo de incertidumbre
    (más rápido; sin yhat_lower / yhat_upper)."""
    futuro = pd.DataFrame({"ds": pd.DatetimeIndex(fechas)})
    if operacion is not None:
        futuro["OPERACION"] = operacion
    np.random.seed(wc.SEMILLA)
    if con_intervalo:
        return m.predict(futuro).set_index("ds")
    muestras = m.uncertainty_samples
    m.uncertainty_samples = 0
    try:
        return m.predict(futuro).set_index("ds")
    finally:
        m.uncertainty_samples = muestras


def yhat_puntual(m: Prophet, fechas, operacion=None) -> pd.Series:
    """Solo yhat (sin muestreo de incertidumbre): rápido, para residuos."""
    muestras = m.uncertainty_samples
    m.uncertainty_samples = 0
    try:
        futuro = pd.DataFrame({"ds": pd.DatetimeIndex(fechas)})
        if operacion is not None:
            futuro["OPERACION"] = operacion
        return m.predict(futuro).set_index("ds")["yhat"]
    finally:
        m.uncertainty_samples = muestras


def factor_duan_modelo(m: Prophet) -> float:
    """Factor de Duan con los residuos del propio ajuste (solo datos <= fin del ajuste)."""
    reg = [c for c in m.extra_regressors]
    hist = m.history
    yhat = yhat_puntual(m, hist["ds"], hist["OPERACION"].to_numpy() if reg else None).to_numpy()
    return wc.factor_duan(hist["y"].to_numpy() - yhat)
