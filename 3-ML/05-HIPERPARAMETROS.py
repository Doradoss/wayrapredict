# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Notebook 5: Ajuste de hiperparámetros (Optuna) - SOLO con la validación
#
# Fases (la prueba NO se usa en ningún momento):
# 1. Prophet: changepoint_prior_scale (incluye valores altos, pedido del usuario para que la
#    tendencia se adapte al cambio de nivel), seasonality_prior_scale y modo de estacionalidad.
#    Objetivo: RMSE (µg/m³) del walk-forward en validación, promedio de h = 1..3.
# 2. LSTM sola: ventana, unidades, capas, dropout, tasa de aprendizaje y lote (épocas con
#    parada temprana). Objetivo: RMSE de validación del modelo A.
# 3. LSTM del híbrido de residuos v2 (con los mejores parámetros de Prophet); en
#    cada prueba se elige alfa por horizonte en validación. Objetivo: RMSE de validación.
# 4. LSTM del híbrido en cascada (predice la concentración con entradas de Prophet).
#    El híbrido ponderado (w*Prophet + (1-w)*LSTM) no tiene hiperparámetros propios: usa la
#    LSTM de la fase 2 y w se elige en 04c con la validación.
# 5. LSTM del híbrido de residuos con variables intradiarias (máximo horario, media 7-11 h,
#    horas > 125 y > 250 µg/m³, desviación estándar horaria de cada día anterior).
# En cada fase la configuración por defecto se evalúa primero (el resultado nunca es peor que
# ella en validación).
#
# Salida: checkpoints/<fuente>/05_hiperparametros_<serie>.json, que usan 02, 03 y 04c.
# Ejecutar con la fuente elegida, p. ej. WAYRA_FUENTE=combinada.

# %%
import gc
import os
import time
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import optuna

import wayra_comun as wc
import wayra_prophet as wp
import wayra_lstm as wl
import wayra_hibrido as wh

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)
pd.set_option("display.width", 230)
pd.set_option("display.max_columns", 30)

N_PRUEBAS = {"prophet": 30, "lstm": 20, "hibrido_v2": 20, "cascada": 20, "hibrido_v2_intra": 20}
H = wl.H
wl.fijar_semillas_keras()
print(f"Fuente: {wc.FUENTE_DATOS} | series: {list(wc.SERIES)} | pruebas: {N_PRUEBAS}")
# Las pruebas se guardan en SQLite: si la ejecución se interrumpe, se retoma sin repetirlas.
ALMACEN = "sqlite:///" + os.path.join(wc.CARPETA_CHECKPOINTS, "05_optuna.db").replace("\\", "/")


def estudio_reanudable(nombre: str, clave: str, por_defecto: list) -> optuna.Study:
    estudio = optuna.create_study(direction="minimize", storage=ALMACEN, study_name=f"{nombre}_{clave}",
                                  load_if_exists=True,
                                  sampler=optuna.samplers.TPESampler(seed=wc.SEMILLA))
    if not estudio.trials:
        for params in por_defecto:
            estudio.enqueue_trial(params)
    return estudio


def optimizar(estudio: optuna.Study, objetivo, n: int):
    hechas = len([t for t in estudio.trials if t.state == optuna.trial.TrialState.COMPLETE])
    if hechas < n:
        estudio.optimize(objetivo, n_trials=n - hechas, gc_after_trial=True)
    else:
        print(f"   {estudio.study_name}: {hechas} pruebas ya completas (se reutilizan)")


def liberar_memoria():
    """TensorFlow acumula grafos al entrenar muchos modelos en un proceso: se liberan."""
    wl.keras.backend.clear_session()
    gc.collect()


def rmse_medio(y_log, pred_log) -> float:
    return float(np.nanmean([wh.rmse_ug(y_log[:, h], pred_log[:, h]) for h in range(H)]))


def resumen_estudio(estudio: optuna.Study, nombre: str, clave: str) -> pd.DataFrame:
    t = estudio.trials_dataframe(attrs=("number", "value", "params", "duration"))
    t = t.sort_values("value")
    t.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"05_busqueda_{nombre}_{clave}.csv"), sep=";", index=False)
    print(f"\n{nombre} - {clave}: mejor RMSE de validación = {estudio.best_value:.3f} {wc.UNIDAD} "
          f"(por defecto: {estudio.trials[0].value:.3f}) | mejores parámetros: {estudio.best_params}")
    print(t.head(8).round(4).to_string(index=False))
    return t


