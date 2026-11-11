# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Notebook 3: LSTM sola (modelo base)
#
# Estructura:
# - 3.1 Datos, cortes y variables de entrada
# - 3.2 Imputación y escalado (ajustados SOLO con train)
# - 3.3 Ventanas deslizantes (muestras origen -> horizontes)
# - 3.4 Modelo Keras y entrenamiento
# - 3.5 Predicciones en val, test y extra + corrección de Duan
# - 3.6 Comparación con persistencia y Prophet (métricas y alertas)
# - 3.7 Figuras
# - 3.8 Guardado
#
# Decisiones:
# - Escala log(1 + x) para el contaminante; se reporta "LSTM" y "LSTM+Duan".
# - Pronóstico directo multi-horizonte: una salida por horizonte (h = 1..H).
# - Entradas: ventana de VENTANA días hasta el origen t (inclusive): contaminante rezagado,
#   marca de dato faltante, meteorología del OEFA rezagada (nunca la del día a predecir),
#   calendario y, en CA-CC-01, OPERACION_CAUSAL (solo usa días <= t).
# - Faltantes en las entradas: relleno hacia adelante de hasta LIMITE_FFILL días (usa solo el
#   pasado) y luego la media de train. En el objetivo NO se imputa: la pérdida ignora los NaN.
# - Modelo A: entrenado con train, con parada temprana en val -> predice los orígenes
#   anteriores al fin de val. Modelo B: reentrenado con train + val durante las épocas óptimas
#   de A -> predice los orígenes desde el fin de val (test y extra). Así la LSTM, igual que el
#   walk-forward de Prophet, usa los datos disponibles hasta el origen.
#   Nota: las métricas de val de la LSTM son algo optimistas (val se usó para la parada temprana).

# %%
import os
import time
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import wayra_comun as wc
import wayra_lstm as wl  # configura TensorFlow/Keras (semillas, determinismo, pérdida enmascarada)

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

# ------------------------------------------------------------------
# CONFIGURACIÓN (valores compartidos en wayra_lstm.py)
# ------------------------------------------------------------------
VERSION_MODELO = "v1"
VENTANA = wl.VENTANA
LIMITE_FFILL = wl.LIMITE_FFILL
MIN_FRACCION_OBSERVADA = wl.MIN_FRACCION_OBSERVADA
PARAMS_LSTM = wl.PARAMS_LSTM   # por defecto; se ajustarán en 05-HIPERPARAMETROS.py
H = wl.H

wl.fijar_semillas_keras()
print("Versiones:", wc.versiones_librerias())


