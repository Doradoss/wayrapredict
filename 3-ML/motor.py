# -*- coding: utf-8 -*-
"""
Experimento 2 - motor compartido de variantes (exploratorio; la prueba ya había sido observada).

Reúne las funciones del experimento 1 (experimento_mejoras/E02_variantes.py, que NO se modifica) y agrega:
- fuentes meteorológicas de varios modelos y su promedio (Open-Meteo),
- variables sugeridas por el análisis de picos (definidas solo con el entrenamiento),
- búsqueda de hiperparámetros con Optuna por variante (solo validación),
- calibración del cuantil de alerta con origen móvil para series nuevas (PM2.5).
Nada escribe en las carpetas de la evaluación principal.
"""
import gc
import os

import numpy as np
import pandas as pd
import keras
from keras import ops
import lightgbm as lgb
import optuna

import wayra_comun as wc
import wayra_lstm as wl
import wayra_hibrido as wh

BASE = os.path.join(wc.RAIZ, "v2")
EXP1 = os.path.join(wc.RAIZ, "v2")
H = wc.HORIZONTES
NH = len(H)
GRILLA = np.round(np.arange(0, 1.0001, 0.05), 2)
VECINAS = {"CA-HUAR-01_PM10": {"CA-COLQ-01": ""}, "CA-ILO-02_PM10": {"CA-ILO-01": "_propia", "CA-ILO-03": "_propia"},
           "CA-ILO-02_PM25": {"CA-ILO-01": "_propia", "CA-ILO-03": "_propia"}}
ALMACEN = "sqlite:///" + os.path.join(BASE, "modelos", "optuna_exp2.db").replace("\\", "/")
optuna.logging.set_verbosity(optuna.logging.WARNING)


@keras.saving.register_keras_serializable(package="wayra_exp2")
def mse_muestra(y_true, y_pred):
    m = ops.logical_not(ops.isnan(y_true))
    yt = ops.where(m, y_true, 0.0)
    e = ops.where(m, ops.square(yt - y_pred), 0.0)
    return ops.sum(e, axis=-1) / ops.maximum(ops.sum(ops.cast(m, "float32"), axis=-1), 1.0)


def liberar():
    keras.backend.clear_session()
    gc.collect()


def entrenar_AB(Xtr, Ytr, Xva, Yva, Xtv, Ytv, p, n_var, n_fut=0, solo_A=False):
    keras.utils.set_random_seed(wc.SEMILLA)
    mA = wl.crear_lstm(n_var, p, ventana=int(p["ventana"]), n_futuro=n_fut)
    mA.compile(optimizer=keras.optimizers.Adam(p["tasa_aprendizaje"]), loss=mse_muestra)
    parada = keras.callbacks.EarlyStopping(monitor="val_loss", patience=p["paciencia"], restore_best_weights=True)
    hist = mA.fit(Xtr, Ytr, validation_data=(Xva, Yva), epochs=p["epocas_max"], batch_size=p["lote"],
                  callbacks=[parada], verbose=0, shuffle=True)
    ep = int(np.argmin(hist.history["val_loss"])) + 1
    if solo_A:
        return mA, None, ep
    keras.utils.set_random_seed(wc.SEMILLA)
    mB = wl.crear_lstm(n_var, p, ventana=int(p["ventana"]), n_futuro=n_fut)
    mB.compile(optimizer=keras.optimizers.Adam(p["tasa_aprendizaje"]), loss=mse_muestra)
    mB.fit(Xtv, Ytv, epochs=ep, batch_size=p["lote"], verbose=0, shuffle=True)
    return mA, mB, ep


def rmse(y, p):
    m = ~np.isnan(y) & ~np.isnan(p)
    return float(np.sqrt(np.mean((y[m] - p[m]) ** 2))) if m.any() else np.nan


# ------------------------------------------------------------------
# Variables
# ------------------------------------------------------------------
def variables_base(D, extra=None):
    ds = D["ds"]
    v = pd.DataFrame(index=ds.index)
    v["y_log"] = np.log1p(ds["OBJETIVO"])
    v["y_falta"] = ds["OBJETIVO"].isna().astype(float)
    v = v.join(wl.variables_meteo_calendario(ds, D["cfg"]["regimen"]))
    return v.join(extra) if extra is not None else v