# %% [markdown]
# ## Fase 1: Prophet

# %%
def rmse_val_prophet(ds: pd.DataFrame, clave: str, params: dict) -> float:
    """Walk-forward en validación (mismos bloques que 02), sin intervalo."""
    cfg = wc.SERIES[clave]
    regimen = cfg["regimen"]
    fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
    fin_val = pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1)
    origenes = pd.date_range(fin_train, fin_val - pd.Timedelta(days=1), freq="D")
    estado = ds["OPERACION_CAUSAL"].ffill() if regimen else None
    y = wc.a_escala_modelo(ds["OBJETIVO"])
    obs, pred = [], []
    for i in range(0, len(origenes), wp.REENTRENAR_CADA):
        bloque = origenes[i:i + wp.REENTRENAR_CADA]
        m = wp.ajustar_prophet(ds, bloque[0], regimen, params)
        fechas = pd.date_range(bloque[0] + pd.Timedelta(days=1), bloque[-1] + pd.Timedelta(days=H))
        p = ({e: wp.predecir(m, fechas, e, False)["yhat"] for e in (0.0, 1.0)} if regimen
             else {None: wp.predecir(m, fechas, None, False)["yhat"]})
        for t in bloque:
            e = estado.get(t, np.nan) if regimen else None
            if regimen and np.isnan(e):
                continue
            fila_o, fila_p = [], []
            for h in range(1, H + 1):
                f = t + pd.Timedelta(days=h)
                fila_o.append(y.get(f, np.nan) if f <= fin_val else np.nan)
                fila_p.append(p[e].get(f, np.nan))
            obs.append(fila_o)
            pred.append(fila_p)
    return rmse_medio(np.array(obs), np.array(pred))


mejores = {}
datasets = {clave: wc.cargar_dataset(clave) for clave in wc.SERIES}
for clave, ds in datasets.items():
    t0 = time.time()

    def objetivo(trial):
        params = {
            "changepoint_prior_scale": trial.suggest_float("changepoint_prior_scale", 0.001, 10, log=True),
            "seasonality_prior_scale": trial.suggest_float("seasonality_prior_scale", 0.01, 30, log=True),
            "seasonality_mode": trial.suggest_categorical("seasonality_mode", ["additive", "multiplicative"]),
        }
        return rmse_val_prophet(ds, clave, params)

    # Si la fase ya se completó en una ejecución anterior (CSV guardado), se reutiliza
    ruta_csv = os.path.join(wc.CARPETA_CHECKPOINTS, f"05_busqueda_prophet_{clave}.csv")
    previa = pd.read_csv(ruta_csv, sep=";") if os.path.exists(ruta_csv) else None
    if previa is not None and len(previa) >= N_PRUEBAS["prophet"]:
        mejor = previa.sort_values("value").iloc[0]
        defecto = previa.loc[previa["number"] == 0, "value"].iloc[0]
        params = {"changepoint_prior_scale": float(mejor["params_changepoint_prior_scale"]),
                  "seasonality_prior_scale": float(mejor["params_seasonality_prior_scale"]),
                  "seasonality_mode": mejor["params_seasonality_mode"]}
        print(f"{clave}: fase de Prophet ya completa ({len(previa)} pruebas, {ruta_csv}); mejor RMSE val = "
              f"{mejor['value']:.3f} (por defecto {defecto:.3f}) | {params}")
        mejores[clave] = {"prophet": params, "rmse_val": {"prophet": float(mejor["value"]),
                                                          "prophet_defecto": float(defecto)}}
        continue
    estudio = estudio_reanudable("prophet", clave, [wp.PARAMS_PROPHET] + [   # por defecto y valores altos
        {**wp.PARAMS_PROPHET, "changepoint_prior_scale": cps} for cps in (0.5, 1.0, 5.0)])
    optimizar(estudio, objetivo, N_PRUEBAS["prophet"])
    resumen_estudio(estudio, "prophet", clave)
    mejores[clave] = {"prophet": estudio.best_params,
                      "rmse_val": {"prophet": estudio.best_value, "prophet_defecto": estudio.trials[0].value}}
    print(f"   ({time.time() - t0:.0f} s)")