def guardar_fig(nombre: str):
    plt.savefig(os.path.join(wc.CARPETA_FIGURAS, f"{nombre}.png"), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close("all")


# %% [markdown]
# ## 3.1 Datos, cortes y variables de entrada

# %%
def construir_variables(ds: pd.DataFrame, regimen: bool) -> pd.DataFrame:
    """Variables diarias de entrada (sin imputar). Todas se usan solo hasta el origen t."""
    v = pd.DataFrame(index=ds.index)
    v["y_log"] = wc.a_escala_modelo(ds["OBJETIVO"])
    v["y_falta"] = ds["OBJETIVO"].isna().astype(float)
    return v.join(wl.variables_meteo_calendario(ds, regimen))


datasets = {clave: wc.cargar_dataset(clave) for clave in wc.SERIES}
variables = {clave: construir_variables(ds, wc.SERIES[clave]["regimen"])
             for clave, ds in datasets.items()}
for clave, v in variables.items():
    print(f"{clave}: {v.shape[1]} variables de entrada -> {list(v.columns)}")

# %% [markdown]
# ## 3.2 Imputación y escalado (estadísticos SOLO de train)

# %%
matrices, escaladores = {}, {}
for clave, v in variables.items():
    fin_train = pd.Timestamp(wc.SERIES[clave]["inicio_val"]) - pd.Timedelta(days=1)
    escaladores[clave] = wl.escalador_train(v, fin_train)
    matrices[clave] = wl.imputar_escalar(v, escaladores[clave])
    print(f"{clave}: faltantes antes de imputar = {v.isna().mean().mean() * 100:.1f}% "
          f"(la marca y_falta conserva la información del hueco)")

# %% [markdown]
# ## 3.3 Ventanas deslizantes
#
# Muestra con origen t: X = variables de t-VENTANA+1 .. t; Y = y_log escalado de t+1 .. t+H.

# %%
def construir_muestras(escalada: pd.DataFrame, v: pd.DataFrame, esc: dict, ventana: int = VENTANA):
    X_todo = escalada.to_numpy(dtype="float32")
    y_esc = ((v["y_log"] - esc["media"]["y_log"]) / esc["desv"]["y_log"]).to_numpy("float32")
    observado = (~v["y_log"].isna()).to_numpy()
    n = len(escalada)
    origenes, X, Y = [], [], []
    for i in range(ventana - 1, n):
        if observado[i - ventana + 1:i + 1].mean() < MIN_FRACCION_OBSERVADA:
            continue
        objetivo = np.full(H, np.nan, dtype="float32")
        fin = min(i + 1 + H, n)
        objetivo[:fin - i - 1] = y_esc[i + 1:fin]
        origenes.append(escalada.index[i])
        X.append(X_todo[i - ventana + 1:i + 1])
        Y.append(objetivo)
    return pd.DatetimeIndex(origenes), np.stack(X), np.stack(Y)


muestras, params = {}, {}
for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    params[clave] = wl.params_lstm(clave, "lstm")
    origenes, X, Y = construir_muestras(matrices[clave], variables[clave], escaladores[clave],
                                        int(params[clave]["ventana"]))
    ultimo_objetivo = origenes + pd.Timedelta(days=H)
    fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
    fin_val = pd.Timestamp(cfg["inicio_test"]) - pd.Timedelta(days=1)
    con_objetivo = ~np.isnan(Y).all(axis=1)
    sel = {
        "train": (ultimo_objetivo <= fin_train) & con_objetivo,
        "val": (origenes >= fin_train) & (ultimo_objetivo <= fin_val) & con_objetivo,
        "train_val": (ultimo_objetivo <= fin_val) & con_objetivo,
    }
    muestras[clave] = {"origenes": origenes, "X": X, "Y": Y, "sel": sel,
                       "fin_train": fin_train, "fin_val": fin_val}
    print(f"{clave}: X={X.shape} | muestras train={sel['train'].sum()}, val={sel['val'].sum()}, "
          f"train+val={sel['train_val'].sum()}")

# %% [markdown]
# ## 3.4 Modelo Keras y entrenamiento
#
# Arquitectura y entrenamiento en wayra_lstm.py: crear_lstm y entrenar_A_B (MSE enmascarado).

# %%
modelos, historiales, epocas_opt = {}, {}, {}
for clave, mu in muestras.items():
    t0 = time.time()
    s = mu["sel"]
    mA, mB, hist, epocas = wl.entrenar_A_B(
        mu["X"][s["train"]], mu["Y"][s["train"]], mu["X"][s["val"]], mu["Y"][s["val"]],
        mu["X"][s["train_val"]], mu["Y"][s["train_val"]], mu["X"].shape[2], params[clave])
    modelos[clave] = {"A": mA, "B": mB}
    historiales[clave] = hist
    epocas_opt[clave] = epocas
    print(f"{clave}: épocas óptimas = {epocas} | pérdida val = {min(hist['val_loss']):.4f} "
          f"| {time.time() - t0:.0f} s")


# %% [markdown]
# ## 3.5 Predicciones en val, test y extra + corrección de Duan
#
# Los orígenes son los mismos del walk-forward de Prophet. Orígenes anteriores al fin de val
# -> modelo A; desde el fin de val -> modelo B. El factor de Duan de cada modelo (y horizonte)
# se calcula con los residuos en sus propios datos de entrenamiento.

# %%
def a_log(pred_esc: np.ndarray, esc: dict) -> np.ndarray:
    return pred_esc * esc["desv"]["y_log"] + esc["media"]["y_log"]


predicciones = {}
factores_duan = {}
for clave, mu in muestras.items():
    esc = escaladores[clave]
    y_log = variables[clave]["y_log"]
    obs = datasets[clave]["OBJETIVO"]

    # Factores de Duan por modelo y horizonte (residuos en los datos de entrenamiento)
    fd = {}
    for nombre, sel in (("A", mu["sel"]["train"]), ("B", mu["sel"]["train_val"])):
        pred = a_log(modelos[clave][nombre].predict(mu["X"][sel], verbose=0), esc)
        real = a_log(mu["Y"][sel], esc)
        fd[nombre] = [wc.factor_duan(real[:, k] - pred[:, k]) for k in range(H)]
    factores_duan[clave] = fd

    # Orígenes a evaluar: los del walk-forward de Prophet
    wf_prophet = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"04_prophet_walkforward_{clave}.pkl"))
    evaluar = mu["origenes"].isin(pd.DatetimeIndex(wf_prophet["origen"].unique()))
    orig = mu["origenes"][evaluar]
    Xe = mu["X"][evaluar]
    usa_B = orig >= mu["fin_val"]
    pred_log = np.empty((len(orig), H), dtype="float64")
    for nombre, m in (("A", ~usa_B), ("B", usa_B)):
        if m.any():
            pred_log[m] = a_log(modelos[clave][nombre].predict(Xe[m], verbose=0), esc)

    filas = []
    ultimo = obs.index.max()
    for j, t in enumerate(orig):
        nombre = "B" if usa_B[j] else "A"
        for h in wc.HORIZONTES:
            f = t + pd.Timedelta(days=h)
            if f > ultimo:
                continue
            filas.append({"origen": t, "horizonte": h, "fecha_objetivo": f, "modelo_lstm": nombre,
                          "yhat_log": pred_log[j, h - 1], "factor_duan": fd[nombre][h - 1],
                          "observado": obs.get(f, np.nan)})
    p = pd.DataFrame(filas)
    p["particion"] = wc.asignar_particion(pd.DatetimeIndex(p["fecha_objetivo"]), clave).to_numpy()
    p["valor"] = wc.a_escala_original(p["yhat_log"])
    p["valor_duan"] = wc.a_escala_original_duan(p["yhat_log"], p["factor_duan"])
    p["limite_inferior"] = np.nan  # la LSTM sola no tiene intervalo
    p["limite_superior"] = np.nan
    predicciones[clave] = p
    print(f"{clave}: {p['origen'].nunique()} orígenes ({len(orig) / wf_prophet['origen'].nunique():.0%} "
          f"de los de Prophet) | Duan A={np.round(fd['A'], 3)}, B={np.round(fd['B'], 3)}")

