# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Notebook 4d: LSTM global (CA-CC-01 + CA-HUAR-01 + CA-ILO-02)
#
# Decisión definida antes del inventario: una LSTM entrenada con las tres estaciones. Se usa en
# Pasco (CA-HUAR-01) y Moquegua (CA-ILO-02); los modelos ya evaluados de La Oroya no cambian
# (CA-CC-01 solo aporta muestras de entrenamiento).
#
# - Normalización POR ESTACIÓN con estadísticas solo del entrenamiento de cada una (las altitudes y
#   los contaminantes son muy distintos: presión, nivel del SO2 vs PM10). Instrucciones_4.md.
# - Entradas alineadas: las variables que una estación no tiene (OPERACION_CAUSAL fuera de La
#   Oroya) valen 0 (= media de train tras normalizar). Se agrega un indicador de estación (one-hot).
# - Dos modelos globales, con el mismo esquema que los modelos por estación:
#   a) "LSTM global": LSTM sola (como 03): objetivo = log(1 + concentración) normalizado por estación.
#   b) "Residuos global": LSTM de residuos de Prophet fuera de muestra (como el híbrido de residuos
#      de 04c): objetivo = residuo normalizado por estación; en 04c se elige alfa por horizonte.
# - Hiperparámetros con Optuna SOLO en validación (objetivo: RMSE medio de h = 1..3 en µg/m³,
#   promedio de CA-HUAR-01 y CA-ILO-02). Modelo A: train con parada temprana en val (conjunta);
#   modelo B: train + val durante las épocas óptimas de A (predice desde el fin de val).
#
# Ejecutar con WAYRA_FUENTE=pasco_moquegua (después de 05, 02 y 03). Salidas en
# checkpoints/fuente_pasco_moquegua/: 05_lstm_global_walkforward_<serie>.pkl y
# 08_residuos_global_walkforward_<serie>.pkl (las lee 04c).

# %%
import gc
import json
import hashlib
import os
import time
import warnings

import numpy as np
import pandas as pd
import optuna

import wayra_comun as wc
import wayra_prophet as wp
import wayra_lstm as wl
import wayra_hibrido as wh

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)
pd.set_option("display.width", 220)

assert wc.FUENTE_DATOS == "pasco_moquegua", "Ejecutar con WAYRA_FUENTE=pasco_moquegua"
VERSION_MODELO = "v1"
H = wl.H
N_PRUEBAS = {"lstm_global": 15, "residuos_global": 15}
OBJETIVO_EVAL = ["CA-HUAR-01_PM10", "CA-ILO-02_PM10"]        # estaciones que usan la LSTM global
ESTACIONES = list(wc.SERIES_GLOBAL)                           # incluye CA-CC-01 (solo entrena)
ALMACEN = "sqlite:///" + os.path.join(wc.CARPETA_CHECKPOINTS, "05_optuna.db").replace("\\", "/")
wl.fijar_semillas_keras()

# La serie de La Oroya entra con su configuración oficial (fuente "combinada", cortes A)
CC = "CA-CC-01_DIOXIDO_AZUFRE"
wc.SERIES[CC] = wc.SERIES_POR_FUENTE["combinada"][CC]
with open(os.path.join(wc.CARPETA_DATOS, "fuente_combinada", f"05_hiperparametros_{CC}.json"), encoding="utf-8") as f:
    PARAMS_PROPHET_CC = json.load(f)["prophet"]


