# -*- coding: utf-8 -*-
"""
WayraPredict - utilidades de la LSTM (Keras / TensorFlow) compartidas por 03-LSTM,
04-HIBRIDO_PROPHET_LSTM y 05-HIPERPARAMETROS.
"""
import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")  # resultados reproducibles en CPU

import numpy as np
import pandas as pd
import tensorflow as tf
import keras
from keras import layers, ops

import wayra_comun as wc

# ------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------
VENTANA = 14                  # días de historia por muestra
LIMITE_FFILL = 3              # días máximos de relleno hacia adelante en las entradas
MIN_FRACCION_OBSERVADA = 0.5  # fracción mínima de días con contaminante en la ventana
METEOROLOGIA = ["TEMPERATURA", "HUMEDAD_RELATIVA", "VELOCIDAD_VIENTO", "PRESION_BAROMETRICA",
                "PRECIPITACION", "VIENTO_SIN", "VIENTO_COS"]
# Corrección de ceros (instrucciones_10; modelos OFICIALES): entrada "meteo_falta" (1 si falta alguna variable
# meteorológica de la estación ese día, antes de imputar). Activada por defecto; WAYRA_INDICADOR_METEO=0 la
# desactiva (solo para reproducir los modelos anteriores a la corrección, respaldados en respaldo_pre_correccion/).
INDICADOR_METEO = os.environ.get("WAYRA_INDICADOR_METEO", "1") != "0"
# Hiperparámetros por defecto (se ajustarán en 05-HIPERPARAMETROS.py)
PARAMS_LSTM = {
    "unidades": 32, "capas": 1, "dropout": 0.2, "tasa_aprendizaje": 1e-3,
    "lote": 32, "epocas_max": 300, "paciencia": 20,
}
H = max(wc.HORIZONTES)
# Híbrido v2: tasa de aprendizaje más baja y más paciencia (pedido del usuario)
PARAMS_HIBRIDO_V2 = {
    "ventana": 14, "unidades": 32, "capas": 1, "dropout": 0.2, "tasa_aprendizaje": 3e-4,
    "lote": 32, "epocas_max": 500, "paciencia": 50,
}


PARAMS_CASCADA = dict(PARAMS_HIBRIDO_V2)   # híbrido en cascada: mismo punto de partida


def params_lstm(clave: str, modelo: str = "lstm") -> dict:
    """Hiperparámetros de la LSTM sola ('lstm'), de la LSTM de residuos del híbrido v2
    ('hibrido_v2') o de la LSTM del híbrido en cascada ('cascada')."""
    defecto = {"lstm": {**PARAMS_LSTM, "ventana": VENTANA}, "hibrido_v2": PARAMS_HIBRIDO_V2,
               "hibrido_v2_intra": PARAMS_HIBRIDO_V2, "cascada": PARAMS_CASCADA}[modelo]
    return wc.hiperparametros(clave, modelo, defecto)


def fijar_semillas_keras():
    wc.fijar_semillas()
    keras.utils.set_random_seed(wc.SEMILLA)
    tf.config.experimental.enable_op_determinism()


def variables_meteo_calendario(ds: pd.DataFrame, regimen: bool) -> pd.DataFrame:
    """Meteorología del OEFA (precipitación en log1p), calendario y régimen causal."""
    v = pd.DataFrame(index=ds.index)
    for col in METEOROLOGIA:
        if col in ds:
            v[col] = np.log1p(ds[col]) if col == "PRECIPITACION" else ds[col]
    if INDICADOR_METEO:
        presentes = [c for c in METEOROLOGIA if c in ds]
        v["meteo_falta"] = ds[presentes].isna().any(axis=1).astype(float)
    if regimen:
        v["OPERACION_CAUSAL"] = ds["OPERACION_CAUSAL"]
    dia_sem = ds.index.dayofweek
    dia_anio = ds.index.dayofyear
    v["sem_sin"], v["sem_cos"] = np.sin(2 * np.pi * dia_sem / 7), np.cos(2 * np.pi * dia_sem / 7)
    v["anio_sin"] = np.sin(2 * np.pi * dia_anio / 365.25)
    v["anio_cos"] = np.cos(2 * np.pi * dia_anio / 365.25)
    return v