# %% [markdown]
# ## Fase 2: LSTM sola

# %%
def datos_lstm(ds: pd.DataFrame, clave: str):
    cfg = wc.SERIES[clave]
    v = pd.DataFrame(index=ds.index)
    v["y_log"] = wc.a_escala_modelo(ds["OBJETIVO"])
    v["y_falta"] = ds["OBJETIVO"].isna().astype(float)
    v = v.join(wl.variables_meteo_calendario(ds, cfg["regimen"]))
    fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
    fin_val = pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1)
    esc = wl.escalador_train(v, fin_train)
    return v, wl.imputar_escalar(v, esc).to_numpy("float32"), esc, fin_train, fin_val


def muestras_lstm(v, X_todo, esc, fin_train, fin_val, ventana):
    y = v["y_log"].to_numpy()
    y_esc = (y - esc["media"]["y_log"]) / esc["desv"]["y_log"]
    obs = ~np.isnan(y)
    X, Y, orig = [], [], []
    for i in range(ventana - 1, len(v) - 1):
        if obs[i - ventana + 1:i + 1].mean() < wl.MIN_FRACCION_OBSERVADA:
            continue
        obj = np.full(H, np.nan)
        fin = min(i + 1 + H, len(v))
        obj[:fin - i - 1] = y_esc[i + 1:fin]
        X.append(X_todo[i - ventana + 1:i + 1])
        Y.append(obj)
        orig.append(v.index[i])
    X, Y, orig = np.stack(X), np.stack(Y).astype("float32"), pd.DatetimeIndex(orig)
    ult = orig + pd.Timedelta(days=H)
    ok = ~np.isnan(Y).all(axis=1)
    return X, Y, np.asarray((ult <= fin_train) & ok), np.asarray((orig >= fin_train) & (ult <= fin_val) & ok)


def sugerir_lstm(trial, lr_min, lr_max, paciencia, epocas_max):
    return {
        "ventana": trial.suggest_categorical("ventana", [7, 14, 21, 28]),
        "unidades": trial.suggest_categorical("unidades", [16, 32, 64, 128]),
        "capas": trial.suggest_int("capas", 1, 2),
        "dropout": trial.suggest_float("dropout", 0.0, 0.5),
        "tasa_aprendizaje": trial.suggest_float("tasa_aprendizaje", lr_min, lr_max, log=True),
        "lote": trial.suggest_categorical("lote", [16, 32, 64]),
        "paciencia": paciencia, "epocas_max": epocas_max,
    }


for clave, ds in datasets.items():
    t0 = time.time()
    v, X_todo, esc, fin_train, fin_val = datos_lstm(ds, clave)
    cache = {}

    def objetivo(trial):
        p = sugerir_lstm(trial, 1e-4, 3e-3, paciencia=30, epocas_max=400)
        if p["ventana"] not in cache:
            cache[p["ventana"]] = muestras_lstm(v, X_todo, esc, fin_train, fin_val, p["ventana"])
        X, Y, s_tr, s_va = cache[p["ventana"]]
        mA, _, _, epocas = wl.entrenar_A_B(X[s_tr], Y[s_tr], X[s_va], Y[s_va], None, None, X.shape[2], p)
        trial.set_user_attr("epocas", epocas)
        pred = mA.predict(X[s_va], verbose=0) * esc["desv"]["y_log"] + esc["media"]["y_log"]
        real = Y[s_va] * esc["desv"]["y_log"] + esc["media"]["y_log"]
        del mA
        liberar_memoria()
        return rmse_medio(real, pred)

    estudio = estudio_reanudable("lstm", clave, [
        {k: val for k, val in {**wl.PARAMS_LSTM, "ventana": wl.VENTANA}.items()
         if k in ("ventana", "unidades", "capas", "dropout", "tasa_aprendizaje", "lote")}])
    optimizar(estudio, objetivo, N_PRUEBAS["lstm"])
    resumen_estudio(estudio, "lstm", clave)
    mejores[clave]["lstm"] = {**estudio.best_params, "paciencia": 30, "epocas_max": 400}
    mejores[clave]["rmse_val"].update({"lstm": estudio.best_value, "lstm_defecto": estudio.trials[0].value})
    print(f"   ({time.time() - t0:.0f} s)")

