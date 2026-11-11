# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Notebook 2: Prophet (modelo base y componente del híbrido)
#
# Estructura:
# - 2.1 Datos y cortes cronológicos (train / val / test)
# - 2.2 Configuración de Prophet
# - 2.3 Ajuste sobre train: componentes y residuos (entrada de la LSTM del híbrido)
# - 2.4 Validación de origen móvil (walk-forward) en val, test y extra
# - 2.5 Métricas por partición y horizonte (Prophet vs persistencia)
# - 2.6 Figuras
# - 2.7 Guardado de modelos y predicciones
#
# Decisiones:
# - Escala del modelo: log(1 + x). Las métricas se calculan en µg/m³ (expm1).
# - Estacionalidad semanal y anual. En CA-CC-01, OPERACION como regresor aditivo.
# - Prophet se ajusta con la OPERACION del propio día (mediana móvil centrada). Al
#   pronosticar, el valor futuro de OPERACION NO se conoce: se usa el ÚLTIMO ESTADO
#   CONOCIDO en el origen, calculado de forma causal (OPERACION_CAUSAL, solo días <= t)
#   y se supone constante durante el horizonte (supuesto documentado).
# - Walk-forward: en cada origen t se pronostica t+1..t+H con un modelo ajustado solo
#   con datos <= t. Prophet se reentrena cada REENTRENAR_CADA días (ventana expansiva).
# - No se imputa: Prophet ignora los días sin dato al ajustar.
# - Corrección de Duan: volver de log con expm1 da la mediana y subestima la media. Se
#   reporta Prophet sin corrección y "Prophet+Duan" (factor = media de exp(residuo) en los
#   datos con que se ajustó cada modelo). El intervalo no se corrige: sus límites son cuantiles.
# - Reglas de alerta: 'puntual' (valor predicho > umbral) e 'intervalo' (límite superior >
#   umbral), para los umbrales Moderada o peor (INCA > 50) y superación del ECA (INCA > 100).

# %%
import os
import time
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from prophet.serialize import model_to_json

import wayra_comun as wc
import wayra_prophet as wp
from wayra_prophet import ajustar_prophet, predecir, factor_duan_modelo

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

# ------------------------------------------------------------------
# CONFIGURACIÓN (valores compartidos en wayra_prophet.py)
# ------------------------------------------------------------------
VERSION_MODELO = "v1"
REENTRENAR_CADA = wp.REENTRENAR_CADA   # días entre reentrenamientos en el walk-forward
INTERVALO = wp.INTERVALO               # nivel del intervalo de incertidumbre de Prophet
MUESTRAS_INCERTIDUMBRE = wp.MUESTRAS_INCERTIDUMBRE
PARAMS_PROPHET = wp.PARAMS_PROPHET     # por defecto; se ajustarán en 05-HIPERPARAMETROS.py

wc.fijar_semillas()
print("Versiones:", wc.versiones_librerias())


