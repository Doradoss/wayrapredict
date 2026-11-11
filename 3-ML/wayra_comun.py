# -*- coding: utf-8 -*-
"""
WayraPredict - módulo compartido de la parte de Machine Learning.

Contiene la configuración común a los scripts 02 a 07 (rutas, umbrales normativos,
series a modelar y sus cortes cronológicos), la carga de los datasets diarios que
genera 01-EDA-CALIDAD_AIRE_v3.py, la clasificación INCA, las métricas y utilidades
de reproducibilidad.

Uso (Spyder o Colab), con la carpeta del proyecto como directorio de trabajo:
    import wayra_comun as wc
"""
import json
import os
import platform
import random
from importlib import metadata

import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# RUTAS (relativas a la carpeta del proyecto; en Colab cambiar RAIZ)
# ------------------------------------------------------------------
RAIZ = os.environ.get("WAYRA_RAIZ", ".")

# ------------------------------------------------------------------
# FUENTE DE DATOS
# ------------------------------------------------------------------
# - "original":        dataset del OEFA (1A.csv), salida de 01-EDA-CALIDAD_AIRE_v3.py
# - "alta_resolucion": datos de 5 minutos del proveedor (01b-EDA-ALTA-RESOLUCION.py), sufijo _v2
# - "combinada":       OEFA hasta 2019 + alta resolución desde 2020, sufijo _combinada.
#                      DATASET OFICIAL de La Oroya; cortes nuevos (A): modelo final.
# - "combinada_comprobacion": misma serie _combinada con los cortes del dataset original y
#                      recortada a dic 2021 (B): solo para comprobar que el cambio de fuente no
#                      altera los resultados.
# Se elige aquí o con la variable de entorno WAYRA_FUENTE. Con "original" todo queda igual que
# antes; con las otras fuentes los resultados de 02-04 van a subcarpetas propias
# (checkpoints/fuente_<fuente>/, figuras/fuente_<fuente>/, modelos/fuente_<fuente>/).
FUENTE_DATOS = os.environ.get("WAYRA_FUENTE", "original")
SUFIJO_FUENTE = {"original": "", "alta_resolucion": "_v2", "combinada": "_combinada",
                 "combinada_comprobacion": "_combinada",
                 # Pasco (CA-COLQ-01) y Moquegua (CA-TAL-01): datos de alta resolución (00d), solo PM10
                 "pasco_moquegua": "_ar"}
if FUENTE_DATOS not in SUFIJO_FUENTE:
    raise ValueError(f"FUENTE_DATOS desconocida: {FUENTE_DATOS}. Opciones: {list(SUFIJO_FUENTE)}")

CARPETA_DATOS = os.path.join(RAIZ, "checkpoints")   # datasets diarios de todas las fuentes
_sub = "" if FUENTE_DATOS == "original" else f"fuente_{FUENTE_DATOS}"
CARPETA_CHECKPOINTS = os.path.join(CARPETA_DATOS, _sub)
CARPETA_FIGURAS = os.path.join(RAIZ, "figuras", _sub)
CARPETA_MODELOS = os.path.join(RAIZ, "modelos", _sub)
for _c in (CARPETA_DATOS, CARPETA_CHECKPOINTS, CARPETA_FIGURAS, CARPETA_MODELOS):
    os.makedirs(_c, exist_ok=True)

SEMILLA = 42

# ------------------------------------------------------------------
# UMBRALES NORMATIVOS (µg/m³, 24 h)
# ------------------------------------------------------------------
ECA_24H = {"PM2.5": 50, "PM10": 100, "DIOXIDO_AZUFRE": 250}   # D.S. 003-2017-MINAM
OMS_24H = {"PM2.5": 15, "PM10": 45, "DIOXIDO_AZUFRE": 40}     # Guías OMS 2021
# VUEC: PENDIENTE DE VERIFICAR en la norma (marcadores; el de SO2 es para promedio móvil de 3 h)
VUEC = {"PM10": 250, "DIOXIDO_AZUFRE": 500}
CATEGORIAS_INCA = ["Buena", "Moderada", "Mala", "Umbral de cuidado"]
COLORES_INCA = {"Buena": "#2E9E44", "Moderada": "#F2C12E",
                "Mala": "#F28C28", "Umbral de cuidado": "#D7263D"}