def vars_vecinas(D):
    out = pd.DataFrame(index=D["ds"].index)
    for v, suf in VECINAS.get(D["clave"], {}).items():
        vec = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, f"03_dataset_{v}_PM10_ar{suf}.pkl"))["OBJETIVO"]
        out[f"vec_{v}_log"] = np.log1p(vec.reindex(out.index))
        out[f"vec_{v}_falta"] = out[f"vec_{v}_log"].isna().astype(float)
    return out


def vars_picos(D):
    """Sugeridas por el análisis de picos (fase 1): racha de días secos, lluvia de 7 días, calma, viento del
    sector de los picos y anomalía de humedad respecto de su media mensual. Umbrales y climatologías calculados
    SOLO con el entrenamiento; cada valor usa solo información del día t o anterior."""
    ds = D["ds"]
    tr = ds.index <= D["fin_train"]
    pp = ds["PRECIPITACION"].fillna(0) if "PRECIPITACION" in ds else pd.Series(0.0, index=ds.index)
    llueve = pp >= 0.1
    racha_seca = (~llueve).astype(int).groupby(llueve.cumsum()).cumsum()
    out = pd.DataFrame(index=ds.index)
    out["pic_dias_secos_log"] = np.log1p(racha_seca)
    out["pic_lluvia_7d_log"] = np.log1p(pp.rolling(7, min_periods=1).sum())
    if "VELOCIDAD_VIENTO" in ds:
        p25 = ds.loc[tr, "VELOCIDAD_VIENTO"].quantile(0.25)
        out["pic_calma"] = (ds["VELOCIDAD_VIENTO"] <= p25).astype(float).where(ds["VELOCIDAD_VIENTO"].notna())
    if "VIENTO_COS" in ds:
        q25 = ds.loc[tr, "VIENTO_COS"].quantile(0.25)
        out["pic_viento_sector_cos_bajo"] = (ds["VIENTO_COS"] <= q25).astype(float).where(ds["VIENTO_COS"].notna())
    if "HUMEDAD_RELATIVA" in ds:
        clim = ds.loc[tr, "HUMEDAD_RELATIVA"].groupby(ds.index[tr].month).mean()
        out["pic_hr_anomalia"] = ds["HUMEDAD_RELATIVA"] - pd.Series(ds.index.month, index=ds.index).map(clim)
    return out


def meteo_fuente(D, modelo):
    """(hf, {1,2,3: pr}) diarios del modelo elegido o el promedio entre modelos disponibles por día."""
    datos = pd.read_pickle(os.path.join(BASE, "datos_externos", f"{D['est']}_meteo_multimodelo.pkl"))
    if modelo != "promedio":
        return datos[modelo]["hf"], datos[modelo]["pr"]
    disp = [m for m, d in datos.items() if d["hf"] is not None]
    hf = pd.concat([datos[m]["hf"] for m in disp]).groupby(level=0).mean()
    pr = {h: pd.concat([datos[m]["pr"][h] for m in disp if datos[m]["pr"][h] is not None]).groupby(level=0).mean() for h in H}
    return hf, pr


def futuro_externo(D, tipo, modelo="best_match"):
    if tipo == "meteo_pron":
        hf, prs = meteo_fuente(D, modelo)
        cols = ["temp", "hr", "viento", "viento_sin", "viento_cos", "precip", "nubes"]
        hf = hf.reindex(columns=cols).copy()
        prs = {h: prs[h].reindex(columns=cols).copy() for h in H}
        for df in [hf] + list(prs.values()):
            df["precip"] = np.log1p(df["precip"].clip(lower=0))
        ref = hf.loc[:D["fin_train"]]
        mu, sd = ref.mean(), ref.std().replace(0, 1).fillna(1)

        def f(t):
            out = []
            for h in H:
                fuente = hf if t + pd.Timedelta(days=NH) <= D["fin_train"] else prs[h]
                fila = fuente.reindex([t + pd.Timedelta(days=h)]).iloc[0]
                out.append(((fila - mu) / sd).fillna(0).to_numpy())
                out.append([float(fila.isna().any())])
            return np.concatenate(out).astype("float32")
        return f, hf["temp"].first_valid_index()
    raise ValueError(tipo)