def walk_forward_cc(ds: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward completo de Prophet de La Oroya: el mismo que usó 04c (caché de la fuente combinada)."""
    cfg = wc.SERIES[CC]
    h = hashlib.md5(json.dumps({"p": PARAMS_PROPHET_CC, "c": cfg, "f": "combinada"},
                               sort_keys=True).encode()).hexdigest()[:10]
    ruta = os.path.join(wc.CARPETA_DATOS, "fuente_combinada", f"07_prophet_wf_completo_{CC}_{h}.pkl")
    if os.path.exists(ruta):
        return pd.read_pickle(ruta)
    print("   (caché de La Oroya no encontrada: se recalcula el walk-forward)")
    return wh.walk_forward_prophet(ds, CC, PARAMS_PROPHET_CC)


def liberar_memoria():
    wl.keras.backend.clear_session()
    gc.collect()


datasets = {k: wc.cargar_dataset(k, f) for k, f in wc.SERIES_GLOBAL.items()}
for k, ds in datasets.items():
    print(f"{k}: {ds.index.min().date()} -> {ds.index.max().date()} | días con dato: {ds['OBJETIVO'].notna().sum()}")

# %% [markdown]
# ## 4d.1 Variables por estación (normalizadas con su propio entrenamiento) y alineación

# %%
ONEHOT = [f"est_{k.split('_')[0]}" for k in ESTACIONES]


def alinear(v_esc: pd.DataFrame, columnas: list, clave: str) -> np.ndarray:
    a = v_esc.reindex(columns=columnas).fillna(0.0)
    for k, c in zip(ESTACIONES, ONEHOT):
        a[c] = 1.0 if k == clave else 0.0
    return a.to_numpy("float32")


def variables_sola(ds, regimen):
    v = pd.DataFrame(index=ds.index)
    v["y_log"] = wc.a_escala_modelo(ds["OBJETIVO"])
    v["y_falta"] = ds["OBJETIVO"].isna().astype(float)
    return v.join(wl.variables_meteo_calendario(ds, regimen))


sola = {}
for k, ds in datasets.items():
    cfg = wc.SERIES[k]
    fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
    v = variables_sola(ds, cfg["regimen"])
    esc = wl.escalador_train(v, fin_train)
    sola[k] = {"v": v, "esc": esc, "v_esc": wl.imputar_escalar(v, esc), "fin_train": fin_train,
               "fin_val": pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1)}
COLS_SOLA = list(dict.fromkeys(c for k in ESTACIONES for c in sola[k]["v_esc"].columns))
for k in ESTACIONES:
    sola[k]["X_todo"] = alinear(sola[k]["v_esc"], COLS_SOLA, k)
print(f"LSTM global: {len(COLS_SOLA) + len(ONEHOT)} variables -> {COLS_SOLA + ONEHOT}")

residuos = {}
for k, ds in datasets.items():
    t0 = time.time()
    wf = walk_forward_cc(ds) if k == CC else wh.walk_forward_prophet(ds, k, wp.params_prophet(k))
    d = wh.Datos(ds, k, wf)
    residuos[k] = d
    print(f"{k}: walk-forward de Prophet ({wf['origen'].nunique()} orígenes, {time.time() - t0:.0f} s)")
COLS_RES = list(dict.fromkeys(c for k in ESTACIONES for c in residuos[k].v.columns))
for k, d in residuos.items():
    v_esc = pd.DataFrame(d.v_esc, index=d.v.index, columns=list(d.esc["media"].keys()))
    d.v_esc = alinear(v_esc, COLS_RES, k)
print(f"Residuos global: {len(COLS_RES) + len(ONEHOT)} variables -> {COLS_RES + ONEHOT}")

# %% [markdown]
# ## 4d.2 Muestras conjuntas

# %%
def muestras_sola(k, ventana):
    s = sola[k]
    y = s["v"]["y_log"].to_numpy()
    y_esc = (y - s["esc"]["media"]["y_log"]) / s["esc"]["desv"]["y_log"]
    obs = ~np.isnan(y)
    X, Y, orig = [], [], []
    for i in range(ventana - 1, len(y)):
        if obs[i - ventana + 1:i + 1].mean() < wl.MIN_FRACCION_OBSERVADA:
            continue
        obj = np.full(H, np.nan)
        fin = min(i + 1 + H, len(y))
        obj[:fin - i - 1] = y_esc[i + 1:fin]
        X.append(s["X_todo"][i - ventana + 1:i + 1])
        Y.append(obj)
        orig.append(s["v"].index[i])
    X, Y, orig = np.stack(X), np.stack(Y).astype("float32"), pd.DatetimeIndex(orig)
    ult = orig + pd.Timedelta(days=H)
    ok = ~np.isnan(Y).all(axis=1)
    sel = {"train": np.asarray((ult <= s["fin_train"]) & ok),
           "val": np.asarray((orig >= s["fin_train"]) & (ult <= s["fin_val"]) & ok),
           "train_val": np.asarray((ult <= s["fin_val"]) & ok)}
    return {"X": X, "Y": Y, "origen": orig, "sel": sel}


def conjunto(mu: dict, sel: str, campos=("X", "Y")):
    """Une las muestras de las tres estaciones (las de val: solo de las estaciones de destino si
    se pide para el objetivo de Optuna)."""
    return [np.concatenate([mu[k][c][mu[k]["sel"][sel]] for k in ESTACIONES]) for c in campos]


cache_sola, cache_res = {}, {}


def mu_sola(ventana):
    if ventana not in cache_sola:
        cache_sola[ventana] = {k: muestras_sola(k, ventana) for k in ESTACIONES}
    return cache_sola[ventana]


def mu_res(ventana):
    if ventana not in cache_res:
        cache_res[ventana] = {k: residuos[k].muestras(ventana) for k in ESTACIONES}
    return cache_res[ventana]


def a_log_sola(k, pred):
    e = sola[k]["esc"]
    return pred * e["desv"]["y_log"] + e["media"]["y_log"]


def rmse_medio(y_log, pred_log):
    return float(np.nanmean([wh.rmse_ug(y_log[:, h], pred_log[:, h]) for h in range(H)]))


# %% [markdown]
# ## 4d.3 Hiperparámetros (Optuna, SOLO validación)

# %%
def sugerir(trial, lr_min, lr_max, paciencia, epocas_max):
    return {"ventana": trial.suggest_categorical("ventana", [7, 14, 21, 28]),
            "unidades": trial.suggest_categorical("unidades", [16, 32, 64, 128]),
            "capas": trial.suggest_int("capas", 1, 2),
            "dropout": trial.suggest_float("dropout", 0.0, 0.5),
            "tasa_aprendizaje": trial.suggest_float("tasa_aprendizaje", lr_min, lr_max, log=True),
            "lote": trial.suggest_categorical("lote", [16, 32, 64]),
            "paciencia": paciencia, "epocas_max": epocas_max}


def estudio(nombre, por_defecto):
    e = optuna.create_study(direction="minimize", storage=ALMACEN, study_name=f"{nombre}_global",
                            load_if_exists=True, sampler=optuna.samplers.TPESampler(seed=wc.SEMILLA))
    if not e.trials:
        e.enqueue_trial(por_defecto)
    return e


def optimizar(e, objetivo, n):
    hechas = len([t for t in e.trials if t.state == optuna.trial.TrialState.COMPLETE])
    if hechas < n:
        e.optimize(objetivo, n_trials=n - hechas, gc_after_trial=True)
    t = e.trials_dataframe(attrs=("number", "value", "params")).sort_values("value")
    t.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"05_busqueda_{e.study_name}.csv"), sep=";", index=False)
    print(f"{e.study_name}: mejor RMSE val = {e.best_value:.3f} (por defecto {e.trials[0].value:.3f}) | {e.best_params}")


def obj_sola(trial):
    p = sugerir(trial, 1e-4, 3e-3, 30, 400)
    mu = mu_sola(p["ventana"])
    Xtr, Ytr = conjunto(mu, "train")
    Xva, Yva = conjunto(mu, "val")
    mA, _, _, ep = wl.entrenar_A_B(Xtr, Ytr, Xva, Yva, None, None, Xtr.shape[2], p)
    rm = []
    for k in OBJETIVO_EVAL:
        s = mu[k]["sel"]["val"]
        rm.append(rmse_medio(a_log_sola(k, mu[k]["Y"][s]), a_log_sola(k, mA.predict(mu[k]["X"][s], verbose=0))))
    trial.set_user_attr("epocas", ep)
    trial.set_user_attr("rmse_por_estacion", rm)
    del mA
    liberar_memoria()
    return float(np.mean(rm))


def obj_res(trial):
    p = sugerir(trial, 5e-5, 1e-3, 50, 500)
    mu = mu_res(p["ventana"])
    Xtr, Ftr, Ytr = conjunto(mu, "train", ("X", "F", "Y"))
    Xva, Fva, Yva = conjunto(mu, "val", ("X", "F", "Y"))
    mA, _, _, ep = wl.entrenar_A_B([Xtr, Ftr], Ytr, [Xva, Fva], Yva, None, None, Xtr.shape[2], p,
                                   n_futuro=Ftr.shape[1])
    rm = []
    for k in OBJETIVO_EVAL:
        va = wh.subconjunto(mu[k], mu[k]["sel"]["val"])
        r_hat = wh.corregir(mA, va, residuos[k])
        alfa, _ = wh.elegir_alfa(va["yhat"], r_hat, va["r_obj"])
        rm.append(rmse_medio(va["yhat"] + va["r_obj"], va["yhat"] + alfa[None, :] * r_hat))
    trial.set_user_attr("epocas", ep)
    trial.set_user_attr("rmse_por_estacion", rm)
    del mA
    liberar_memoria()
    return float(np.mean(rm))


claves_p = ("ventana", "unidades", "capas", "dropout", "tasa_aprendizaje", "lote")
e_sola = estudio("lstm", {k: v for k, v in {**wl.PARAMS_LSTM, "ventana": wl.VENTANA}.items() if k in claves_p})
optimizar(e_sola, obj_sola, N_PRUEBAS["lstm_global"])
e_res = estudio("residuos", {k: v for k, v in wl.PARAMS_HIBRIDO_V2.items() if k in claves_p})
optimizar(e_res, obj_res, N_PRUEBAS["residuos_global"])
P_SOLA = {**e_sola.best_params, "paciencia": 30, "epocas_max": 400}
P_RES = {**e_res.best_params, "paciencia": 50, "epocas_max": 500}
wc.guardar_json({"lstm_global": P_SOLA, "residuos_global": P_RES,
                 "rmse_val": {"lstm_global": e_sola.best_value, "lstm_global_defecto": e_sola.trials[0].value,
                              "residuos_global": e_res.best_value, "residuos_global_defecto": e_res.trials[0].value},
                 "nota": "Optuna solo con validación; RMSE medio h = 1..3 (µg/m³), promedio HUAR e ILO-02."},
                os.path.join(wc.CARPETA_CHECKPOINTS, "05_hiperparametros_global.json"))

# %% [markdown]
# ## 4d.4 Modelos A y B y predicciones (orígenes de val, test y extra de HUAR e ILO-02)

# %%
liberar_memoria()
wl.fijar_semillas_keras()
# a) LSTM global (sola)
mu = mu_sola(int(P_SOLA["ventana"]))
Xtr, Ytr = conjunto(mu, "train")
Xva, Yva = conjunto(mu, "val")
Xtv, Ytv = conjunto(mu, "train_val")
t0 = time.time()
mA, mB, hist_sola, ep_sola = wl.entrenar_A_B(Xtr, Ytr, Xva, Yva, Xtv, Ytv, Xtr.shape[2], P_SOLA)
print(f"LSTM global: épocas = {ep_sola} | {time.time() - t0:.0f} s")
for k in OBJETIVO_EVAL:
    m = mu[k]
    fd = {}
    for nombre, modelo, s in (("A", mA, m["sel"]["train"]), ("B", mB, m["sel"]["train_val"])):
        real = a_log_sola(k, m["Y"][s])
        pred = a_log_sola(k, modelo.predict(m["X"][s], verbose=0))
        fd[nombre] = [wc.factor_duan(real[:, h] - pred[:, h]) for h in range(H)]
    wf02 = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"04_prophet_walkforward_{k}.pkl"))
    ev = m["origen"].isin(pd.DatetimeIndex(wf02["origen"].unique()))
    orig, Xe = m["origen"][ev], m["X"][ev]
    usa_B = np.asarray(orig >= sola[k]["fin_val"])
    pred_log = np.empty((len(orig), H))
    for nombre, modelo, s in (("A", mA, ~usa_B), ("B", mB, usa_B)):
        if s.any():
            pred_log[s] = a_log_sola(k, modelo.predict(Xe[s], verbose=0))
    obs = datasets[k]["OBJETIVO"]
    filas = []
    for j, t in enumerate(orig):
        nombre = "B" if usa_B[j] else "A"
        for h in wc.HORIZONTES:
            f = t + pd.Timedelta(days=h)
            if f > obs.index.max():
                continue
            filas.append({"origen": t, "horizonte": h, "fecha_objetivo": f, "modelo_lstm": nombre,
                          "yhat_log": pred_log[j, h - 1], "factor_duan": fd[nombre][h - 1],
                          "observado": obs.get(f, np.nan)})
    p = pd.DataFrame(filas)
    p["particion"] = wc.asignar_particion(pd.DatetimeIndex(p["fecha_objetivo"]), k).to_numpy()
    p["valor"] = wc.a_escala_original(p["yhat_log"])
    p["valor_duan"] = wc.a_escala_original_duan(p["yhat_log"], p["factor_duan"])
    p["limite_inferior"] = np.nan
    p["limite_superior"] = np.nan
    wc.a_formato_bd(p, k).to_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"05_lstm_global_walkforward_{k}.pkl"))
    print(f"   {k}: {p['origen'].nunique()} orígenes | Duan A={np.round(fd['A'], 3)} B={np.round(fd['B'], 3)}")
carpeta = os.path.join(wc.CARPETA_MODELOS, f"GLOBAL_lstm_{VERSION_MODELO}")
os.makedirs(carpeta, exist_ok=True)
mA.save(os.path.join(carpeta, "lstm_global_A_train.keras"))
mB.save(os.path.join(carpeta, "lstm_global_B_train_val.keras"))
del mA, mB
liberar_memoria()

# b) Residuos global
wl.fijar_semillas_keras()
mu = mu_res(int(P_RES["ventana"]))
Xtr, Ftr, Ytr = conjunto(mu, "train", ("X", "F", "Y"))
Xva, Fva, Yva = conjunto(mu, "val", ("X", "F", "Y"))
Xtv, Ftv, Ytv = conjunto(mu, "train_val", ("X", "F", "Y"))
t0 = time.time()
mA, mB, hist_res, ep_res = wl.entrenar_A_B([Xtr, Ftr], Ytr, [Xva, Fva], Yva, [Xtv, Ftv], Ytv, Xtr.shape[2], P_RES,
                                           n_futuro=Ftr.shape[1])
print(f"Residuos global: épocas = {ep_res} | {time.time() - t0:.0f} s")
for k in OBJETIVO_EVAL:
    d = residuos[k]
    ev = wh.subconjunto(mu[k], mu[k]["sel"]["eval"])
    usa_B = np.asarray(ev["origen"] >= d.fin_val)
    corr = np.empty((len(ev["origen"]), H))
    for modelo, s in ((mA, ~usa_B), (mB, usa_B)):
        if s.any():
            corr[s] = wh.corregir(modelo, wh.subconjunto(ev, s), d)
    obs = datasets[k]["OBJETIVO"]
    filas = []
    for j, t in enumerate(ev["origen"]):
        for h in wc.HORIZONTES:
            f = t + pd.Timedelta(days=h)
            if f > obs.index.max():
                continue
            filas.append({"origen": t, "horizonte": h, "fecha_objetivo": f, "prophet_log": ev["yhat"][j, h - 1],
                          "correccion_log": corr[j, h - 1], "lower_log": ev["lower"][j, h - 1],
                          "upper_log": ev["upper"][j, h - 1], "observado": obs.get(f, np.nan),
                          "modelo_lstm": "B" if usa_B[j] else "A"})
    p = pd.DataFrame(filas)
    p.to_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_residuos_global_walkforward_{k}.pkl"))
    print(f"   {k}: {p['origen'].nunique()} orígenes")
mA.save(os.path.join(carpeta, "residuos_global_A_train.keras"))
mB.save(os.path.join(carpeta, "residuos_global_B_train_val.keras"))
wc.guardar_json({
    "estaciones": ESTACIONES, "estaciones_evaluadas": OBJETIVO_EVAL,
    "normalizacion": "por estación, media y desviación de su propio entrenamiento (<= 2024-12-31)",
    "variables_lstm_global": COLS_SOLA + ONEHOT, "variables_residuos_global": COLS_RES + ONEHOT,
    "hiperparametros": {"lstm_global": P_SOLA, "residuos_global": P_RES},
    "epocas_optimas": {"lstm_global": ep_sola, "residuos_global": ep_res},
    "escaladores_sola": {k: sola[k]["esc"] for k in ESTACIONES},
    "escaladores_residuos": {k: residuos[k].esc for k in ESTACIONES},
    "semilla": wc.SEMILLA, "versiones": wc.versiones_librerias()}, os.path.join(carpeta, "metadatos.json"))
print(f"Guardado en {carpeta}")