# %% [markdown]
# ## 3.6 Comparación con persistencia y Prophet
#
# Todos los modelos se evalúan sobre los mismos pares (origen, horizonte).

# %%
tablas_met, tablas_ale = [], []
for clave in wc.SERIES:
    cont = wc.SERIES[clave]["contaminante"]
    modelos_cmp = wc.predicciones_base(clave, datasets[clave])
    p = predicciones[clave]
    modelos_cmp["LSTM"] = p
    modelos_cmp["LSTM+Duan"] = p.assign(valor=p["valor_duan"])
    met, ale = wc.comparar_modelos(modelos_cmp, cont)
    met.insert(0, "serie", clave)
    ale.insert(0, "serie", clave)
    tablas_met.append(met)
    tablas_ale.append(ale)
metricas = pd.concat(tablas_met, ignore_index=True)
alertas = pd.concat(tablas_ale, ignore_index=True)
metricas.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, "05_metricas_lstm.csv"),
                sep=";", index=False, decimal=",")
alertas.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, "05_alertas_lstm.csv"),
               sep=";", index=False, decimal=",")

cols = ["serie", "particion", "horizonte", "modelo", "n", "RMSE", "MAE", "R2",
        "acierto_categoria", "recall_Moderada", "recall_Mala"]
print(metricas[metricas["particion"].isin(["test", "extra"])][cols].round(3).to_string(index=False))

# %% [markdown]
# ### Detección de días "Moderada o peor" y de superación del ECA (prueba)

# %%
for clave in wc.SERIES:
    print(f"\n=== {clave} - test: recall y precisión de las alertas ===")
    print(wc.resumen_alertas(alertas[alertas["serie"] == clave], "test").to_string())

# %%
# Matriz de confusión INCA en test (h = 1): LSTM+Duan
for clave, p in predicciones.items():
    cont = wc.SERIES[clave]["contaminante"]
    sel = p[(p["particion"] == "test") & (p["horizonte"] == 1)]
    print(f"\n{clave} - test, h=1, LSTM+Duan (filas: observada, columnas: predicha)")
    print(wc.matriz_confusion_inca(sel["observado"], sel["valor_duan"], cont).to_string())