def escalador_train(v: pd.DataFrame, fin_train: pd.Timestamp) -> dict:
    tr = v.loc[:fin_train]
    return {"media": tr.mean().to_dict(), "desv": tr.std().replace(0, 1).fillna(1).to_dict()}


def imputar_escalar(v: pd.DataFrame, esc: dict, no_rellenar=("y_falta",)) -> pd.DataFrame:
    """Relleno hacia adelante (solo pasado, hasta LIMITE_FFILL días), luego media de train;
    estandarización con media/desv. de train."""
    media, desv = pd.Series(esc["media"]), pd.Series(esc["desv"])
    relleno = v.ffill(limit=LIMITE_FFILL).fillna(media)
    for c in no_rellenar:
        if c in v:
            relleno[c] = v[c]
    return (relleno[media.index] - media) / desv


@keras.saving.register_keras_serializable(package="wayra")
def mse_enmascarado(y_true, y_pred):
    """MSE que ignora los objetivos sin dato (NaN)."""
    mascara = ops.logical_not(ops.isnan(y_true))
    y_true = ops.where(mascara, y_true, 0.0)
    error = ops.where(mascara, ops.square(y_true - y_pred), 0.0)
    return ops.sum(error) / ops.maximum(ops.sum(ops.cast(mascara, "float32")), 1.0)


def crear_lstm(n_variables: int, p: dict = PARAMS_LSTM, ventana: int = VENTANA,
               n_futuro: int = 0) -> keras.Model:
    """LSTM multi-horizonte (una salida por horizonte). Si n_futuro > 0 se agrega una segunda
    entrada con variables de los días objetivo (escenario de meteorología ideal), que se
    concatena a la salida de la LSTM antes de la capa densa."""
    entrada = keras.Input(shape=(ventana, n_variables), name="historia")
    x = entrada
    for k in range(p["capas"]):
        x = layers.LSTM(p["unidades"], return_sequences=k < p["capas"] - 1)(x)
        x = layers.Dropout(p["dropout"])(x)
    entradas = [entrada]
    if n_futuro:
        futuro = keras.Input(shape=(n_futuro,), name="futuro")
        x = layers.Concatenate()([x, futuro])
        entradas.append(futuro)
    salida = layers.Dense(H)(x)
    modelo = keras.Model(entradas if n_futuro else entrada, salida)
    modelo.compile(optimizer=keras.optimizers.Adam(p["tasa_aprendizaje"]), loss=mse_enmascarado)
    return modelo


def entrenar_A_B(X_tr, Y_tr, X_val, Y_val, X_trval, Y_trval, n_variables: int,
                 p: dict = PARAMS_LSTM, n_futuro: int = 0):
    """Modelo A: train con parada temprana en val. Modelo B: train+val durante las épocas
    óptimas de A. X_* puede ser un arreglo o una lista [historia, futuro]."""
    ventana = int(p.get("ventana", VENTANA))
    keras.utils.set_random_seed(wc.SEMILLA)
    mA = crear_lstm(n_variables, p, ventana=ventana, n_futuro=n_futuro)
    parada = keras.callbacks.EarlyStopping(monitor="val_loss", patience=p["paciencia"],
                                           restore_best_weights=True)
    hist = mA.fit(X_tr, Y_tr, validation_data=(X_val, Y_val), epochs=p["epocas_max"],
                  batch_size=p["lote"], callbacks=[parada], verbose=0, shuffle=True)
    epocas = int(np.argmin(hist.history["val_loss"])) + 1
    if X_trval is None:  # solo modelo A (búsqueda de hiperparámetros)
        return mA, None, hist.history, epocas
    keras.utils.set_random_seed(wc.SEMILLA)
    mB = crear_lstm(n_variables, p, ventana=ventana, n_futuro=n_futuro)
    mB.fit(X_trval, Y_trval, epochs=epocas, batch_size=p["lote"], verbose=0, shuffle=True)
    return mA, mB, hist.history, epocas