# %% [markdown]
# ## Fase 3: LSTM del híbrido v2 (con los mejores parámetros de Prophet)

# %%
for clave, ds in datasets.items():
    t0 = time.time()
    wf = wh.walk_forward_prophet(ds, clave, mejores[clave]["prophet"])   # se guarda en caché para 04c
    datos = wh.Datos(ds, clave, wf)
    print(f"{clave}: walk-forward completo de Prophet listo ({time.time() - t0:.0f} s)")
    cache = {}

    def objetivo(trial):
        p = sugerir_lstm(trial, 5e-5, 1e-3, paciencia=50, epocas_max=500)
        if p["ventana"] not in cache:
            cache[p["ventana"]] = datos.muestras(p["ventana"])
        mu = cache[p["ventana"]]
        tr, va = wh.subconjunto(mu, mu["sel"]["train"]), wh.subconjunto(mu, mu["sel"]["val"])
        mA, _, _, epocas = wl.entrenar_A_B(wh.entrada(tr), tr["Y"], wh.entrada(va), va["Y"], None, None,
                                           tr["X"].shape[2], p, n_futuro=tr["F"].shape[1])
        r_hat = wh.corregir(mA, va, datos)
        alfa, _ = wh.elegir_alfa(va["yhat"], r_hat, va["r_obj"])
        trial.set_user_attr("epocas", epocas)
        trial.set_user_attr("alfa", alfa.tolist())
        del mA
        liberar_memoria()
        return rmse_medio(va["yhat"] + va["r_obj"], va["yhat"] + alfa[None, :] * r_hat)

    estudio = estudio_reanudable("hibrido_v2", clave, [
        {k: val for k, val in wl.PARAMS_HIBRIDO_V2.items()
         if k in ("ventana", "unidades", "capas", "dropout", "tasa_aprendizaje", "lote")}])
    optimizar(estudio, objetivo, N_PRUEBAS["hibrido_v2"])
    resumen_estudio(estudio, "hibrido_v2", clave)
    print(f"   alfa de la mejor prueba: {estudio.best_trial.user_attrs['alfa']} | "
          f"épocas: {estudio.best_trial.user_attrs['epocas']}")
    mejores[clave]["hibrido_v2"] = {**estudio.best_params, "paciencia": 50, "epocas_max": 500}
    mejores[clave]["rmse_val"].update({"hibrido_v2": estudio.best_value,
                                       "hibrido_v2_defecto": estudio.trials[0].value})
    print(f"   ({time.time() - t0:.0f} s)")

# %% [markdown]
# ## Fase 4: LSTM del híbrido en cascada (predice la concentración con entradas de Prophet)

# %%
for clave, ds in datasets.items():
    t0 = time.time()
    wf = wh.walk_forward_prophet(ds, clave, mejores[clave]["prophet"])   # desde la caché
    datos = wh.Datos(ds, clave, wf)
    cache = {}

    def objetivo(trial):
        p = sugerir_lstm(trial, 5e-5, 1e-3, paciencia=50, epocas_max=500)
        if p["ventana"] not in cache:
            cache[p["ventana"]] = datos.muestras(p["ventana"])
        mu = cache[p["ventana"]]
        tr, va = wh.subconjunto(mu, mu["sel"]["train"]), wh.subconjunto(mu, mu["sel"]["val"])
        mA, _, _, epocas = wl.entrenar_A_B(wh.entrada(tr), tr["Yc"], wh.entrada(va), va["Yc"], None, None,
                                           tr["X"].shape[2], p, n_futuro=tr["F"].shape[1])
        pred = wh.concentracion(mA, va, datos)
        trial.set_user_attr("epocas", epocas)
        del mA
        liberar_memoria()
        return rmse_medio(va["yhat"] + va["r_obj"], pred)

    estudio = estudio_reanudable("cascada", clave, [
        {k: val for k, val in wl.PARAMS_CASCADA.items()
         if k in ("ventana", "unidades", "capas", "dropout", "tasa_aprendizaje", "lote")}])
    optimizar(estudio, objetivo, N_PRUEBAS["cascada"])
    resumen_estudio(estudio, "cascada", clave)
    print(f"   épocas de la mejor prueba: {estudio.best_trial.user_attrs['epocas']}")
    mejores[clave]["cascada"] = {**estudio.best_params, "paciencia": 50, "epocas_max": 500}
    mejores[clave]["rmse_val"].update({"cascada": estudio.best_value, "cascada_defecto": estudio.trials[0].value})
    print(f"   ({time.time() - t0:.0f} s)")