# %% [markdown]
# ## 3.7 Figuras

# %%
# (a) Curvas de entrenamiento del modelo A
fig, axes = plt.subplots(1, len(wc.SERIES), figsize=(5 * len(wc.SERIES), 3.4), squeeze=False)
for ax, clave in zip(axes[0], wc.SERIES):
    cfg = wc.SERIES[clave]
    h = historiales[clave]
    ax.plot(h["loss"], label="Entrenamiento", color="#2F5597")
    ax.plot(h["val_loss"], label="Validación", color="#C55A11")
    ax.axvline(epocas_opt[clave] - 1, color="black", ls=":", lw=0.8, label="Época óptima")
    ax.set_title(f"{wc.NOMBRE_VAR[cfg['contaminante']]} - {cfg['estacion']}")
    ax.set_xlabel("Época")
    ax.set_ylabel("MSE (escala log estandarizada)")
    ax.legend(fontsize=8)
fig.suptitle("Curvas de aprendizaje de la LSTM", y=1.03)
plt.tight_layout()
guardar_fig("fig14_lstm_curvas_aprendizaje")

# %%
# (b) Prueba, h = 1: observado vs persistencia, Prophet+Duan y LSTM+Duan
for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    cont = cfg["contaminante"]
    base = wc.predicciones_base(clave, datasets[clave])
    series_plot = {
        "Persistencia": base["Persistencia"],
        "Prophet+Duan": base["Prophet+Duan"],
        "LSTM+Duan": predicciones[clave].assign(valor=predicciones[clave]["valor_duan"]),
    }
    fig, ax = plt.subplots(figsize=(13, 4.2))
    obs = None
    for nombre, df in series_plot.items():
        d = (df[(df["horizonte"] == 1) & (df["particion"] == "test")]
             .set_index("fecha_objetivo").sort_index()[["valor", "observado"]].asfreq("D"))  # huecos visibles
        obs = d["observado"] if obs is None else obs
        ax.plot(d.index, d["valor"], lw=1.0, color=wc.COLORES_MODELO[nombre], label=nombre,
                ls=":" if nombre == "Persistencia" else "-")
    ax.plot(obs.index, obs.values, color="#404040", lw=1.1, label="Observado", zorder=0)
    ax.axhline(wc.ECA_24H[cont], color="#D7263D", ls="--", lw=1,
               label=f"ECA 24 h ({wc.ECA_24H[cont]} {wc.UNIDAD})")
    ax.axhline(wc.ECA_24H[cont] * 0.5, color="#F2C12E", ls="-.", lw=0.9, label="INCA 50 (Buena/Moderada)")
    ax.set_title(f"{wc.NOMBRE_VAR[cont]} - {cfg['estacion']} "
                 f"({wc.NOMBRE_DEP[cfg['departamento']]}): prueba, horizonte de 1 día")
    ax.set_ylabel(f"Promedio diario ({wc.UNIDAD})")
    ax.set_xlabel("Fecha")
    ax.legend(fontsize=8, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.16), frameon=False)
    plt.tight_layout()
    guardar_fig(f"fig15_lstm_test_{clave}")

# %%
# (c) RMSE por horizonte en test: todos los modelos
sel = metricas[metricas["particion"] == "test"]
fig, axes = plt.subplots(1, len(wc.SERIES), figsize=(5.5 * len(wc.SERIES), 3.8), squeeze=False)
for ax, clave in zip(axes[0], wc.SERIES):
    cfg = wc.SERIES[clave]
    d = sel[sel["serie"] == clave].pivot(index="horizonte", columns="modelo", values="RMSE")
    d = d[[m for m in wc.COLORES_MODELO if m in d.columns]]
    d.plot(kind="bar", ax=ax, color=wc.COLORES_MODELO, rot=0, width=0.8)
    ax.set_title(f"{wc.NOMBRE_VAR[cfg['contaminante']]} - {cfg['estacion']}")
    ax.set_xlabel("Horizonte (días)")
    ax.set_ylabel(f"RMSE ({wc.UNIDAD})")
    ax.legend(title="", fontsize=7)