# ------------------------------------------------------------------
# Muestras, LSTM y LightGBM
# ------------------------------------------------------------------
def muestras(D, v, p, fut=None, inicio=None):
    vent = int(p["ventana"])
    esc = wl.escalador_train(v, D["fin_train"])
    X_todo = wl.imputar_escalar(v, esc).to_numpy("float32")
    ylog = np.log1p(D["ds"]["OBJETIVO"].to_numpy(float))
    tr = v.index <= D["fin_train"]
    mu, sd = np.nanmean(ylog[tr]), np.nanstd(ylog[tr])
    obs = ~np.isnan(ylog)
    O, X, Y, F = [], [], [], []
    for i in range(vent - 1, len(v)):
        t = v.index[i]
        if obs[i - vent + 1:i + 1].mean() < wl.MIN_FRACCION_OBSERVADA or (inicio is not None and t < inicio):
            continue
        obj = np.full(NH, np.nan)
        fin = min(i + 1 + NH, len(v))
        obj[:fin - i - 1] = (ylog[i + 1:fin] - mu) / sd
        O.append(t)
        X.append(X_todo[i - vent + 1:i + 1])
        Y.append(obj)
        if fut is not None:
            F.append(fut(t))
    O = pd.DatetimeIndex(O)
    M = {"O": O, "X": np.stack(X), "Y": np.stack(Y).astype("float32"), "F": np.stack(F) if fut is not None else None,
         "mu": mu, "sd": sd}
    ult = O + pd.Timedelta(days=NH)
    ok = ~np.isnan(M["Y"]).all(axis=1)
    M["sel"] = {"train": np.asarray((ult <= D["fin_train"]) & ok),
                "val": np.asarray((O >= D["fin_train"]) & (ult <= D["fin_val"]) & ok),
                "tv": np.asarray((ult <= D["fin_val"]) & ok)}
    return M


def _entrada(M, m):
    return [M["X"][m], M["F"][m]] if M["F"] is not None else M["X"][m]


def correr_lstm(D, v, p, fut_tipo=None, modelo="best_match"):
    fut, inicio = futuro_externo(D, fut_tipo, modelo) if fut_tipo else (None, None)
    M = muestras(D, v, p, fut, inicio)
    s = M["sel"]
    nf = M["F"].shape[1] if M["F"] is not None else 0
    liberar()
    mA, mB, ep = entrenar_AB(_entrada(M, s["train"]), M["Y"][s["train"]], _entrada(M, s["val"]), M["Y"][s["val"]],
                             _entrada(M, s["tv"]), M["Y"][s["tv"]], p, M["X"].shape[2], nf)
    usaB = np.asarray(M["O"] >= D["fin_val"])
    pred = np.empty((len(M["O"]), NH))
    for mod, m in ((mA, ~usaB), (mB, usaB)):
        if m.any():
            pred[m] = mod.predict(_entrada(M, m), verbose=0) * M["sd"] + M["mu"]
    del mA, mB
    liberar()
    return pd.DataFrame(pred, index=M["O"], columns=H), {"epocas": ep, "muestras_train": int(s["train"].sum()),
                                                         "inicio_entrenamiento": str(M["O"][s["train"]].min().date())}


def sugerir_lstm(trial):
    """Mismo espacio que 05-HIPERPARAMETROS (LSTM sola)."""
    return {"ventana": trial.suggest_categorical("ventana", [7, 14, 21, 28]),
            "unidades": trial.suggest_categorical("unidades", [16, 32, 64, 128]),
            "capas": trial.suggest_int("capas", 1, 2), "dropout": trial.suggest_float("dropout", 0.0, 0.5),
            "tasa_aprendizaje": trial.suggest_float("tasa_aprendizaje", 1e-4, 3e-3, log=True),
            "lote": trial.suggest_categorical("lote", [16, 32, 64]), "paciencia": 30, "epocas_max": 400}