def guardar_fig(nombre: str):
    plt.savefig(os.path.join(wc.CARPETA_FIGURAS, f"{nombre}.png"), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close("all")


# %% [markdown]
# ## 2.1 Datos y cortes cronológicos

# %%
datasets = {clave: wc.cargar_dataset(clave) for clave in wc.SERIES}
for clave, ds in datasets.items():
    print(f"\n=== {clave} ===")
    print(wc.resumen_particiones(ds).to_string())

# %% [markdown]
# ## 2.2 Configuración de Prophet
#
# Las funciones de ajuste y predicción están en wayra_prophet.py (compartidas con el híbrido):
# crear_prophet, ajustar_prophet, predecir, yhat_puntual y factor_duan_modelo.

# %%
print(f"Hiperparámetros: { {k: wp.params_prophet(k) for k in wc.SERIES} } | intervalo: {INTERVALO:.0%} | "
      f"reentrenamiento cada {REENTRENAR_CADA} días")

# %% [markdown]
# ## 2.3 Ajuste sobre train: componentes y residuos
#
# Los residuos de train (en escala log) son la entrada de la LSTM en el híbrido (04).

# %%
modelos_train = {}
ajustes_train = {}
for clave, ds in datasets.items():
    cfg = wc.SERIES[clave]
    fin_train = pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1)
    t0 = time.time()
    m = ajustar_prophet(ds, fin_train, cfg["regimen"], wp.params_prophet(clave))
    modelos_train[clave] = m

    tr = ds.loc[:fin_train]
    op = tr["OPERACION"].ffill().bfill().to_numpy() if cfg["regimen"] else None
    p = predecir(m, tr.index, op)
    aj = pd.DataFrame({
        "observado": tr["OBJETIVO"], "observado_log": wc.a_escala_modelo(tr["OBJETIVO"]),
        "yhat_log": p["yhat"], "yhat_lower_log": p["yhat_lower"], "yhat_upper_log": p["yhat_upper"],
        "tendencia_log": p["trend"], "semanal_log": p["weekly"], "anual_log": p["yearly"],
    })
    if cfg["regimen"]:
        aj["OPERACION"] = tr["OPERACION"]
        aj["efecto_operacion_log"] = p["OPERACION"]
    aj["valor"] = wc.a_escala_original(aj["yhat_log"])
    aj["residuo_log"] = aj["observado_log"] - aj["yhat_log"]
    fd = wc.factor_duan(aj["residuo_log"])
    aj["valor_duan"] = wc.a_escala_original_duan(aj["yhat_log"], fd)
    aj.attrs["factor_duan"] = fd
    ajustes_train[clave] = aj

    met = wc.metricas_regresion(aj["observado"], aj["valor"])
    met_d = wc.metricas_regresion(aj["observado"], aj["valor_duan"])
    print(f"{clave}: ajuste en train ({time.time() - t0:.1f} s) | n={met['n']} | "
          f"RMSE={met['RMSE']:.2f} | MAE={met['MAE']:.2f} | R²={met['R2']:.3f} {wc.UNIDAD} | "
          f"residuo log: media={aj['residuo_log'].mean():.3f}, desv.={aj['residuo_log'].std():.3f}")
    print(f"   Factor de Duan = {fd:.3f} | con corrección: RMSE={met_d['RMSE']:.2f}, "
          f"MAE={met_d['MAE']:.2f}, R²={met_d['R2']:.3f} | media observada={aj['observado'].mean():.1f}, "
          f"predicha={aj['valor'].mean():.1f} (sin), {aj['valor_duan'].mean():.1f} (Duan)")
    if cfg["regimen"]:
        efecto = aj.groupby("OPERACION")["efecto_operacion_log"].mean()
        print(f"   Efecto de OPERACION (log): detenida={efecto.get(0.0, np.nan):+.3f}, "
              f"operando={efecto.get(1.0, np.nan):+.3f} -> factor x"
              f"{np.exp(efecto.get(1.0, 0) - efecto.get(0.0, 0)):.1f} en (1 + concentración)")

# %% [markdown]
# ## 2.4 Validación de origen móvil (walk-forward)
#
# Orígenes t desde el día anterior al inicio de val hasta el penúltimo día con datos.
# Cada predicción se etiqueta con la partición de su FECHA OBJETIVO.

# %%
def walk_forward(ds: pd.DataFrame, clave: str, params=PARAMS_PROPHET,
                 cada=REENTRENAR_CADA, horizontes=wc.HORIZONTES) -> pd.DataFrame:
    cfg = wc.SERIES[clave]
    regimen = cfg["regimen"]
    hmax = max(horizontes)
    ultimo = ds.index.max()
    origenes = pd.date_range(pd.Timestamp(cfg["inicio_val"]) - pd.Timedelta(days=1),
                             ultimo - pd.Timedelta(days=1), freq="D")
    # Último estado de operación conocido en cada origen (solo información <= t)
    estado = ds["OPERACION_CAUSAL"].ffill() if regimen else None
    obs = ds["OBJETIVO"]
    filas = []
    for i in range(0, len(origenes), cada):
        bloque = origenes[i:i + cada]
        m = ajustar_prophet(ds, bloque[0], regimen, params)
        fd = factor_duan_modelo(m)
        fechas = pd.date_range(bloque[0] + pd.Timedelta(days=1),
                               bloque[-1] + pd.Timedelta(days=hmax), freq="D")
        if regimen:
            pred = {e: predecir(m, fechas, e) for e in (0.0, 1.0)}
        else:
            pred = {None: predecir(m, fechas)}
        for t in bloque:
            e = estado.get(t, np.nan) if regimen else None
            if regimen and np.isnan(e):
                continue
            p = pred[e]
            for h in horizontes:
                f = t + pd.Timedelta(days=h)
                if f > ultimo:
                    continue
                filas.append({"origen": t, "horizonte": h, "fecha_objetivo": f,
                              "operacion_supuesta": e,
                              "yhat_log": p.at[f, "yhat"],
                              "yhat_lower_log": p.at[f, "yhat_lower"],
                              "yhat_upper_log": p.at[f, "yhat_upper"],
                              "factor_duan": fd,
                              "observado": obs.get(f, np.nan)})
    wf = pd.DataFrame(filas)
    wf["particion"] = wc.asignar_particion(pd.DatetimeIndex(wf["fecha_objetivo"]), clave).to_numpy()
    wf["valor"] = wc.a_escala_original(wf["yhat_log"])
    wf["valor_duan"] = wc.a_escala_original_duan(wf["yhat_log"], wf["factor_duan"])
    wf["limite_inferior"] = wc.a_escala_original(wf["yhat_lower_log"])
    wf["limite_superior"] = wc.a_escala_original(wf["yhat_upper_log"])
    wf["observado_log"] = wc.a_escala_modelo(wf["observado"])
    wf["residuo_log"] = wf["observado_log"] - wf["yhat_log"]
    return wf