fig.suptitle("RMSE en el conjunto de prueba por horizonte", y=1.03)
plt.tight_layout()
guardar_fig("fig16_rmse_horizonte_modelos")

# %%
# (d) Recall de alertas "Moderada o peor" en test (h = 1) por modelo y regla
a = alertas[(alertas["particion"] == "test") & (alertas["horizonte"] == 1)
            & (alertas["umbral"] == "moderada_o_peor")].copy()
a["etiqueta"] = a["modelo"] + np.where(a["regla"] == "intervalo", "\n(intervalo)", "")
fig, axes = plt.subplots(1, len(wc.SERIES), figsize=(5.5 * len(wc.SERIES), 3.8), squeeze=False)
for ax, clave in zip(axes[0], wc.SERIES):
    cfg = wc.SERIES[clave]
    d = a[a["serie"] == clave]
    colores = [wc.COLORES_MODELO[m] for m in d["modelo"]]
    ax.bar(d["etiqueta"], d["recall"].fillna(0), color=colores,
           hatch=None, edgecolor=["black" if r == "intervalo" else "none" for r in d["regla"]])
    for x, (r, pr) in enumerate(zip(d["recall"], d["precision"])):
        ax.text(x, (0 if np.isnan(r) else r) + 0.02, f"R={r:.2f}\nP={pr:.2f}" if not np.isnan(pr)
                else f"R={0 if np.isnan(r) else r:.2f}", ha="center", fontsize=7)
    dias = int(d["dias_reales"].iloc[0]) if len(d) else 0
    ax.set_title(f"{wc.NOMBRE_VAR[cfg['contaminante']]} - {cfg['estacion']} ({dias} días reales)")
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("Recall")
    ax.tick_params(axis="x", labelsize=7, rotation=0)
fig.suptitle('Detección de días "Moderada o peor" en la prueba (h = 1). R = recall, P = precisión', y=1.03)
plt.tight_layout()
guardar_fig("fig17_recall_alertas_test")

# %% [markdown]
# ## 3.8 Guardado
#
# - checkpoints/05_lstm_walkforward_<serie>.pkl/.csv : predicciones (formato tabla prediccion).
# - modelos/<serie>_lstm_v1/ : modelos A y B (.keras), escalador y metadatos.

# %%
for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    salida = wc.a_formato_bd(predicciones[clave], clave)
    salida.to_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"05_lstm_walkforward_{clave}.pkl"))
    salida.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"05_lstm_walkforward_{clave}.csv"),
                  sep=";", index=False)
    carpeta = os.path.join(wc.CARPETA_MODELOS, f"{clave}_lstm_{VERSION_MODELO}")
    os.makedirs(carpeta, exist_ok=True)
    modelos[clave]["A"].save(os.path.join(carpeta, "lstm_A_train.keras"))
    modelos[clave]["B"].save(os.path.join(carpeta, "lstm_B_train_val.keras"))
    wc.guardar_json(escaladores[clave], os.path.join(carpeta, "escalador.json"))
    wc.guardar_json({
        "serie": clave, "version": VERSION_MODELO, "config_serie": cfg,
        "variables": list(variables[clave].columns), "ventana": params[clave]["ventana"], "horizontes": wc.HORIZONTES,
        "limite_ffill": LIMITE_FFILL, "min_fraccion_observada": MIN_FRACCION_OBSERVADA,
        "hiperparametros": params[clave], "epocas_optimas": epocas_opt[clave],
        "factores_duan": factores_duan[clave],
        "escala": "log1p estandarizado; valor = expm1(yhat_log); con Duan: exp(yhat_log)*factor - 1",
        "semilla": wc.SEMILLA, "versiones": wc.versiones_librerias(),
    }, os.path.join(carpeta, "metadatos.json"))
    print(f"{clave}: guardado en {carpeta}")

# %% [markdown]
# ## Resumen de la fase
#
# - LSTM multi-horizonte con historia de VENTANA días (contaminante, meteorología rezagada,
#   calendario y régimen causal), entrenada en escala log y evaluada con y sin Duan.
# - Comparación sobre los mismos pares (origen, horizonte) con la persistencia y Prophet
#   (05_metricas_lstm.csv, 05_alertas_lstm.csv).