def optuna_lstm(D, v, nombre, n=20, fut_tipo=None, modelo="best_match", defecto=None):
    """Hiperparámetros de la LSTM de una variante: RMSE medio h1-h3 (µg/m³) del modelo A en validación."""
    fut, inicio = futuro_externo(D, fut_tipo, modelo) if fut_tipo else (None, None)
    cache = {}

    def objetivo(trial):
        p = sugerir_lstm(trial)
        if p["ventana"] not in cache:
            cache[p["ventana"]] = muestras(D, v, p, fut, inicio)
        M = cache[p["ventana"]]
        s = M["sel"]
        nf = M["F"].shape[1] if M["F"] is not None else 0
        liberar()
        mA, _, ep = entrenar_AB(_entrada(M, s["train"]), M["Y"][s["train"]], _entrada(M, s["val"]), M["Y"][s["val"]],
                                None, None, p, M["X"].shape[2], nf, solo_A=True)
        pred = mA.predict(_entrada(M, s["val"]), verbose=0) * M["sd"] + M["mu"]
        real = M["Y"][s["val"]] * M["sd"] + M["mu"]
        del mA
        liberar()
        return float(np.nanmean([wh.rmse_ug(real[:, k], pred[:, k]) for k in range(NH)]))

    e = optuna.create_study(direction="minimize", storage=ALMACEN, study_name=f"{nombre}_{D['tag']}", load_if_exists=True,
                            sampler=optuna.samplers.TPESampler(seed=wc.SEMILLA))
    if not e.trials and defecto:
        e.enqueue_trial({k: defecto[k] for k in ("ventana", "unidades", "capas", "dropout", "tasa_aprendizaje", "lote")})
    hechas = len([t for t in e.trials if t.state == optuna.trial.TrialState.COMPLETE])
    if hechas < n:
        e.optimize(objetivo, n_trials=n - hechas, gc_after_trial=True)
    return {**e.best_params, "paciencia": 30, "epocas_max": 400}, e.best_value, e.trials[0].value


PARAMS_LGB = {"objective": "regression", "learning_rate": 0.03, "num_leaves": 15, "min_data_in_leaf": 20,
              "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 1.0, "verbose": -1,
              "seed": wc.SEMILLA, "deterministic": True, "num_threads": 2}


def correr_lgbm(D, v, p_lstm, params=PARAMS_LGB, solo_val=False):
    M = muestras(D, v, p_lstm)
    s = M["sel"]
    Xf = M["X"].reshape(len(M["X"]), -1)
    usaB = np.asarray(M["O"] >= D["fin_val"])
    pred = np.full((len(M["O"]), NH), np.nan)
    errores = []
    for k in range(NH):
        mtr, mva = s["train"] & ~np.isnan(M["Y"][:, k]), s["val"] & ~np.isnan(M["Y"][:, k])
        mA = lgb.train(params, lgb.Dataset(Xf[mtr], M["Y"][mtr, k]), 2000, valid_sets=[lgb.Dataset(Xf[mva], M["Y"][mva, k])],
                       callbacks=[lgb.early_stopping(100, verbose=False)])
        it = mA.best_iteration or 100
        pv = mA.predict(Xf[mva], num_iteration=it) * M["sd"] + M["mu"]
        errores.append(wh.rmse_ug(M["Y"][mva, k] * M["sd"] + M["mu"], pv))
        if solo_val:
            continue
        mtv = s["tv"] & ~np.isnan(M["Y"][:, k])
        mB = lgb.train(params, lgb.Dataset(Xf[mtv], M["Y"][mtv, k]), it)
        pred[~usaB, k] = mA.predict(Xf[~usaB], num_iteration=it)
        pred[usaB, k] = mB.predict(Xf[usaB])
    if solo_val:
        return float(np.mean(errores))
    return pd.DataFrame(pred * M["sd"] + M["mu"], index=M["O"], columns=H), {"rmse_val_A": float(np.mean(errores))}


def optuna_lgbm(D, v, p_lstm, n=20):
    def objetivo(trial):
        params = {**PARAMS_LGB, "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
                  "num_leaves": trial.suggest_int("num_leaves", 7, 63),
                  "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 10, 60),
                  "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
                  "lambda_l2": trial.suggest_float("lambda_l2", 0.0, 5.0)}
        return correr_lgbm(D, v, p_lstm, params, solo_val=True)

    e = optuna.create_study(direction="minimize", storage=ALMACEN, study_name=f"E8opt_{D['tag']}", load_if_exists=True,
                            sampler=optuna.samplers.TPESampler(seed=wc.SEMILLA))
    if not e.trials:
        e.enqueue_trial({k: PARAMS_LGB[k] for k in ("learning_rate", "num_leaves", "min_data_in_leaf", "feature_fraction", "lambda_l2")})
    hechas = len([t for t in e.trials if t.state == optuna.trial.TrialState.COMPLETE])
    if hechas < n:
        e.optimize(objetivo, n_trials=n - hechas, gc_after_trial=True)
    return {**PARAMS_LGB, **e.best_params}, e.best_value, e.trials[0].value