# %% [markdown]
# ## Fase 5: LSTM del híbrido de residuos + variables intradiarias
#
# Además de las entradas de la fase 3: máximo horario, media de 7 a 11 h, horas > 125 y
# > 250 µg/m³ y desviación estándar horaria de cada día (datos de 5 min agregados a horas).

# %%
for clave, ds in datasets.items():
    t0 = time.time()
    wf = wh.walk_forward_prophet(ds, clave, mejores[clave]["prophet"])   # desde la caché
    datos = wh.Datos(ds, clave, wf, intradiarias=True)
    print(f"{clave}: variables intradiarias -> {[c for c in datos.v.columns if c.startswith('intra_')]} | "
          f"días con dato: {datos.v['intra_max_log'].notna().sum()}")
    cache = {}

    def objetivo(trial):
        p = sugerir_lstm(trial, 5e-5, 1e-3, paciencia=50, epocas_max=500)
        if p["ventana"] not in cache:
            cache[p["ventana"]] = datos.muestras(p["ventana"])
        mu = cache[p["ventana"]]
        tr, va = wh.subconjunto(mu, mu["sel"]["train"]), wh.subconjunto(mu, mu["sel"]["val"])
        mA, _, _, epocas = wl.entrenar_A_B(wh.entrada(tr), tr["Y"], wh.entrada(va), va["Y"], None, None,
                                           tr["X"].shape[2], p, n_futuro=tr["F"].shape[1])
        r_hat = wh.corregir(mA, va, datos)
        alfa, _ = wh.elegir_alfa(va["yhat"], r_hat, va["r_obj"])
        trial.set_user_attr("epocas", epocas)
        trial.set_user_attr("alfa", alfa.tolist())
        del mA
        liberar_memoria()
        return rmse_medio(va["yhat"] + va["r_obj"], va["yhat"] + alfa[None, :] * r_hat)

    estudio = estudio_reanudable("hibrido_v2_intra", clave, [
        {k: val for k, val in wl.PARAMS_HIBRIDO_V2.items()
         if k in ("ventana", "unidades", "capas", "dropout", "tasa_aprendizaje", "lote")}])
    optimizar(estudio, objetivo, N_PRUEBAS["hibrido_v2_intra"])
    resumen_estudio(estudio, "hibrido_v2_intra", clave)
    print(f"   alfa de la mejor prueba: {estudio.best_trial.user_attrs['alfa']} | "
          f"épocas: {estudio.best_trial.user_attrs['epocas']}")
    mejores[clave]["hibrido_v2_intra"] = {**estudio.best_params, "paciencia": 50, "epocas_max": 500}
    mejores[clave]["rmse_val"].update({"hibrido_v2_intra": estudio.best_value,
                                       "hibrido_v2_intra_defecto": estudio.trials[0].value})
    print(f"   ({time.time() - t0:.0f} s)")

# %% [markdown]
# ## Guardado

# %%
for clave, m in mejores.items():
    m["nota"] = "Elegidos solo con la validación (walk-forward). RMSE en µg/m³, promedio h = 1..3."
    m["fuente"] = wc.FUENTE_DATOS
    m["versiones"] = wc.versiones_librerias()
    wc.guardar_json(m, wc.ruta_hiperparametros(clave))
    print(f"\n{clave}: guardado en {wc.ruta_hiperparametros(clave)}")
    print(pd.Series(m["rmse_val"]).round(3).to_string())