predicciones = {}
for clave, ds in datasets.items():
    t0 = time.time()
    predicciones[clave] = walk_forward(ds, clave, wp.params_prophet(clave))
    wf = predicciones[clave]
    print(f"{clave}: {wf['origen'].nunique()} orígenes, {len(wf):,} predicciones "
          f"({time.time() - t0:.0f} s) | factor de Duan: {wf['factor_duan'].min():.3f} - "
          f"{wf['factor_duan'].max():.3f}")
    salida = wc.a_formato_bd(wf, clave)
    salida.to_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"04_prophet_walkforward_{clave}.pkl"))
    salida.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"04_prophet_walkforward_{clave}.csv"),
                  sep=";", index=False)

# %% [markdown]
# ## 2.5 Métricas por partición y horizonte: Persistencia vs Prophet vs Prophet+Duan
#
# Los tres modelos se comparan sobre los mismos pares (origen, horizonte). La persistencia
# (valor del último día observado) usa los mismos orígenes y fechas objetivo.

# %%
tablas_met, tablas_ale = [], []
for clave in wc.SERIES:
    cont = wc.SERIES[clave]["contaminante"]
    met, ale = wc.comparar_modelos(wc.predicciones_base(clave, datasets[clave]), cont)
    met.insert(0, "serie", clave)
    ale.insert(0, "serie", clave)
    tablas_met.append(met)
    tablas_ale.append(ale)
metricas = pd.concat(tablas_met, ignore_index=True)
alertas = pd.concat(tablas_ale, ignore_index=True)
metricas.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, "04_metricas_prophet.csv"),
                sep=";", index=False, decimal=",")
alertas.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, "04_alertas_prophet.csv"),
               sep=";", index=False, decimal=",")

cols = ["serie", "particion", "horizonte", "modelo", "n", "RMSE", "MAE", "R2",
        "acierto_categoria", "recall_Moderada", "recall_Mala", "cobertura_intervalo"]
print(metricas[cols].round(3).to_string(index=False))

# %% [markdown]
# ### Detección de días "Moderada o peor" y de superación del ECA
#
# - dias_reales: días del período con la categoría real (para dimensionar el recall).
# - Regla puntual: alerta si el valor predicho supera el umbral.
# - Regla intervalo: alerta si el límite superior del intervalo de Prophet supera el umbral.

# %%
for clave in wc.SERIES:
    for part in ("val", "test"):
        a = alertas[alertas["serie"] == clave]
        print(f"\n=== {clave} - {part}: recall y precisión de las alertas ===")
        print(wc.resumen_alertas(a, part).to_string())

# %%
# Matriz de confusión INCA en test (horizonte 1): Prophet sin y con corrección de Duan
for clave, wf in predicciones.items():
    cont = wc.SERIES[clave]["contaminante"]
    sel = wf[(wf["particion"] == "test") & (wf["horizonte"] == 1)]
    for etiqueta, col in (("Prophet", "valor"), ("Prophet+Duan", "valor_duan")):
        print(f"\n{clave} - test, h=1, {etiqueta} (filas: observada, columnas: predicha)")
        print(wc.matriz_confusion_inca(sel["observado"], sel[col], cont).to_string())

# %% [markdown]
# ## 2.6 Figuras