# ------------------------------------------------------------------
# Candidatos (sola / ponderada con Prophet; con o sin Duan), intervalo y alerta
# ------------------------------------------------------------------
def tabla_larga(D, pred_log):
    base = D["sel"][["origen", "horizonte", "fecha_objetivo", "particion", "observado", "valor"]].rename(columns={"valor": "valor_principal"})
    wf = D["wf"][["origen", "horizonte", "yhat", "yhat_lower", "yhat_upper"]]
    if len(pred_log):
        pl = pred_log.stack().rename("var_log").reset_index()
        pl.columns = ["origen", "horizonte", "var_log"]
        pl["horizonte"] = pl["horizonte"].astype(int)
        t = base.merge(pl, on=["origen", "horizonte"], how="left")
    else:
        t = base.assign(var_log=np.nan)
    t = t.merge(wf, on=["origen", "horizonte"], how="left")
    t["obs_log"] = np.log1p(t["observado"])
    return t


def elegir_y_aplicar(D, t):
    elegido, partes = {}, []
    for h, g in t.groupby("horizonte"):
        g = g.copy()
        val = g["particion"] == "val"
        cands = []
        for w in GRILLA:
            centro = w * g["yhat"] + (1 - w) * g["var_log"]
            fd = wc.factor_duan((g.loc[val, "obs_log"] - centro[val]).to_numpy())
            for duan in (False, True):
                vv = np.exp(centro) * fd - 1 if duan else np.expm1(centro)
                cands.append((rmse(g.loc[val, "observado"].to_numpy(), vv[val].to_numpy()), w, duan, fd))
        r_, w, duan, fd = min([c for c in cands if not np.isnan(c[0])], key=lambda c: c[0])
        centro = w * g["yhat"] + (1 - w) * g["var_log"]
        g["centro_log"] = centro
        g["valor"] = np.exp(centro) * fd - 1 if duan else np.expm1(centro)
        d = centro - g["yhat"]
        g["limite_inferior"], g["limite_superior"] = np.expm1(g["yhat_lower"] + d), np.expm1(g["yhat_upper"] + d)
        elegido[int(h)] = {"w_prophet": float(w), "duan": bool(duan), "factor_duan": round(fd, 4), "rmse_val": round(r_, 3)}
        partes.append(g)
    t = pd.concat(partes)
    agregar_alerta(D, t, elegido)
    return t, elegido


def agregar_alerta(D, t, elegido):
    sigma = (t["yhat_upper"] - t["yhat_lower"]) / (2 * wh.Z80)
    if D.get("q_movil") is not None:
        q = {h: D["q_movil"][h - 1] for h in H}
    else:
        val = t[t["particion"] == "val"]
        piv = {c: val.pivot(index="origen", columns="horizonte", values=c).reindex(columns=H).to_numpy()
               for c in ("centro_log", "yhat_lower", "yhat_upper", "obs_log", "yhat")}
        d = piv["centro_log"] - piv["yhat"]
        qs, _ = wh.calibrar_cuantil(piv["centro_log"], piv["yhat_lower"] + d, piv["yhat_upper"] + d, piv["obs_log"],
                                    D["cfg"]["contaminante"])
        q = dict(zip(H, qs))
    t["limite_alerta"] = np.expm1(t["centro_log"] + wh.norm.ppf(t["horizonte"].map(q)) * sigma)
    for h in H:
        elegido.setdefault(int(h), {})["cuantil_alerta"] = float(q[h])


def q_origen_movil(D):
    """Cuantil de alerta con origen móvil (como 04c): pronósticos de Prophet fuera de muestra con objetivo
    anterior a la prueba."""
    wfm = D["wf"][D["wf"]["fecha_objetivo"] <= D["fin_val"]].copy()
    wfm["obs_log"] = np.log1p(wfm["fecha_objetivo"].map(D["ds"]["OBJETIVO"]))
    piv = {c: wfm.pivot(index="origen", columns="horizonte", values=c).reindex(columns=H).to_numpy()
           for c in ("yhat", "yhat_lower", "yhat_upper", "obs_log")}
    q, _ = wh.calibrar_cuantil(piv["yhat"], piv["yhat_lower"], piv["yhat_upper"], piv["obs_log"], D["cfg"]["contaminante"])
    return list(q)


def guardar(D, nombre, t, info):
    os.makedirs(D["carpeta"], exist_ok=True)
    t = t.copy()
    t["variante"] = nombre
    pd.to_pickle({"pred": t, "info": info}, os.path.join(D["carpeta"], f"{nombre}.pkl"))


def hecho(D, nombre):
    return os.path.exists(os.path.join(D["carpeta"], f"{nombre}.pkl"))