# Rótulos
NOMBRE_VAR = {"DIOXIDO_AZUFRE": "SO$_2$", "PM10": "PM$_{10}$", "PM2.5": "PM$_{2.5}$"}
CODIGO_CONTAMINANTE = {"DIOXIDO_AZUFRE": "SO2", "PM10": "PM10", "PM2.5": "PM2.5"}  # tabla prediccion
NOMBRE_DEP = {"JUNIN": "Junín", "PASCO": "Pasco", "MOQUEGUA": "Moquegua"}
UNIDAD = "µg/m³"
COLORES_MODELO = {"Persistencia": "#A5A5A5", "Prophet": "#F4B183", "Prophet+Duan": "#C55A11",
                  "LSTM": "#9DC3E6", "LSTM+Duan": "#2F5597",
                  "Híbrido": "#A9D18E", "Híbrido+Duan": "#548235",
                  "Híbrido ideal": "#FFD966", "Híbrido ideal+Duan": "#BF9000",
                  "Híbrido v1": "#A9D18E", "Híbrido v1+Duan": "#548235",
                  "Híbrido v2": "#C9A0DC", "Híbrido v2+Duan": "#7030A0"}

# Régimen de operación de la fuente (confirmado con el histograma fig02)
UMBRAL_OPERACION = 40
VENTANA_OPERACION = 7

# ------------------------------------------------------------------
# SERIES A MODELAR Y CORTES CRONOLÓGICOS (fechas inclusivas)
# ------------------------------------------------------------------
# train: < inicio de val | val: [val, test) | test: [test, fin_test] | extra: > fin_test
# En CA-CC-01 la prueba cae en un período con la fuente operando; el tramo posterior
# (fuente detenida) se reporta aparte como "extra".
SERIES_ORIGINAL = {
    "CA-CC-01_DIOXIDO_AZUFRE": {
        "departamento": "JUNIN", "estacion": "CA-CC-01", "contaminante": "DIOXIDO_AZUFRE",
        "inicio_val": "2020-01-01", "inicio_test": "2020-10-01", "fin_test": "2021-03-31",
        "regimen": True,
    },
    "CA-SB-01_PM10": {
        "departamento": "PASCO", "estacion": "CA-SB-01", "contaminante": "PM10",
        "inicio_val": "2020-07-01", "inicio_test": "2021-01-01", "fin_test": "2021-12-31",
        "regimen": False,
    },
    "CA-TO-01_PM10": {
        "departamento": "MOQUEGUA", "estacion": "CA-TO-01", "contaminante": "PM10",
        "inicio_val": "2020-01-01", "inicio_test": "2020-07-01", "fin_test": "2021-01-29",
        "regimen": False,
    },
}
# Fuentes nuevas: por ahora solo CA-CC-01 (confirmado con el usuario, Paso 4 de
# TAREA_DATOS_NUEVOS.md). "fin_datos" (opcional) recorta la serie antes de modelar.
_CC01 = SERIES_ORIGINAL["CA-CC-01_DIOXIDO_AZUFRE"]
_CORTES_PENDIENTES = {"inicio_val": None, "inicio_test": None, "fin_test": None}
SERIES_POR_FUENTE = {
    "original": SERIES_ORIGINAL,
    # _v2 sin cortes: no se modela (el usuario pidió no correr A con _v2)
    "alta_resolucion": {"CA-CC-01_DIOXIDO_AZUFRE": {**_CC01, **_CORTES_PENDIENTES}},
    # A: modelo final. train 2018 -> dic 2024, val ene -> ago 2025, test sep 2025 -> jun 2026
    "combinada": {"CA-CC-01_DIOXIDO_AZUFRE": {
        **_CC01, "inicio_val": "2025-01-01", "inicio_test": "2025-09-01", "fin_test": "2026-06-30"}},
    # B: comprobación con los mismos cortes que el original y la serie recortada a dic 2021
    "combinada_comprobacion": {"CA-CC-01_DIOXIDO_AZUFRE": {**_CC01, "fin_datos": "2021-12-31"}},
    # Pasco y Moquegua (confirmado por el usuario): misma separación que La Oroya (cortes A).
    # CA-TAL-01 une TAL-01 y TAL-02 (reubicación del equipo el 11/07/2025; columna REUBICACION).
    # Estaciones finales (instrucciones_4.md): Pasco = CA-HUAR-01 combinada (Huaraucaca + días sin
    # dato rellenados con CA-COLQ-01 ajustada; columna RELLENO; 00f) y Moquegua = CA-ILO-02
    # (Ilo-Pacocha, datos propios sin relleno, desde jun 2022; 00h). CA-TAL-01 descartada
    # (reubicación entre train y test; C1 incumplido). LSTM global: CA-CC-01 + estas dos.
    # - "inicio_datos": recorta el inicio de la serie.
    # - "extender_dias": agrega días vacíos al final para pronosticar desde el último día con datos
    #   (no cambia ajustes ni métricas: esos días no tienen observado).
    # - "intervalo_completo": el walk-forward completo de Prophet calcula el intervalo también en
    #   train (calibración de alertas con origen móvil).
    "pasco_moquegua": {
        "CA-HUAR-01_PM10": {"departamento": "PASCO", "estacion": "CA-HUAR-01", "contaminante": "PM10",
                            "inicio_val": "2025-01-01", "inicio_test": "2025-09-01", "fin_test": "2026-06-30",
                            "regimen": False, "relleno": "CA-COLQ-01", "extender_dias": 3,
                            "intervalo_completo": True},
        "CA-ILO-02_PM10": {"departamento": "MOQUEGUA", "estacion": "CA-ILO-02", "contaminante": "PM10",
                           "inicio_val": "2025-01-01", "inicio_test": "2025-09-01", "fin_test": "2026-06-30",
                           "regimen": False, "inicio_datos": "2022-06-01", "extender_dias": 3,
                           "intervalo_completo": True},
    },
}
# Serie de La Oroya en la LSTM global (fuente oficial "combinada", cortes A)
SERIES_GLOBAL = {"CA-CC-01_DIOXIDO_AZUFRE": "combinada", "CA-HUAR-01_PM10": "pasco_moquegua",
                 "CA-ILO-02_PM10": "pasco_moquegua"}