# %%
# (a) Componentes de Prophet ajustado en train (escala log(1 + x))
for clave, aj in ajustes_train.items():
    cfg = wc.SERIES[clave]
    nombre = f"{wc.NOMBRE_VAR[cfg['contaminante']]} - {cfg['estacion']}"
    n_pan = 4 if cfg["regimen"] else 3
    fig, axes = plt.subplots(1, n_pan, figsize=(4.6 * n_pan, 3.6))
    axes[0].plot(aj.index, aj["tendencia_log"], color="#4472C4")
    axes[0].set_title("Tendencia")
    axes[0].set_ylabel("log(1 + concentración)")
    axes[0].tick_params(axis="x", rotation=45)

    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    sem = aj.groupby(aj.index.dayofweek)["semanal_log"].mean()
    axes[1].bar(dias, sem.reindex(range(7)).to_numpy(), color="#4472C4")
    axes[1].axhline(0, color="black", lw=0.6)
    axes[1].set_title("Estacionalidad semanal")
    axes[1].set_ylabel("Efecto en log(1 + x)")

    anual = aj.groupby(aj.index.dayofyear)["anual_log"].mean()
    axes[2].plot(anual.index, anual.to_numpy(), color="#4472C4")
    axes[2].axhline(0, color="black", lw=0.6)
    axes[2].set_xticks([1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335])
    axes[2].set_xticklabels(["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    axes[2].set_title("Estacionalidad anual")
    axes[2].set_xlabel("Mes")
    axes[2].set_ylabel("Efecto en log(1 + x)")

    if cfg["regimen"]:
        ef = aj.groupby("OPERACION")["efecto_operacion_log"].mean()
        axes[3].bar(["Detenida (0)", "Operando (1)"], [ef.get(0.0, np.nan), ef.get(1.0, np.nan)],
                    color=["#8FAADC", "#F28C28"])
        axes[3].axhline(0, color="black", lw=0.6)
        axes[3].set_title("Regresor OPERACION")
        axes[3].set_ylabel("Efecto en log(1 + x)")
    fig.suptitle(f"Componentes de Prophet (ajuste en entrenamiento) - {nombre}", y=1.03)
    plt.tight_layout()
    guardar_fig(f"fig11_componentes_prophet_{clave}")

# %%
# (b) Observado vs Prophet (h = 1) en validación y prueba, con intervalo
for clave, wf in predicciones.items():
    cfg = wc.SERIES[clave]
    cont = cfg["contaminante"]
    s = wf[wf["horizonte"] == 1].set_index("fecha_objetivo").sort_index()
    fig, ax = plt.subplots(figsize=(13, 4.2))
    ax.fill_between(s.index, s["limite_inferior"], s["limite_superior"], color="#F28C28", alpha=0.2,
                    label=f"Intervalo Prophet ({INTERVALO:.0%})")
    ax.plot(s.index, s["observado"], color="#404040", lw=0.9, label="Observado")
    ax.plot(s.index, s["valor"], color="#F28C28", lw=1.1, label="Prophet (h = 1)")
    ax.plot(s.index, s["valor_duan"], color="#C55A11", lw=1.0, ls="--", label="Prophet+Duan (h = 1)")
    ax.axhline(wc.ECA_24H[cont], color="#D7263D", ls="--", lw=1,
               label=f"ECA 24 h ({wc.ECA_24H[cont]} {wc.UNIDAD})")
    ax.axhline(wc.OMS_24H[cont], color="#2E9E44", ls=":", lw=1,
               label=f"Guía OMS 24 h ({wc.OMS_24H[cont]} {wc.UNIDAD})")
    for k, etiqueta in (("inicio_test", "inicio prueba"), ("fin_test", "fin prueba")):
        f = pd.Timestamp(cfg[k])
        if s.index.min() < f < s.index.max():
            ax.axvline(f, color="black", ls="-.", lw=0.8)
            ax.text(f, ax.get_ylim()[1] * 0.97, f" {etiqueta}", fontsize=8, va="top")
    ax.set_title(f"{wc.NOMBRE_VAR[cont]} - {cfg['estacion']} "
                 f"({wc.NOMBRE_DEP[cfg['departamento']]}): Prophet en validación y prueba")
    ax.set_ylabel(f"Promedio diario ({wc.UNIDAD})")
    ax.set_xlabel("Fecha")
    ax.legend(fontsize=8, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.16), frameon=False)
    plt.tight_layout()
    guardar_fig(f"fig12_prophet_val_test_{clave}")

# %%
# (c) RMSE por horizonte en test: persistencia vs Prophet (sin y con Duan)
sel = metricas[metricas["particion"] == "test"]
if len(sel):
    fig, axes = plt.subplots(1, len(wc.SERIES), figsize=(5 * len(wc.SERIES), 3.6), squeeze=False)
    for ax, clave in zip(axes[0], wc.SERIES):
        cfg = wc.SERIES[clave]
        d = sel[sel["serie"] == clave].pivot(index="horizonte", columns="modelo", values="RMSE")
        d = d[[m for m in wc.COLORES_MODELO if m in d.columns]]
        d.plot(kind="bar", ax=ax, color=wc.COLORES_MODELO, rot=0)
        ax.set_title(f"{wc.NOMBRE_VAR[cfg['contaminante']]} - {cfg['estacion']}")
        ax.set_xlabel("Horizonte (días)")
        ax.set_ylabel(f"RMSE ({wc.UNIDAD})")
        ax.legend(title="", fontsize=8)
    fig.suptitle("RMSE en el conjunto de prueba por horizonte", y=1.03)
    plt.tight_layout()
    guardar_fig("fig13_rmse_horizonte_prophet")

# %% [markdown]
# ## 2.7 Guardado de modelos y predicciones
#
# - checkpoints/04_prophet_ajuste_train_<serie>.pkl : ajuste y residuos en train (híbrido).
# - checkpoints/04_prophet_walkforward_<serie>.pkl/.csv : predicciones walk-forward.
# - modelos/<serie>_prophet_v1/ : modelo ajustado en train, modelo ajustado con todos los
#   datos hasta el fin de la prueba (candidato para inferencia) y metadatos.

# %%
for clave in wc.SERIES:
    cfg = wc.SERIES[clave]
    ajustes_train[clave].to_pickle(
        os.path.join(wc.CARPETA_CHECKPOINTS, f"04_prophet_ajuste_train_{clave}.pkl"))

    carpeta = os.path.join(wc.CARPETA_MODELOS, f"{clave}_prophet_{VERSION_MODELO}")
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "prophet_train.json"), "w") as f:
        f.write(model_to_json(modelos_train[clave]))
    m_final = ajustar_prophet(datasets[clave], pd.Timestamp(cfg["fin_test"]), cfg["regimen"],
                              wp.params_prophet(clave))
    with open(os.path.join(carpeta, "prophet_hasta_fin_test.json"), "w") as f:
        f.write(model_to_json(m_final))
    wc.guardar_json({
        "serie": clave, "version": VERSION_MODELO, "config_serie": cfg,
        "escala": "log1p (predicción = expm1(yhat); con Duan: exp(yhat) * factor - 1)",
        "factor_duan_train": ajustes_train[clave].attrs["factor_duan"],
        "factor_duan_hasta_fin_test": factor_duan_modelo(m_final),
        "hiperparametros": wp.params_prophet(clave), "intervalo": INTERVALO,
        "muestras_incertidumbre": MUESTRAS_INCERTIDUMBRE,
        "reentrenar_cada_dias": REENTRENAR_CADA, "horizontes": wc.HORIZONTES,
        "regresores": ["OPERACION"] if cfg["regimen"] else [],
        "supuesto_regresor": ("OPERACION futura = último estado conocido en el origen "
                              "(OPERACION_CAUSAL, mediana móvil de 7 días hacia atrás del "
                              f"máximo horario diario > {wc.UMBRAL_OPERACION} µg/m³)")
        if cfg["regimen"] else None,
        "semilla": wc.SEMILLA, "versiones": wc.versiones_librerias(),
    }, os.path.join(carpeta, "metadatos.json"))
    print(f"{clave}: guardado en {carpeta}")

# %% [markdown]
# ## Resumen de la fase
#
# - Prophet (escala log) con estacionalidad semanal y anual; en CA-CC-01 con el
#   regresor OPERACION (último estado conocido al pronosticar).
# - Evaluación walk-forward por partición y horizonte frente a la persistencia
#   (tabla 04_metricas_prophet.csv), con métricas de regresión e INCA.
# - Los residuos de Prophet en train y las predicciones walk-forward quedan listos para
#   el híbrido Prophet-LSTM (04).
