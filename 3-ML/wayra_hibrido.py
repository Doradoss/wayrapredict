# -*- coding: utf-8 -*-
"""
WayraPredict - híbrido Prophet-LSTM v2 (compartido por 04c-HIBRIDO_V2 y 05-HIPERPARAMETROS).

Cambios respecto del híbrido v1 (04-HIBRIDO_PROPHET_LSTM.py), pedidos por el usuario y
elegidos SOLO con la validación:
1. La LSTM se entrena con residuos de Prophet FUERA DE MUESTRA: el walk-forward de Prophet se
   extiende a todo el entrenamiento (bloques de 7 días alineados con los de 02-PROPHET).
   - Entrada: residuo a 1 día r1(d) = y(d) - Prophet(d | datos <= d-1).
   - Objetivo: y(t+h) - Prophet(t+h | datos <= t).
2. Predicción = Prophet + alfa_h * LSTM, con alfa_h en [0, 1] elegido en validación por horizonte.
3. Entradas nuevas: pronóstico y componentes de Prophet para t+1..t+H (tendencia, semanal, anual
   y efecto de OPERACION), media y máximo del SO2 de los últimos 7 días y OPERACION (versión
   causal: la centrada usa 3 días futuros).
4. Tasa de aprendizaje más baja y más paciencia (wayra_lstm.PARAMS_HIBRIDO_V2).
5. Nivel del intervalo de la regla de alerta calibrado en validación (máximo F2).
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd
from scipy.stats import norm

import wayra_comun as wc
import wayra_prophet as wp
import wayra_lstm as wl

H = wl.H
COMPONENTES = ["yhat", "trend", "weekly", "yearly", "efecto_operacion"]
Z80 = norm.ppf(0.9)                   # el intervalo de Prophet es del 80 %
DIAS_CALENTAMIENTO = 365              # el walk-forward empieza tras 1 año de datos
GRILLA_ALFA = np.round(np.arange(0, 1.0001, 0.05), 2)
# Grilla fina (0.005): con 0.025 el % de días con alerta saltaba de ~14 % a > 39 % entre dos niveles
GRILLA_CUANTIL = np.round(np.arange(0.50, 0.9951, 0.005), 3)
UMBRALES_INTRADIARIOS = (125, 250)   # µg/m³: horas por encima (INCA 50 y ECA de SO2)


def umbrales_intradiarios(contaminante: str) -> tuple:
    """Horas por encima de INCA 50 y del ECA del contaminante (SO2: 125 y 250 µg/m³, como antes;
    PM10: 50 y 100 µg/m³)."""
    eca = wc.ECA_24H[contaminante]
    return (int(0.5 * eca), int(eca))
# Tope de días con alerta al calibrar: F2 solo se maximiza alertando casi todos los días (con
# ~20 % de días "Moderada o peor", alertar siempre ya da F2 ~0.56). El usuario pidió priorizar
# el recall SIN alertar casi todos los días: % de días con alerta <= factor x % de días reales.
FACTOR_MAX_ALERTAS = 2.0


# ------------------------------------------------------------------
# 1) WALK-FORWARD COMPLETO DE PROPHET (entrenamiento, validación y prueba)
# ------------------------------------------------------------------
def walk_forward_prophet(ds: pd.DataFrame, clave: str, params: dict) -> pd.DataFrame:
    """Pronósticos t+1..t+H y componentes para cada origen t. Bloques de 7 días alineados con
    02-PROPHET (sus pronósticos en val/test son idénticos). Intervalo solo desde el fin de train
    (antes no se usa). Se guarda en caché por hiperparámetros."""
    cfg = wc.SERIES[clave]
    clave_cache = hashlib.md5(json.dumps({"p": params, "c": cfg, "f": wc.FUENTE_DATOS},
                                         sort_keys=True).encode()).hexdigest()[:10]
    ruta = os.path.join(wc.CARPETA_CHECKPOINTS, f"07_prophet_wf_completo_{clave}_{clave_cache}.pkl")
    if os.path.exists(ruta):
        return pd.read_pickle(ruta)

    regimen = cfg["regimen"]
    fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
    desde = ds.index.min() + pd.Timedelta(days=DIAS_CALENTAMIENTO)
    k = int(np.ceil((fin_train - desde).days / wp.REENTRENAR_CADA))
    inicio = fin_train - pd.Timedelta(days=k * wp.REENTRENAR_CADA)
    ultimo = ds.index.max()
    origenes = pd.date_range(inicio, ultimo - pd.Timedelta(days=1), freq="D")
    estado = ds["OPERACION_CAUSAL"].ffill() if regimen else None
    filas = []
    for i in range(0, len(origenes), wp.REENTRENAR_CADA):
        bloque = origenes[i:i + wp.REENTRENAR_CADA]
        m = wp.ajustar_prophet(ds, bloque[0], regimen, params)
        fechas = pd.date_range(bloque[0] + pd.Timedelta(days=1), bloque[-1] + pd.Timedelta(days=H))
        # intervalo_completo: también en train (calibración de alertas con origen móvil)
        intervalo = bloque[0] >= fin_train or bool(cfg.get("intervalo_completo"))
        pred = ({e: wp.predecir(m, fechas, e, intervalo) for e in (0.0, 1.0)} if regimen
                else {None: wp.predecir(m, fechas, None, intervalo)})
        for t in bloque:
            e = estado.get(t, np.nan) if regimen else None
            if regimen and np.isnan(e):
                continue
            p = pred[e]
            for h in range(1, H + 1):
                f = t + pd.Timedelta(days=h)
                if f > ultimo:
                    continue
                filas.append({
                    "origen": t, "horizonte": h, "fecha_objetivo": f, "estado": e if regimen else 0.0,
                    "yhat": p.at[f, "yhat"], "trend": p.at[f, "trend"], "weekly": p.at[f, "weekly"],
                    "yearly": p.at[f, "yearly"],
                    "efecto_operacion": p.at[f, "OPERACION"] if regimen else 0.0,
                    "yhat_lower": p.at[f, "yhat_lower"] if "yhat_lower" in p else np.nan,
                    "yhat_upper": p.at[f, "yhat_upper"] if "yhat_upper" in p else np.nan})
    wf = pd.DataFrame(filas)
    wf.to_pickle(ruta)
    return wf


# ------------------------------------------------------------------
# 2) VARIABLES Y MUESTRAS
# ------------------------------------------------------------------
def variables_diarias(ds: pd.DataFrame, wf: pd.DataFrame, regimen: bool) -> pd.DataFrame:
    """Variables por día (se usan solo hasta el origen t)."""
    y = wc.a_escala_modelo(ds["OBJETIVO"])
    h1 = wf[wf["horizonte"] == 1].set_index("fecha_objetivo")["yhat"]
    v = pd.DataFrame(index=ds.index)
    v["residuo_oos"] = y - h1.reindex(ds.index)
    v["y_log"] = y
    v["y_falta"] = ds["OBJETIVO"].isna().astype(float)
    v["media7_log"] = wc.a_escala_modelo(ds["OBJETIVO"].rolling(7, min_periods=4).mean())
    v["max7_log"] = wc.a_escala_modelo(ds["OBJETIVO"].rolling(7, min_periods=4).max())
    return v.join(wl.variables_meteo_calendario(ds, regimen))


def serie_horaria(clave: str) -> pd.Series:
    """SO2 horario válido (µg/m³) de la estación. Desde que hay datos de alta resolución, los
    promedios horarios construidos con los registros de 5 min (01b); antes, los horarios del OEFA
    (01), igual que la serie combinada."""
    cfg = wc.SERIES[clave]
    # Extracto ya calculado (lo incluye el repositorio, que no lleva los archivos horarios completos)
    ruta_extracto = os.path.join(wc.CARPETA_DATOS, f"fuente_{wc.FUENTE_DATOS}", f"serie_horaria_{clave}.pkl")
    if os.path.exists(ruta_extracto):
        return pd.read_pickle(ruta_extracto)
    # Pasco y Moquegua: promedios horarios de 00d (datos de 5 min, mismas reglas de validez)
    ruta_00d = os.path.join(wc.CARPETA_DATOS, "inventario_estaciones", f"02_{cfg['estacion']}_horario.pkl")
    if wc.FUENTE_DATOS == "pasco_moquegua" and os.path.exists(ruta_00d):
        col = {"PM10": "PM10", "PM2.5": "PM25"}[cfg["contaminante"]]
        return pd.read_pickle(ruta_00d)[col].dropna().sort_index()
    partes, inicio_ar = [], None
    ruta_ar = os.path.join(wc.CARPETA_DATOS, "alta_resolucion", f"03_dataset_horario_{cfg['estacion']}_v2.pkl")
    if wc.FUENTE_DATOS != "original" and os.path.exists(ruta_ar):
        h = pd.read_pickle(ruta_ar)["CONTAMINANTE"].dropna()
        partes.append(h)
        inicio_ar = h.index.min().floor("D")
    if wc.FUENTE_DATOS != "alta_resolucion":
        oe = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, "01_mediciones_marcadas.pkl"))
        oe = oe[(oe["NOMBRE_PUNTO"] == cfg["estacion"]) & (oe["VARIABLE"] == cfg["contaminante"])
                & ~oe["FLAG_DOMINIO"] & ~oe["FLAG_CERO_RACHA"]].groupby("FECHA_HORA")["VALOR"].mean()
        partes.append(oe[oe.index < inicio_ar] if inicio_ar is not None else oe)
    return pd.concat(partes).sort_index()


def variables_intradiarias(ds: pd.DataFrame, clave: str) -> pd.DataFrame:
    """Por día (solo días con >= 18 horas válidas): máximo horario, media de 7 a 11 h (horas
    7, 8, 9 y 10; >= 3 válidas), horas por encima de 125 y 250 µg/m³ y desviación estándar
    horaria. Se usan como entradas rezagadas (días <= origen). Umbrales: INCA 50 y ECA del
    contaminante (SO2: 125 y 250 µg/m³)."""
    h = serie_horaria(clave).to_frame("v")
    h["dia"], h["hora"] = h.index.floor("D"), h.index.hour
    g = h.groupby("dia")["v"]
    salida = pd.DataFrame({"intra_max_log": np.log1p(g.max()), "intra_desv_log": np.log1p(g.std())})
    for u in umbrales_intradiarios(wc.SERIES[clave]["contaminante"]):
        salida[f"intra_horas_sobre_{u}"] = (h["v"] > u).groupby(h["dia"]).sum()
    salida = salida.where(g.count() >= 18)
    manana = h[h["hora"].between(7, 10)].groupby("dia")["v"].agg(["mean", "count"])
    salida["intra_media_7_11_log"] = np.log1p(manana["mean"].where(manana["count"] >= 3))
    return salida.reindex(ds.index)


def futuro_por_origen(wf: pd.DataFrame) -> pd.DataFrame:
    """Pronóstico y componentes de Prophet para t+1..t+H (una fila por origen)."""
    piv = wf.pivot(index="origen", columns="horizonte", values=COMPONENTES)
    piv.columns = [f"{c}_{h}" for c, h in piv.columns]
    piv["estado"] = wf.groupby("origen")["estado"].first()
    return piv


class Datos:
    """Prepara, escala (con estadísticos de train) y arma las muestras de una serie."""

    def __init__(self, ds: pd.DataFrame, clave: str, wf: pd.DataFrame, intradiarias: bool = False):
        cfg = wc.SERIES[clave]
        self.ds, self.clave, self.wf = ds, clave, wf
        self.fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
        self.fin_val = pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1)
        self.v = variables_diarias(ds, wf, cfg["regimen"])
        if intradiarias:
            self.v = self.v.join(variables_intradiarias(ds, clave))
        self.esc = wl.escalador_train(self.v, self.fin_train)
        self.v_esc = wl.imputar_escalar(self.v, self.esc).to_numpy("float32")
        fut = futuro_por_origen(wf)
        fut_tr = fut.loc[fut.index + pd.Timedelta(days=H) <= self.fin_train]
        self.fut_media, self.fut_desv = fut_tr.mean(), fut_tr.std().replace(0, 1).fillna(1)
        self.fut = fut
        self.fut_esc = ((fut - self.fut_media) / self.fut_desv).fillna(0)
        self.y = self.v["y_log"].to_numpy()
        self.r_obs = self.v["residuo_oos"].notna().to_numpy()
        self.obs = ~np.isnan(self.y)
        self.idx = ds.index
        self.mu_r, self.sd_r = self.esc["media"]["residuo_oos"], self.esc["desv"]["residuo_oos"]

    def muestras(self, ventana: int) -> dict:
        """Y: residuo de Prophet escalado (variante 'residuos'); Yc: concentración en log
        escalada (variante 'cascada')."""
        salida = {k: [] for k in ("origen", "X", "F", "Y", "Yc", "yhat", "r_obj", "lower", "upper")}
        mu_y, sd_y = self.esc["media"]["y_log"], self.esc["desv"]["y_log"]
        pos = self.idx.get_indexer(self.fut.index)
        yh_cols = [f"yhat_{h}" for h in range(1, H + 1)]
        for t, i in zip(self.fut.index, pos):
            if i < ventana - 1:
                continue
            ventana_obs = self.obs[i - ventana + 1:i + 1]
            if ventana_obs.mean() < wl.MIN_FRACCION_OBSERVADA or \
                    self.r_obs[i - ventana + 1:i + 1].mean() < wl.MIN_FRACCION_OBSERVADA:
                continue
            yhat = self.fut.loc[t, yh_cols].to_numpy(float)
            r_obj = np.array([self.y[i + h] - yhat[h - 1] if i + h < len(self.y) else np.nan
                              for h in range(1, H + 1)])
            g = self.wf_lookup(t)
            salida["origen"].append(t)
            salida["X"].append(self.v_esc[i - ventana + 1:i + 1])
            salida["F"].append(self.fut_esc.loc[t].to_numpy("float32"))
            salida["Y"].append(((r_obj - self.mu_r) / self.sd_r).astype("float32"))
            salida["Yc"].append((((yhat + r_obj) - mu_y) / sd_y).astype("float32"))
            salida["yhat"].append(yhat)
            salida["r_obj"].append(r_obj)
            salida["lower"].append(g[0])
            salida["upper"].append(g[1])
        out = {k: np.stack(v) for k, v in salida.items() if k != "origen"}
        out["origen"] = pd.DatetimeIndex(salida["origen"])
        ult = out["origen"] + pd.Timedelta(days=H)
        con_obj = ~np.isnan(out["Y"]).all(axis=1)
        out["sel"] = {
            "train": np.asarray((ult <= self.fin_train) & con_obj),
            "val": np.asarray((out["origen"] >= self.fin_train) & (ult <= self.fin_val) & con_obj),
            "train_val": np.asarray((ult <= self.fin_val) & con_obj),
            "eval": np.asarray(out["origen"] >= self.fin_train),   # orígenes de val/test (como 02)
        }
        return out

    def wf_lookup(self, t):
        if not hasattr(self, "_lu"):
            p = self.wf.pivot(index="origen", columns="horizonte", values=["yhat_lower", "yhat_upper"])
            self._lu = p
        fila = self._lu.loc[t]
        return (fila["yhat_lower"].reindex(range(1, H + 1)).to_numpy(float),
                fila["yhat_upper"].reindex(range(1, H + 1)).to_numpy(float))


def subconjunto(mu: dict, m) -> dict:
    return {k: v[m] for k, v in mu.items() if k not in ("sel", "origen")} | {"origen": mu["origen"][m]}


def entrada(d: dict):
    return [d["X"], d["F"]]


def corregir(modelo, d: dict, datos: Datos) -> np.ndarray:
    """Corrección de la LSTM en escala log (residuo predicho). Variante 'residuos'."""
    return modelo.predict(entrada(d), verbose=0) * datos.sd_r + datos.mu_r


def concentracion(modelo, d: dict, datos: Datos) -> np.ndarray:
    """Concentración predicha en escala log. Variante 'cascada'."""
    return modelo.predict(entrada(d), verbose=0) * datos.esc["desv"]["y_log"] + datos.esc["media"]["y_log"]


def elegir_peso(prophet_log, lstm_log, y_log_obs):
    """w_h en [0, 1] de w*Prophet + (1-w)*LSTM (escala log) que minimiza el RMSE (µg/m³) en
    validación, por horizonte. Variante 'ponderada'."""
    pesos, tabla = [], []
    for h in range(H):
        errores = [rmse_ug(y_log_obs[:, h], w * prophet_log[:, h] + (1 - w) * lstm_log[:, h])
                   for w in GRILLA_ALFA]
        pesos.append(float(GRILLA_ALFA[int(np.nanargmin(errores))]))
        tabla.append(errores)
    return np.array(pesos), pd.DataFrame(np.array(tabla).T, index=GRILLA_ALFA,
                                         columns=[f"h{h + 1}" for h in range(H)])


# ------------------------------------------------------------------
# 3) ALFA, DUAN Y CALIBRACIÓN DEL INTERVALO (solo validación)
# ------------------------------------------------------------------
def rmse_ug(y_log_obs, pred_log):
    m = ~np.isnan(y_log_obs) & ~np.isnan(pred_log)
    return float(np.sqrt(np.mean((np.expm1(pred_log[m]) - np.expm1(y_log_obs[m])) ** 2))) if m.any() else np.nan


def elegir_alfa(yhat, r_hat, r_obj):
    """alfa_h en [0, 1] que minimiza el RMSE (µg/m³) en validación, por horizonte."""
    y_obs = yhat + r_obj
    alfas, tabla = [], []
    for h in range(H):
        errores = [rmse_ug(y_obs[:, h], yhat[:, h] + a * r_hat[:, h]) for a in GRILLA_ALFA]
        alfas.append(float(GRILLA_ALFA[int(np.nanargmin(errores))]))
        tabla.append(errores)
    return np.array(alfas), pd.DataFrame(np.array(tabla).T, index=GRILLA_ALFA,
                                         columns=[f"h{h + 1}" for h in range(H)])


def factores_duan(pred_log, y_log_obs):
    return np.array([wc.factor_duan(y_log_obs[:, h] - pred_log[:, h]) for h in range(H)])


def calibrar_cuantil(centro_log, lower, upper, y_log_obs, contaminante: str):
    """Cuantil de la regla de alerta (límite superior > umbral 'Moderada o peor') que maximiza
    F2 en validación, por horizonte. Supone la incertidumbre de Prophet ~normal en escala log:
    sigma = (upper - lower) / (2 * z_0.9)."""
    umbral = np.log1p(wc.UMBRALES_ALERTA["moderada_o_peor"] * wc.ECA_24H[contaminante])
    sigma = (upper - lower) / (2 * Z80)
    cuantiles, filas = [], []
    for h in range(H):
        real = y_log_obs[:, h] > umbral
        ok = ~np.isnan(y_log_obs[:, h]) & ~np.isnan(sigma[:, h])
        tope = FACTOR_MAX_ALERTAS * (real & ok).sum() / ok.sum() * 100
        candidatos = []
        for q in GRILLA_CUANTIL:
            alerta = (centro_log[:, h] + norm.ppf(q) * sigma[:, h]) > umbral
            vp = (real & alerta & ok).sum()
            rec = vp / (real & ok).sum() if (real & ok).sum() else np.nan
            prec = vp / (alerta & ok).sum() if (alerta & ok).sum() else np.nan
            f2 = wc.f_beta(prec, rec, 2)
            pct = (alerta & ok).sum() / ok.sum() * 100
            filas.append({"horizonte": h + 1, "cuantil": q, "recall": rec, "precision": prec, "F2": f2,
                          "pct_dias_con_alerta": pct, "pct_tope": tope, "cumple_tope": pct <= tope})
            candidatos.append((pct <= tope, f2, -pct, q))
        # Máximo F2 entre los cuantiles que respetan el tope; si ninguno lo respeta, el que menos alerta
        validos = [c for c in candidatos if c[0]]
        elegido = max(validos, key=lambda c: c[1])[3] if validos else max(candidatos, key=lambda c: c[2])[3]
        cuantiles.append(float(elegido))
    return np.array(cuantiles), pd.DataFrame(filas)


def limite_alerta(centro_log, lower, upper, cuantiles):
    sigma = (upper - lower) / (2 * Z80)
    return np.expm1(centro_log + norm.ppf(cuantiles)[None, :] * sigma)