SERIES = SERIES_POR_FUENTE[FUENTE_DATOS]
PARTICIONES = ["train", "val", "test", "extra"]

# Horizonte de predicción en días (empezar con 1-3; ampliar a 5 según las métricas)
HORIZONTES = [1, 2, 3]

# Columnas de la tabla `prediccion` de la base de datos
COLUMNAS_PREDICCION_BD = ["estacion", "contaminante", "fecha_objetivo", "valor",
                          "limite_inferior", "limite_superior", "categoria_inca"]


# ------------------------------------------------------------------
# REPRODUCIBILIDAD
# ------------------------------------------------------------------
def fijar_semillas(semilla: int = SEMILLA):
    """Fija las semillas de random, numpy y (si está instalado) TensorFlow."""
    random.seed(semilla)
    np.random.seed(semilla)
    os.environ["PYTHONHASHSEED"] = str(semilla)
    try:
        import tensorflow as tf
        tf.random.set_seed(semilla)
    except ImportError:
        pass


def versiones_librerias() -> dict:
    libs = ["numpy", "pandas", "prophet", "cmdstanpy", "statsmodels", "matplotlib",
            "seaborn", "tensorflow", "keras", "optuna", "scikit-learn"]
    v = {"python": platform.python_version(), "sistema": platform.platform()}
    for lib in libs:
        try:
            v[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:
            pass
    return v


def guardar_json(obj, ruta: str):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def ruta_hiperparametros(clave: str) -> str:
    return os.path.join(CARPETA_CHECKPOINTS, f"05_hiperparametros_{clave}.json")


def hiperparametros(clave: str, modelo: str, por_defecto: dict) -> dict:
    """Hiperparámetros elegidos en 05-HIPERPARAMETROS.py (solo con validación) para la fuente
    activa; si no existen, los valores por defecto. modelo: 'prophet', 'lstm' o 'hibrido_v2'.
    Con WAYRA_HIPERPARAMETROS=defecto se ignoran (para reproducir la versión anterior)."""
    ruta = ruta_hiperparametros(clave)
    if os.environ.get("WAYRA_HIPERPARAMETROS") == "defecto" or not os.path.exists(ruta):
        return dict(por_defecto)
    with open(ruta, encoding="utf-8") as f:
        elegidos = json.load(f).get(modelo, {})
    return {**por_defecto, **elegidos}


# ------------------------------------------------------------------
# CARGA DE DATOS Y PARTICIÓN
# ------------------------------------------------------------------
def cargar_dataset(clave: str, fuente: str = None) -> pd.DataFrame:
    """Dataset diario de una serie (salida de 01-EDA o 01b-EDA) de la fuente elegida, con la
    columna PARTICION."""
    fuente = fuente or FUENTE_DATOS
    ds = pd.read_pickle(os.path.join(CARPETA_DATOS, f"03_dataset_{clave}{SUFIJO_FUENTE[fuente]}.pkl"))
    cfg = SERIES_POR_FUENTE[fuente][clave]
    if cfg.get("fin_datos"):
        ds = ds.loc[:cfg["fin_datos"]]
    if cfg.get("inicio_datos"):
        ds = ds.loc[cfg["inicio_datos"]:]
        ds = ds.loc[ds["OBJETIVO"].first_valid_index():]
    ds = ds.loc[:ds["OBJETIVO"].last_valid_index()] if cfg.get("extender_dias") else ds
    ds = ds.asfreq("D")
    if cfg.get("extender_dias"):
        futuro = pd.date_range(ds.index.max() + pd.Timedelta(days=1), periods=cfg["extender_dias"], freq="D")
        ds = ds.reindex(ds.index.append(futuro))
        ds.index.name = "FECHA"
        ds["DIA_SEMANA"], ds["MES"] = ds.index.dayofweek, ds.index.month
    ds["PARTICION"] = asignar_particion(ds.index, clave, fuente)
    return ds


def asignar_particion(fechas: pd.DatetimeIndex, clave: str, fuente: str = None) -> pd.Series:
    cfg = SERIES_POR_FUENTE[fuente or FUENTE_DATOS][clave]
    if cfg["inicio_val"] is None:
        raise ValueError(f"Cortes de {clave} para la fuente '{fuente or FUENTE_DATOS}' pendientes de "
                         "confirmar (Paso 4 de TAREA_DATOS_NUEVOS.md).")
    val, test, fin = (pd.Timestamp(cfg[k]) for k in ("inicio_val", "inicio_test", "fin_test"))
    part = np.select([fechas < val, fechas < test, fechas <= fin], ["train", "val", "test"], "extra")
    return pd.Series(part, index=fechas, name="PARTICION")


def resumen_particiones(ds: pd.DataFrame) -> pd.DataFrame:
    """Días, días con dato y distribución INCA por partición (para verificar los cortes)."""
    g = ds.groupby("PARTICION", sort=False)
    t = pd.DataFrame({
        "desde": g.apply(lambda d: d.index.min().date()),
        "hasta": g.apply(lambda d: d.index.max().date()),
        "dias": g.size(),
        "dias_con_dato": g["OBJETIVO"].count(),
        "% Moderada o peor": g["INCA"].apply(lambda s: (s.dropna() > 50).mean() * 100).round(1),
        "días > ECA": g["SUPERA_ECA"].apply(lambda s: int(s.dropna().astype(bool).sum())),
    })
    if "OPERACION" in ds:
        t["% días operando"] = g["OPERACION"].apply(lambda s: s.dropna().mean() * 100).round(1)
    return t.reindex([p for p in PARTICIONES if p in t.index])


# ------------------------------------------------------------------
# ESCALA DEL MODELO: log(1 + x)
# ------------------------------------------------------------------
def a_escala_modelo(x):
    return np.log1p(x)


def a_escala_original(z):
    return np.expm1(z)


def factor_duan(residuos_log) -> float:
    """Factor de 'smearing' de Duan (1983): media de exp(residuo) en los datos de ajuste.
    Corrige el sesgo de volver de log a µg/m³ (expm1 de la media del log = mediana,
    que subestima la media)."""
    r = np.asarray(residuos_log, float)
    r = r[~np.isnan(r)]
    return float(np.exp(r).mean()) if len(r) else 1.0


def a_escala_original_duan(z, factor: float):
    """x = exp(z) * factor - 1, con z = log(1 + x) predicho. Solo para el valor puntual:
    los límites del intervalo son cuantiles y se transforman con expm1 sin corrección."""
    return np.exp(z) * factor - 1


# ------------------------------------------------------------------
# INCA
# ------------------------------------------------------------------
def valor_inca(valor, contaminante: str):
    return np.asarray(valor, dtype=float) * 100 / ECA_24H[contaminante]


def categoria_inca(valor, contaminante: str) -> pd.Series:
    """INCA = concentración / ECA x 100. Buena 0-50, Moderada 51-100, Mala 101-VUEC,
    Umbral de cuidado > VUEC (R.M. 181-2016-MINAM)."""
    inca = pd.Series(valor_inca(valor, contaminante),
                     index=valor.index if isinstance(valor, pd.Series) else None)
    if contaminante in VUEC:
        tope = VUEC[contaminante] * 100 / ECA_24H[contaminante]
        cortes, etiquetas = [-np.inf, 50, 100, tope, np.inf], CATEGORIAS_INCA
    else:
        cortes, etiquetas = [-np.inf, 50, 100, np.inf], CATEGORIAS_INCA[:3]
    cat = pd.cut(inca, cortes, labels=etiquetas).astype(object)
    return cat.where(inca.notna(), None)


# ------------------------------------------------------------------
# MÉTRICAS
# ------------------------------------------------------------------
def metricas_regresion(y, yhat) -> dict:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = ~np.isnan(y) & ~np.isnan(yhat)
    y, yhat = y[m], yhat[m]
    if len(y) == 0:
        return {"n": 0, "RMSE": np.nan, "MAE": np.nan, "R2": np.nan}
    err = yhat - y
    ss_tot = ((y - y.mean()) ** 2).sum()
    return {"n": int(len(y)),
            "RMSE": float(np.sqrt((err ** 2).mean())),
            "MAE": float(np.abs(err).mean()),
            "R2": float(1 - (err ** 2).sum() / ss_tot) if ss_tot > 0 else np.nan}


def _binaria(real: np.ndarray, pred: np.ndarray, prefijo: str) -> dict:
    vp = int((real & pred).sum())
    fn = int((real & ~pred).sum())
    fp = int((~real & pred).sum())
    return {f"{prefijo}_casos": int(real.sum()),
            f"{prefijo}_recall": vp / (vp + fn) if vp + fn else np.nan,
            f"{prefijo}_precision": vp / (vp + fp) if vp + fp else np.nan,
            f"{prefijo}_falsas_alarmas": fp}


def metricas_inca(y, yhat, contaminante: str) -> dict:
    """Acierto global de la categoría INCA, recall por categoría y detección de
    días 'Moderada o peor' (INCA > 50) y de superación del ECA (INCA > 100)."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = ~np.isnan(y) & ~np.isnan(yhat)
    y, yhat = y[m], yhat[m]
    cr = categoria_inca(pd.Series(y), contaminante)
    cp = categoria_inca(pd.Series(yhat), contaminante)
    res = {"acierto_categoria": float((cr == cp).mean()) if len(y) else np.nan}
    for c in CATEGORIAS_INCA[:3]:
        sel = cr == c
        res[f"recall_{c}"] = float((cp[sel] == c).mean()) if sel.any() else np.nan
    ir, ip = valor_inca(y, contaminante), valor_inca(yhat, contaminante)
    res.update(_binaria(ir > 50, ip > 50, "moderada_o_peor"))
    res.update(_binaria(ir > 100, ip > 100, "supera_eca"))
    return res


def matriz_confusion_inca(y, yhat, contaminante: str) -> pd.DataFrame:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = ~np.isnan(y) & ~np.isnan(yhat)
    cr = categoria_inca(pd.Series(y[m]), contaminante).rename("Observada")
    cp = categoria_inca(pd.Series(yhat[m]), contaminante).rename("Predicha")
    cats = CATEGORIAS_INCA if contaminante in VUEC else CATEGORIAS_INCA[:3]
    return pd.crosstab(cr, cp).reindex(index=cats, columns=cats, fill_value=0)


def cobertura_intervalo(y, inferior, superior) -> float:
    y, lo, hi = (np.asarray(a, float) for a in (y, inferior, superior))
    m = ~np.isnan(y) & ~np.isnan(lo) & ~np.isnan(hi)
    return float(((y[m] >= lo[m]) & (y[m] <= hi[m])).mean()) if m.any() else np.nan


def tabla_metricas(pred: pd.DataFrame, contaminante: str,
                   col_obs="observado", col_pred="valor", por=("particion", "horizonte")) -> pd.DataFrame:
    """Métricas de regresión + INCA agrupadas (por defecto por partición y horizonte)."""
    filas = []
    for llave, g in pred.groupby(list(por), sort=False):
        fila = dict(zip(por, llave if isinstance(llave, tuple) else (llave,)))
        fila.update(metricas_regresion(g[col_obs], g[col_pred]))
        fila.update(metricas_inca(g[col_obs], g[col_pred], contaminante))
        if {"limite_inferior", "limite_superior"} <= set(g.columns):
            fila["cobertura_intervalo"] = cobertura_intervalo(g[col_obs], g["limite_inferior"],
                                                              g["limite_superior"])
        filas.append(fila)
    return pd.DataFrame(filas)


# ------------------------------------------------------------------
# REGLAS DE ALERTA
# ------------------------------------------------------------------
# Umbrales de alerta como fracción del ECA: INCA > 50 (Moderada o peor) e INCA > 100 (> ECA)
UMBRALES_ALERTA = {"moderada_o_peor": 0.5, "supera_eca": 1.0}


def f_beta(precision, recall, beta=2.0) -> float:
    """F-beta (beta = 2 prioriza el recall). Sin alertas o sin aciertos -> 0."""
    if not (precision > 0 and recall > 0):
        return 0.0
    b2 = beta ** 2
    return (1 + b2) * precision * recall / (b2 * precision + recall)


def tabla_alertas(pred: pd.DataFrame, contaminante: str, modelo: str,
                  col_obs="observado", col_pred="valor", col_sup="limite_superior",
                  por=("particion", "horizonte")) -> pd.DataFrame:
    """Recall y precisión de dos reglas de alerta para cada umbral:
    - 'puntual': alerta si el valor predicho supera el umbral;
    - 'intervalo': alerta si el límite superior del intervalo supera el umbral
      (solo si el modelo tiene intervalo)."""
    reglas = {"puntual": col_pred}
    if col_sup in pred.columns and pred[col_sup].notna().any():
        reglas["intervalo"] = col_sup
    # Límite superior con el nivel calibrado en validación (máximo F2), si existe
    if "limite_alerta" in pred.columns and pred["limite_alerta"].notna().any():
        reglas["intervalo calibrado"] = "limite_alerta"
    # Pasco y Moquegua: cuantil calibrado con origen móvil (todos los pronósticos fuera de muestra
    # anteriores a la prueba, no solo la validación)
    if "limite_alerta_movil" in pred.columns and pred["limite_alerta_movil"].notna().any():
        reglas["intervalo calibrado (origen móvil)"] = "limite_alerta_movil"
    filas = []
    for llave, g in pred.groupby(list(por), sort=False):
        g = g[g[col_obs].notna()]
        base = dict(zip(por, llave if isinstance(llave, tuple) else (llave,)))
        for umbral, frac in UMBRALES_ALERTA.items():
            limite = frac * ECA_24H[contaminante]
            real = (g[col_obs] > limite).to_numpy()
            for regla, col in reglas.items():
                alerta = (g[col] > limite).to_numpy()
                vp = int((real & alerta).sum())
                rec = vp / real.sum() if real.sum() else np.nan
                prec = vp / alerta.sum() if alerta.sum() else np.nan
                filas.append({**base, "modelo": modelo, "umbral": umbral, "regla": regla,
                              "dias": len(g), "dias_reales": int(real.sum()),
                              "alertas": int(alerta.sum()), "aciertos": vp,
                              "falsas_alarmas": int((~real & alerta).sum()),
                              "recall": rec, "precision": prec, "F2": f_beta(prec, rec, 2),
                              "pct_dias_con_alerta": alerta.mean() * 100 if len(g) else np.nan})
    return pd.DataFrame(filas)


def filtrar_comunes(modelos: dict) -> dict:
    """Deja en cada tabla de predicciones solo los pares (origen, horizonte) que tienen
    predicción en TODOS los modelos, para comparar sobre los mismos días."""
    llaves = None
    for df in modelos.values():
        k = set(map(tuple, df.loc[df["valor"].notna(), ["origen", "horizonte"]].to_numpy()))
        llaves = k if llaves is None else llaves & k
    salida = {}
    for nombre, df in modelos.items():
        idx = pd.MultiIndex.from_frame(df[["origen", "horizonte"]])
        salida[nombre] = df[idx.isin(list(llaves))].copy()
    return salida


# ------------------------------------------------------------------
# MODELO BASE: PERSISTENCIA
# ------------------------------------------------------------------
def prediccion_persistencia(serie: pd.Series, origenes, horizontes=HORIZONTES) -> pd.DataFrame:
    """Predice el valor de t+h con el último valor observado hasta el origen t."""
    ultimo = serie.ffill()
    filas = []
    for t in origenes:
        for h in horizontes:
            f = t + pd.Timedelta(days=h)
            filas.append({"origen": t, "horizonte": h, "fecha_objetivo": f,
                          "valor": ultimo.get(t, np.nan), "observado": serie.get(f, np.nan)})
    return pd.DataFrame(filas)


def predicciones_base(clave: str, ds: pd.DataFrame = None) -> dict:
    """Persistencia, Prophet y Prophet+Duan sobre los orígenes del walk-forward de 02-PROPHET
    (lee checkpoints/04_prophet_walkforward_<clave>.pkl)."""
    ds = cargar_dataset(clave) if ds is None else ds
    wf = pd.read_pickle(os.path.join(CARPETA_CHECKPOINTS, f"04_prophet_walkforward_{clave}.pkl"))
    base = ["origen", "horizonte", "fecha_objetivo", "particion", "observado"]
    prophet = wf[base + ["valor", "limite_inferior", "limite_superior"]].copy()
    # El intervalo es el mismo con y sin Duan (sus límites son cuantiles): se reporta una
    # sola vez, como "Prophet (intervalo)".
    duan = wf[base].assign(valor=wf["valor_duan"])
    pers = prediccion_persistencia(ds["OBJETIVO"], sorted(wf["origen"].unique()),
                                   sorted(wf["horizonte"].unique()))
    pers["particion"] = asignar_particion(pd.DatetimeIndex(pers["fecha_objetivo"]), clave).to_numpy()
    return {"Persistencia": pers, "Prophet": prophet, "Prophet+Duan": duan}


def predicciones_lstm(clave: str) -> dict:
    """LSTM y LSTM+Duan (lee checkpoints/05_lstm_walkforward_<clave>.pkl)."""
    p = pd.read_pickle(os.path.join(CARPETA_CHECKPOINTS, f"05_lstm_walkforward_{clave}.pkl"))
    base = ["origen", "horizonte", "fecha_objetivo", "particion", "observado"]
    return {"LSTM": p[base + ["valor"]].copy(), "LSTM+Duan": p[base].assign(valor=p["valor_duan"])}


def comparar_modelos(modelos: dict, contaminante: str, particiones=("val", "test", "extra")):
    """Métricas de regresión/INCA y de alerta de varios modelos sobre los mismos pares
    (origen, horizonte). Devuelve (metricas, alertas)."""
    modelos = filtrar_comunes({k: v[v["particion"].isin(particiones)] for k, v in modelos.items()})
    met, ale = [], []
    for nombre, df in modelos.items():
        t = tabla_metricas(df, contaminante)
        t.insert(0, "modelo", nombre)
        met.append(t)
        ale.append(tabla_alertas(df, contaminante, nombre))
    met = pd.concat(met, ignore_index=True)
    met["_p"] = met["particion"].map({p: i for i, p in enumerate(PARTICIONES)})
    met["_m"] = met["modelo"].map({m: i for i, m in enumerate(modelos)})
    met = met.sort_values(["_p", "horizonte", "_m"]).drop(columns=["_p", "_m"])
    ale = pd.concat(ale, ignore_index=True)
    return met.reset_index(drop=True), ale


def resumen_alertas(alertas: pd.DataFrame, particion="test") -> pd.DataFrame:
    """Tabla compacta: días reales por umbral y recall/precisión de cada modelo y regla."""
    a = alertas[alertas["particion"] == particion].copy()
    a["modelo_regla"] = a["modelo"] + np.where(a["regla"] == "puntual", "", " (" + a["regla"] + ")")
    orden = list(dict.fromkeys(a["modelo_regla"]))
    t = a.pivot_table(index=["umbral", "horizonte", "dias_reales"], columns="modelo_regla",
                      values=["recall", "precision"]).sort_index()
    return t.reindex(columns=pd.MultiIndex.from_product([["recall", "precision"], orden])).round(2)


# ------------------------------------------------------------------
# SALIDA EN FORMATO DE LA TABLA `prediccion`
# ------------------------------------------------------------------
def a_formato_bd(pred: pd.DataFrame, clave: str) -> pd.DataFrame:
    cfg = SERIES[clave]
    out = pred.copy()
    out["estacion"] = cfg["estacion"]
    out["contaminante"] = CODIGO_CONTAMINANTE[cfg["contaminante"]]
    out["categoria_inca"] = categoria_inca(out["valor"], cfg["contaminante"]).values
    return out[COLUMNAS_PREDICCION_BD + [c for c in out.columns if c not in COLUMNAS_PREDICCION_BD]]
