# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Notebook 4c: Híbrido Prophet-LSTM v2 - tres variantes y selección por horizonte
#
# Variantes (todo lo que se elige, se elige SOLO con la validación):
# - Residuos:  Prophet + alfa_h * LSTM(residuo de Prophet fuera de muestra).
# - Cascada:   la LSTM predice la concentración; recibe el pronóstico y los componentes de
#              Prophet, media y máximo del SO2 de 7 días, meteorología rezagada y OPERACION.
# - Ponderada: w_h * Prophet + (1 - w_h) * LSTM sola (escala log).
# Entradas de las LSTM (residuos y cascada): residuo fuera de muestra, SO2 reciente (log, media
# y máximo de 7 días), marca de faltante, meteorología rezagada, calendario, OPERACION (causal)
# y, como entrada aparte, pronóstico y componentes de Prophet para t+1..t+H (wayra_hibrido.py).
# Tasa de aprendizaje baja y paciencia alta; hiperparámetros de 05-HIPERPARAMETROS.py.
#
# Para cada variante y horizonte, en validación: alfa o w, factor de Duan (residuos de val) y
# cuantil del límite de alerta (máx. F2 con tope de días con alerta). Selección por horizonte:
# la variante (con o sin Duan) de menor RMSE de validación sobre los mismos pares (origen, h).
# Intervalo de cada variante: el de Prophet desplazado a su centro.
#
# La PRUEBA se calcula una sola vez, al final (WAYRA_MOSTRAR_PRUEBA=1); sin esa variable solo
# se muestra y guarda la validación.

# %%
import os
import time
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import wayra_comun as wc
import wayra_prophet as wp
import wayra_lstm as wl
import wayra_hibrido as wh

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

VERSION_MODELO = "v2"
MOSTRAR_PRUEBA = os.environ.get("WAYRA_MOSTRAR_PRUEBA") == "1"
PARTICIONES_REPORTE = ("val", "test") if MOSTRAR_PRUEBA else ("val",)
CARPETA_V1 = os.path.join(wc.CARPETA_CHECKPOINTS, "v1_anterior")  # híbrido v1 (respaldo)
VARIANTES = ["Prophet", "Residuos", "Residuos intradiario", "Cascada", "Ponderada", "Residuos global"]
# Pasco y Moquegua: LSTM global (04d) y calibración de alertas con origen móvil
RUTA_GLOBAL = os.path.join(wc.CARPETA_CHECKPOINTS, "08_residuos_global_walkforward_{}.pkl")
RUTA_LSTM_GLOBAL = os.path.join(wc.CARPETA_CHECKPOINTS, "05_lstm_global_walkforward_{}.pkl")
H = wh.H

wl.fijar_semillas_keras()
print(f"Fuente: {wc.FUENTE_DATOS} | prueba visible: {MOSTRAR_PRUEBA}")
print("Versiones:", wc.versiones_librerias())


def guardar_fig(nombre: str):
    plt.savefig(os.path.join(wc.CARPETA_FIGURAS, f"{nombre}.png"), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close("all")


def a_largo(origenes, yhat, lower, upper, centro, obs: pd.Series, clave: str, extra=None) -> pd.DataFrame:
    """Arreglos (n, H) -> tabla larga (origen, horizonte). El intervalo de Prophet se desplaza al
    centro de la variante."""
    filas = []
    ultimo = obs.index.max()
    for j, t in enumerate(origenes):
        for h in wc.HORIZONTES:
            f = t + pd.Timedelta(days=h)
            if f > ultimo:
                continue
            d = centro[j, h - 1] - yhat[j, h - 1]
            fila = {"origen": t, "horizonte": h, "fecha_objetivo": f, "prophet_log": yhat[j, h - 1],
                    "centro_log": centro[j, h - 1], "lower_log": lower[j, h - 1] + d,
                    "upper_log": upper[j, h - 1] + d, "observado": obs.get(f, np.nan)}
            if extra is not None:
                fila.update({k: v[j] for k, v in extra.items()})
            filas.append(fila)
    df = pd.DataFrame(filas)
    df["obs_log"] = wc.a_escala_modelo(df["observado"])
    df["particion"] = wc.asignar_particion(pd.DatetimeIndex(df["fecha_objetivo"]), clave).to_numpy()
    return df


def elegir_por_horizonte(val: pd.DataFrame, pred_fn, grilla=wh.GRILLA_ALFA):
    """Parámetro por horizonte que minimiza el RMSE (µg/m³) de validación."""
    elegidos, curvas = {}, {}
    for h, g in val.groupby("horizonte"):
        errores = [wh.rmse_ug(g["obs_log"].to_numpy(), pred_fn(g, a)) for a in grilla]
        elegidos[h] = float(grilla[int(np.nanargmin(errores))])
        curvas[f"h{h}"] = errores
    return elegidos, pd.DataFrame(curvas, index=grilla)


# %% [markdown]
# ## 4c.1 Walk-forward completo de Prophet y datos

# %%
datasets = {clave: wc.cargar_dataset(clave) for clave in wc.SERIES}
estado = {}
for clave, ds in datasets.items():
    t0 = time.time()
    pp = wp.params_prophet(clave)
    wf = wh.walk_forward_prophet(ds, clave, pp)
    wf02 = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"04_prophet_walkforward_{clave}.pkl"))
    comun = wf.merge(wf02[["origen", "horizonte", "yhat_log"]], on=["origen", "horizonte"])
    datos = wh.Datos(ds, clave, wf)
    datos_intra = wh.Datos(ds, clave, wf, intradiarias=True)
    params = {"Residuos": wl.params_lstm(clave, "hibrido_v2"),
              "Residuos intradiario": wl.params_lstm(clave, "hibrido_v2_intra"),
              "Cascada": wl.params_lstm(clave, "cascada")}
    estado[clave] = {"datos": datos, "datos_intra": datos_intra, "wf": wf, "params": params,
                     "params_prophet": pp, "variantes": {}}
    print(f"   variables intradiarias: {[c for c in datos_intra.v.columns if c.startswith('intra_')]}")
    print(f"{clave}: Prophet {pp} | orígenes walk-forward: {wf['origen'].nunique()} | dif. máx. con 02 = "
          f"{(comun['yhat'] - comun['yhat_log']).abs().max():.1e} | {time.time() - t0:.0f} s")
    for v, p in params.items():
        print(f"   LSTM {v}: {p}")

# %% [markdown]
# ## 4c.2 Entrenamiento de las LSTM (A: train con parada temprana en val; B: train + val) y
# ## predicciones de las tres variantes en val y test

# %%
for clave, e in estado.items():
    obs = datasets[clave]["OBJETIVO"]
    for variante, objetivo, datos in (("Residuos", "Y", e["datos"]),
                                      ("Residuos intradiario", "Y", e["datos_intra"]),
                                      ("Cascada", "Yc", e["datos"])):
        t0 = time.time()
        p = e["params"][variante]
        mu = datos.muestras(int(p["ventana"]))
        tr, va, tv = (wh.subconjunto(mu, mu["sel"][s]) for s in ("train", "val", "train_val"))
        mA, mB, hist, epocas = wl.entrenar_A_B(wh.entrada(tr), tr[objetivo], wh.entrada(va), va[objetivo],
                                               wh.entrada(tv), tv[objetivo], tr["X"].shape[2], p,
                                               n_futuro=tr["F"].shape[1])
        ev = wh.subconjunto(mu, mu["sel"]["eval"])
        usa_B = np.asarray(ev["origen"] >= datos.fin_val)
        salida = np.empty((len(ev["origen"]), H))
        for etiqueta, modelo, sel in (("A", mA, ~usa_B), ("B", mB, usa_B)):
            if sel.any():
                sub = wh.subconjunto(ev, sel)
                salida[sel] = (wh.corregir(modelo, sub, datos) if objetivo == "Y"
                               else wh.concentracion(modelo, sub, datos))
        if objetivo == "Y":   # centro provisional con alfa = 1; alfa se elige en 4c.3
            largo = a_largo(ev["origen"], ev["yhat"], ev["lower"], ev["upper"], ev["yhat"] + salida, obs, clave)
            largo["correccion_log"] = largo["centro_log"] - largo["prophet_log"]
        else:
            largo = a_largo(ev["origen"], ev["yhat"], ev["lower"], ev["upper"], salida, obs, clave)
        largo["modelo_lstm"] = np.where(largo["origen"] >= datos.fin_val, "B", "A")
        e["variantes"][variante] = {"largo": largo, "A": mA, "B": mB, "hist": hist, "epocas": epocas}
        print(f"{clave} [{variante}]: épocas óptimas = {epocas} | pérdida val = {min(hist['val_loss']):.4f} | "
              f"{time.time() - t0:.0f} s")

    # Prophet solo como candidato explícito (mismo walk-forward que 02)
    datos = e["datos"]
    pro = e["wf"][e["wf"]["origen"] >= datos.fin_train].rename(columns={"yhat": "prophet_log"})
    solo = pro.assign(centro_log=pro["prophet_log"], lower_log=pro["yhat_lower"], upper_log=pro["yhat_upper"])
    solo["observado"] = solo["fecha_objetivo"].map(obs)
    solo["obs_log"] = wc.a_escala_modelo(solo["observado"])
    solo["particion"] = wc.asignar_particion(pd.DatetimeIndex(solo["fecha_objetivo"]), clave).to_numpy()
    e["variantes"]["Prophet"] = {"largo": solo}

    # Ponderada: Prophet (walk-forward) + LSTM sola (03-LSTM), mismos orígenes
    lstm = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"05_lstm_walkforward_{clave}.pkl"))
    pro = e["wf"][e["wf"]["origen"] >= datos.fin_train]
    pon = pro.merge(lstm[["origen", "horizonte", "yhat_log"]].rename(columns={"yhat_log": "lstm_log"}),
                    on=["origen", "horizonte"])
    pon = pon.rename(columns={"yhat": "prophet_log", "yhat_lower": "lower_prophet", "yhat_upper": "upper_prophet"})
    pon["observado"] = pon["fecha_objetivo"].map(obs)
    pon["obs_log"] = wc.a_escala_modelo(pon["observado"])
    pon["particion"] = wc.asignar_particion(pd.DatetimeIndex(pon["fecha_objetivo"]), clave).to_numpy()
    e["variantes"]["Ponderada"] = {"largo": pon}
    print(f"{clave} [Ponderada]: {pon['origen'].nunique()} orígenes con Prophet y LSTM sola")

    # Residuos global: corrección de la LSTM global de residuos (04d), mismos orígenes
    if os.path.exists(RUTA_GLOBAL.format(clave)):
        g = pd.read_pickle(RUTA_GLOBAL.format(clave))
        g["centro_log"] = g["prophet_log"] + g["correccion_log"]     # alfa = 1 provisional (4c.3)
        g["lower_log"] = g["lower_log"] + g["correccion_log"]
        g["upper_log"] = g["upper_log"] + g["correccion_log"]
        g["obs_log"] = wc.a_escala_modelo(g["observado"])
        g["particion"] = wc.asignar_particion(pd.DatetimeIndex(g["fecha_objetivo"]), clave).to_numpy()
        e["variantes"]["Residuos global"] = {"largo": g}
        print(f"{clave} [Residuos global]: {g['origen'].nunique()} orígenes (LSTM global de 04d)")

# %% [markdown]
# ## 4c.3 Parámetros de combinación, Duan y calibración de alertas (SOLO validación)

# %%
for clave, e in estado.items():
    cont = wc.SERIES[clave]["contaminante"]
    V = e["variantes"]
    # alfa (residuos) y w (ponderada) por horizonte
    alfa, curvas_a = {}, {}
    for variante in [v for v in ("Residuos", "Residuos intradiario", "Residuos global") if v in V]:
        r = V[variante]["largo"]
        alfa[variante], curvas_a[variante] = elegir_por_horizonte(
            r[r["particion"] == "val"], lambda g, a: (g["prophet_log"] + a * g["correccion_log"]).to_numpy())
        a_h = r["horizonte"].map(alfa[variante])
        r["centro_log"] = r["prophet_log"] + a_h * r["correccion_log"]
        r["lower_log"] = r["lower_log"] - (1 - a_h) * r["correccion_log"]
        r["upper_log"] = r["upper_log"] - (1 - a_h) * r["correccion_log"]
    p = V["Ponderada"]["largo"]
    w, curva_w = elegir_por_horizonte(p[p["particion"] == "val"],
                                      lambda g, a: (a * g["prophet_log"] + (1 - a) * g["lstm_log"]).to_numpy())
    p["centro_log"] = p["horizonte"].map(w) * p["prophet_log"] + (1 - p["horizonte"].map(w)) * p["lstm_log"]
    p["lower_log"] = p["lower_prophet"] + (p["centro_log"] - p["prophet_log"])
    p["upper_log"] = p["upper_prophet"] + (p["centro_log"] - p["prophet_log"])
    e.update({"alfa": alfa, "w": w})
    print(f"\n{clave}")
    for variante, curva in curvas_a.items():
        print(f"{variante} - RMSE de validación según alfa (0 = Prophet solo):")
        print(curva.iloc[::4].round(2).to_string())
        print(f"alfa elegido: {alfa[variante]}")
    print("Ponderada - RMSE de validación según w (1 = Prophet solo, 0 = LSTM sola):")
    print(curva_w.iloc[::4].round(2).to_string())
    print(f"w elegido: {w}")

    # Duan y cuantil de alerta por variante y horizonte (validación)
    for variante, d in V.items():
        largo = d["largo"]
        val = largo[largo["particion"] == "val"]
        duan = {h: wc.factor_duan(g["obs_log"] - g["centro_log"]) for h, g in val.groupby("horizonte")}
        piv = {c: val.pivot(index="origen", columns="horizonte", values=c).reindex(columns=range(1, H + 1)).to_numpy()
               for c in ("centro_log", "lower_log", "upper_log", "obs_log")}
        q, cal = wh.calibrar_cuantil(piv["centro_log"], piv["lower_log"], piv["upper_log"], piv["obs_log"], cont)
        largo["valor"] = wc.a_escala_original(largo["centro_log"])
        largo["valor_duan"] = np.exp(largo["centro_log"]) * largo["horizonte"].map(duan) - 1
        largo["limite_inferior"] = wc.a_escala_original(largo["lower_log"])
        largo["limite_superior"] = wc.a_escala_original(largo["upper_log"])
        sigma = (largo["upper_log"] - largo["lower_log"]) / (2 * wh.Z80)
        largo["limite_alerta"] = np.expm1(largo["centro_log"] + wh.norm.ppf(largo["horizonte"].map(
            dict(zip(range(1, H + 1), q)))) * sigma)
        d.update({"duan": duan, "q": q, "cal": cal})
        print(f"{variante}: Duan (val) = { {h: round(v, 3) for h, v in duan.items()} } | cuantil de alerta = {q}")

    # Prophet solo: cuantil calibrado (comparación justa de la regla del intervalo)
    wfp = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"04_prophet_walkforward_{clave}.pkl"))
    val = wfp[wfp["particion"] == "val"]
    piv = {c: val.pivot(index="origen", columns="horizonte", values=c).reindex(columns=range(1, H + 1)).to_numpy()
           for c in ("yhat_log", "yhat_lower_log", "yhat_upper_log", "observado_log")}
    e["q_prophet"], _ = wh.calibrar_cuantil(piv["yhat_log"], piv["yhat_lower_log"], piv["yhat_upper_log"],
                                            piv["observado_log"], cont)
    print(f"Prophet: cuantil de alerta = {e['q_prophet']}")

    # Calibración con ORIGEN MÓVIL (Pasco y Moquegua): cuantil elegido con todos los pronósticos
    # de Prophet fuera de muestra cuyo objetivo es anterior a la prueba (walk-forward completo desde
    # el primer año de datos hasta el fin de val). Se aplica al intervalo de cada variante.
    if wc.SERIES[clave].get("intervalo_completo"):
        fin_val = pd.Timestamp(wc.SERIES[clave]["inicio_test"]) - pd.Timedelta(days=1)
        wfm = e["wf"][e["wf"]["fecha_objetivo"] <= fin_val].copy()
        wfm["obs_log"] = wc.a_escala_modelo(wfm["fecha_objetivo"].map(datasets[clave]["OBJETIVO"]))
        piv = {c: wfm.pivot(index="origen", columns="horizonte", values=c).reindex(columns=range(1, H + 1)).to_numpy()
               for c in ("yhat", "yhat_lower", "yhat_upper", "obs_log")}
        e["q_movil"], cal_m = wh.calibrar_cuantil(piv["yhat"], piv["yhat_lower"], piv["yhat_upper"], piv["obs_log"], cont)
        umbral = wc.UMBRALES_ALERTA["moderada_o_peor"] * wc.ECA_24H[cont]
        n_epi = int((wfm[wfm["horizonte"] == 1]["obs_log"] > np.log1p(umbral)).sum())
        print(f"Origen móvil: {wfm['origen'].nunique()} orígenes ({wfm['origen'].min().date()} -> "
              f"{wfm['origen'].max().date()}), {n_epi} días 'Moderada o peor' (h = 1) | cuantil = {e['q_movil']}")
        cal_m.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_calibracion_origen_movil_{clave}.csv"), sep=";",
                     index=False, decimal=",")
        for variante, d in V.items():
            largo = d["largo"]
            sigma = (largo["upper_log"] - largo["lower_log"]) / (2 * wh.Z80)
            largo["limite_alerta_movil"] = np.expm1(largo["centro_log"] + wh.norm.ppf(
                largo["horizonte"].map(dict(zip(range(1, H + 1), e["q_movil"])))) * sigma)

# %% [markdown]
# ## 4c.4 Selección de la variante por horizonte (SOLO validación, mismos pares origen-h)

# %%
for clave, e in estado.items():
    V = e["variantes"]
    llaves = None
    for d in V.values():
        val = d["largo"][(d["largo"]["particion"] == "val") & d["largo"]["observado"].notna()]
        k = set(map(tuple, val[["origen", "horizonte"]].to_numpy()))
        llaves = k if llaves is None else llaves & k
    filas = []
    for variante, d in V.items():
        val = d["largo"][d["largo"]["particion"] == "val"]
        val = val[pd.MultiIndex.from_frame(val[["origen", "horizonte"]]).isin(list(llaves))]
        for h, g in val.groupby("horizonte"):
            for forma, col in (("", "valor"), ("+Duan", "valor_duan")):
                m = wc.metricas_regresion(g["observado"], g[col])
                filas.append({"horizonte": h, "candidato": variante + forma, "variante": variante, "columna": col,
                              "n": m["n"], "RMSE_val": m["RMSE"], "MAE_val": m["MAE"]})
    sel = pd.DataFrame(filas)
    elegidos = sel.loc[sel.groupby("horizonte")["RMSE_val"].idxmin()].set_index("horizonte")
    e["seleccion"] = elegidos
    tabla_sel = sel.pivot(index="candidato", columns="horizonte", values="RMSE_val")
    print(f"{clave} - RMSE de validación ({wc.UNIDAD}) de cada candidato (mismos pares; n = "
          f"{sel.groupby('horizonte')['n'].first().to_dict()}):")
    print(tabla_sel.round(3).to_string())
    print("Elegido por horizonte: " + ", ".join(f"h{h} = {r['candidato']}" for h, r in elegidos.iterrows()))
    sel.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_seleccion_variante_{clave}.csv"), sep=";", index=False,
               decimal=",")

    # Híbrido seleccionado: por horizonte, filas de la variante elegida (con o sin Duan)
    partes = []
    for h, r in elegidos.iterrows():
        d = V[r["variante"]]["largo"]
        d = d[d["horizonte"] == h].copy()
        d["valor"] = d[r["columna"]]
        d["variante"] = r["candidato"]
        partes.append(d)
    e["seleccionado"] = pd.concat(partes, ignore_index=True)

# %% [markdown]
# ## 4c.5 Comparación: persistencia, Prophet, LSTM, híbrido v1 (anterior), las tres variantes y
# ## el híbrido seleccionado. Reglas: puntual, intervalo (80 %) e intervalo calibrado.

# %%
COLS = ["origen", "horizonte", "fecha_objetivo", "particion", "observado"]


def modelos_a_comparar(clave: str) -> dict:
    e = estado[clave]
    mods = wc.predicciones_base(clave, datasets[clave])
    wfp = pd.read_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"04_prophet_walkforward_{clave}.pkl"))
    q = e["q_prophet"][wfp["horizonte"].to_numpy() - 1]
    sigma = (wfp["yhat_upper_log"] - wfp["yhat_lower_log"]) / (2 * wh.Z80)
    wfp["limite_alerta"] = np.expm1(wfp["yhat_log"] + wh.norm.ppf(q) * sigma)
    cols_lim = ["limite_alerta"]
    if "q_movil" in e:
        qm = e["q_movil"][wfp["horizonte"].to_numpy() - 1]
        wfp["limite_alerta_movil"] = np.expm1(wfp["yhat_log"] + wh.norm.ppf(qm) * sigma)
        cols_lim.append("limite_alerta_movil")
    mods["Prophet"] = mods["Prophet"].merge(wfp[["origen", "horizonte"] + cols_lim],
                                            on=["origen", "horizonte"], how="left")
    mods.update(wc.predicciones_lstm(clave))
    if os.path.exists(RUTA_LSTM_GLOBAL.format(clave)):
        g = pd.read_pickle(RUTA_LSTM_GLOBAL.format(clave))
        mods["LSTM global"] = g[COLS + ["valor"]].copy()
        mods["LSTM global+Duan"] = g[COLS].assign(valor=g["valor_duan"])
    ruta_v1 = os.path.join(CARPETA_V1, f"06_hibrido_walkforward_{clave}.pkl")
    if os.path.exists(ruta_v1):
        v1 = pd.read_pickle(ruta_v1)
        mods["Híbrido v1 (anterior)"] = v1[COLS + ["valor", "limite_inferior", "limite_superior"]]
        mods["Híbrido v1 (anterior)+Duan"] = v1[COLS].assign(valor=v1["valor_duan"])
    for variante, d in e["variantes"].items():
        if variante == "Prophet":   # ya está como modelo base
            continue
        x = d["largo"]
        mods[f"H. {variante}"] = x[COLS + ["valor", "limite_inferior", "limite_superior", "limite_alerta"]
                                   + [c for c in ("limite_alerta_movil",) if c in x]]
        mods[f"H. {variante}+Duan"] = x[COLS].assign(valor=x["valor_duan"])
    s = e["seleccionado"]
    mods["Híbrido seleccionado"] = s[COLS + ["valor", "limite_inferior", "limite_superior", "limite_alerta"]
                                     + [c for c in ("limite_alerta_movil",) if c in s]]
    return mods


ORDEN = ["Persistencia", "Prophet", "Prophet+Duan", "LSTM", "LSTM+Duan", "LSTM global", "LSTM global+Duan",
         "Híbrido v1 (anterior)",
         "Híbrido v1 (anterior)+Duan"] + [f"H. {v}{s}" for v in VARIANTES for s in ("", "+Duan")] + \
        ["Híbrido seleccionado"]
tablas_met, tablas_ale = [], []
for clave in wc.SERIES:
    met, ale = wc.comparar_modelos(modelos_a_comparar(clave), wc.SERIES[clave]["contaminante"],
                                   particiones=PARTICIONES_REPORTE)
    met.insert(0, "serie", clave)
    ale.insert(0, "serie", clave)
    tablas_met.append(met)
    tablas_ale.append(ale)
metricas = pd.concat(tablas_met, ignore_index=True)
alertas = pd.concat(tablas_ale, ignore_index=True)
pers = metricas[metricas["modelo"] == "Persistencia"].set_index(["serie", "particion", "horizonte"])["RMSE"]
metricas["skill_vs_persistencia"] = 1 - metricas["RMSE"] / metricas.set_index(
    ["serie", "particion", "horizonte"]).index.map(pers)
sufijo = "" if MOSTRAR_PRUEBA else "_solo_val"
metricas.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_metricas_hibrido_v2{sufijo}.csv"), sep=";", index=False,
                decimal=",")
alertas.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_alertas_hibrido_v2{sufijo}.csv"), sep=";", index=False,
               decimal=",")

for clave in wc.SERIES:
    print(f"\nVariante elegida por horizonte (validación): "
          + ", ".join(f"h{h} = {r['candidato']}" for h, r in estado[clave]["seleccion"].iterrows()))
    for part in PARTICIONES_REPORTE:
        t = metricas[(metricas["serie"] == clave) & (metricas["particion"] == part)]
        tabla = t.pivot(index="modelo", columns="horizonte", values=["RMSE", "MAE", "R2", "skill_vs_persistencia"])
        tabla = tabla.reindex([m for m in ORDEN if m in tabla.index])
        print(f"\n=== {clave} - {part}: métricas por horizonte ({wc.UNIDAD}; n = "
              f"{t.groupby('horizonte')['n'].first().to_dict()}) ===")
        print(tabla.round(3).to_string())
        a = alertas[(alertas["serie"] == clave) & (alertas["particion"] == part)
                    & (alertas["umbral"] == "moderada_o_peor")].copy()
        a["modelo_regla"] = a["modelo"] + np.where(a["regla"] == "puntual", "", " (" + a["regla"] + ")")
        ta = a.pivot_table(index="modelo_regla", columns="horizonte",
                           values=["recall", "precision", "F2", "pct_dias_con_alerta"])
        orden_mr = [f"{m}{s}" for m in ORDEN for s in ("", " (intervalo)", " (intervalo calibrado)",
                                                       " (intervalo calibrado (origen móvil))")
                    if f"{m}{s}" in ta.index]
        print(f"Alertas 'Moderada o peor' (días reales por horizonte: "
              f"{a.groupby('horizonte')['dias_reales'].max().to_dict()}):")
        print(ta.reindex(orden_mr)[["recall", "precision", "F2", "pct_dias_con_alerta"]].round(2).to_string())
        e_ = a[a["regla"] == "puntual"]
        eca = alertas[(alertas["serie"] == clave) & (alertas["particion"] == part) & (alertas["umbral"] == "supera_eca")]
        print(f"Días > ECA por horizonte: {eca.groupby('horizonte')['dias_reales'].max().to_dict()}")

# %%
# CA-HUAR-01 (serie combinada): métricas también SOLO con los días propios (RELLENO = 0), que son
# la evaluación principal (decisión del usuario). Los días rellenados con CA-COLQ-01 no se evalúan.
for clave in wc.SERIES:
    ds = datasets[clave]
    if "RELLENO" not in ds:
        continue
    rellenados = set(ds.index[ds["RELLENO"] == 1])
    mods = {k: v.assign(observado=v["observado"].where(~v["fecha_objetivo"].isin(rellenados)))
            for k, v in modelos_a_comparar(clave).items()}
    met_p, ale_p = wc.comparar_modelos(mods, wc.SERIES[clave]["contaminante"], particiones=PARTICIONES_REPORTE)
    pers_p = met_p[met_p["modelo"] == "Persistencia"].set_index(["particion", "horizonte"])["RMSE"]
    met_p["skill_vs_persistencia"] = 1 - met_p["RMSE"] / met_p.set_index(["particion", "horizonte"]).index.map(pers_p)
    met_p.insert(0, "serie", clave)
    ale_p.insert(0, "serie", clave)
    met_p.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_metricas_hibrido_v2{sufijo}_propios_{clave}.csv"),
                 sep=";", index=False, decimal=",")
    ale_p.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_alertas_hibrido_v2{sufijo}_propios_{clave}.csv"),
                 sep=";", index=False, decimal=",")
    for part in PARTICIONES_REPORTE:
        t = met_p[met_p["particion"] == part]
        tabla = t.pivot(index="modelo", columns="horizonte", values=["RMSE", "MAE", "R2", "skill_vs_persistencia"])
        tabla = tabla.reindex([m for m in ORDEN if m in tabla.index])
        print(f"\n=== {clave} - {part} - SOLO DÍAS PROPIOS (evaluación principal; n = "
              f"{t.groupby('horizonte')['n'].first().to_dict()}) ===")
        print(tabla.round(3).to_string())
        a = ale_p[(ale_p["particion"] == part) & (ale_p["umbral"] == "moderada_o_peor")].copy()
        a["modelo_regla"] = a["modelo"] + np.where(a["regla"] == "puntual", "", " (" + a["regla"] + ")")
        ta = a.pivot_table(index="modelo_regla", columns="horizonte", values=["recall", "precision", "F2", "pct_dias_con_alerta"])
        orden_mr = [f"{m}{s}" for m in ORDEN for s in ("", " (intervalo)", " (intervalo calibrado)",
                                                       " (intervalo calibrado (origen móvil))") if f"{m}{s}" in ta.index]
        print(f"Alertas 'Moderada o peor' (días propios reales por horizonte: "
              f"{a.groupby('horizonte')['dias_reales'].max().to_dict()}):")
        print(ta.reindex(orden_mr)[["recall", "precision", "F2", "pct_dias_con_alerta"]].round(2).to_string())

# %% [markdown]
# ## 4c.6 Figuras y guardado

# %%
for clave, e in estado.items():
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.5))
    for ax, v in zip(axes, ("Residuos", "Cascada")):
        h = e["variantes"][v]["hist"]
        ax.plot(h["loss"], label="Entrenamiento", color="#2F5597")
        ax.plot(h["val_loss"], label="Validación", color="#C55A11")
        ax.axvline(e["variantes"][v]["epocas"] - 1, color="black", ls=":", lw=0.8, label="Época óptima")
        ax.set_title(f"Híbrido {v.lower()}: curvas de aprendizaje")
        ax.set_xlabel("Época")
        ax.set_ylabel("MSE (estandarizado)")
        ax.legend(fontsize=8)
    plt.tight_layout()
    guardar_fig(f"fig24_hibrido_v2_curvas_{clave}")

if MOSTRAR_PRUEBA:
    for clave in wc.SERIES:
        cfg = wc.SERIES[clave]
        cont = cfg["contaminante"]
        mods = modelos_a_comparar(clave)
        for h_fig in wc.HORIZONTES:
            fig, ax = plt.subplots(figsize=(13, 4.4))
            s = mods["Híbrido seleccionado"]
            d = s[(s["horizonte"] == h_fig) & (s["particion"] == "test")].set_index("fecha_objetivo").sort_index().asfreq("D")
            ax.fill_between(d.index, d["limite_inferior"], d["limite_superior"], color="#C9A0DC", alpha=0.35,
                            label=f"Intervalo ({wp.INTERVALO:.0%})")
            ax.plot(d.index, d["limite_alerta"], color="#7030A0", lw=0.8, ls="--", label="Límite de alerta calibrado")
            ax.plot(d.index, d["observado"], color="#404040", lw=1.1, label="Observado")
            for nombre, estilo, color in (("Persistencia", ":", "#A5A5A5"), ("Prophet", "-", "#F4B183"),
                                          ("Híbrido seleccionado", "-", "#7030A0")):
                x = (mods[nombre][(mods[nombre]["horizonte"] == h_fig) & (mods[nombre]["particion"] == "test")]
                     .set_index("fecha_objetivo").sort_index()[["valor"]].asfreq("D"))
                ax.plot(x.index, x["valor"], ls=estilo, lw=1.1, color=color, label=nombre)
            ax.axhline(wc.ECA_24H[cont] * 0.5, color="#F2C12E", ls="-.", lw=0.9, label="INCA 50 (Buena/Moderada)")
            ax.axhline(wc.ECA_24H[cont], color="#D7263D", ls="--", lw=1,
                       label=f"ECA 24 h ({wc.ECA_24H[cont]} {wc.UNIDAD})")
            ax.set_title(f"{wc.NOMBRE_VAR[cont]} - {cfg['estacion']}: híbrido seleccionado en prueba, h = {h_fig} "
                         f"({estado[clave]['seleccion'].loc[h_fig, 'candidato']})")
            ax.set_ylabel(f"Promedio diario ({wc.UNIDAD})")
            ax.set_xlabel("Fecha")
            ax.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.16), frameon=False)
            plt.tight_layout()
            guardar_fig(f"fig25_hibrido_seleccionado_test_h{h_fig}_{clave}")

for clave, e in estado.items():
    salida = wc.a_formato_bd(e["seleccionado"], clave)
    salida.to_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_hibrido_seleccionado_walkforward_{clave}.pkl"))
    salida.to_csv(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_hibrido_seleccionado_walkforward_{clave}.csv"),
                  sep=";", index=False)
    for v, d in e["variantes"].items():
        d["largo"].to_pickle(os.path.join(wc.CARPETA_CHECKPOINTS, f"08_hibrido_{v.lower().replace(' ', '_')}_walkforward_{clave}.pkl"))
    carpeta = os.path.join(wc.CARPETA_MODELOS, f"{clave}_hibrido_{VERSION_MODELO}")
    os.makedirs(carpeta, exist_ok=True)
    for v in ("Residuos", "Residuos intradiario", "Cascada"):
        e["variantes"][v]["A"].save(os.path.join(carpeta, f"lstm_{v.lower().replace(' ', '_')}_A_train.keras"))
        e["variantes"][v]["B"].save(os.path.join(carpeta, f"lstm_{v.lower().replace(' ', '_')}_B_train_val.keras"))
    wc.guardar_json({"escalador_diario": e["datos"].esc,
                     "escalador_futuro": {"media": e["datos"].fut_media.to_dict(), "desv": e["datos"].fut_desv.to_dict()}},
                    os.path.join(carpeta, "escaladores.json"))
    wc.guardar_json({
        "serie": clave, "version": VERSION_MODELO, "fuente": wc.FUENTE_DATOS, "config_serie": wc.SERIES[clave],
        "hiperparametros_prophet": e["params_prophet"], "hiperparametros_lstm": e["params"],
        "epocas_optimas": {v: e["variantes"][v]["epocas"] for v in ("Residuos", "Residuos intradiario", "Cascada")},
        "alfa_residuos_por_horizonte": e["alfa"], "peso_prophet_ponderada_por_horizonte": e["w"],
        "factor_duan": {v: d["duan"] for v, d in e["variantes"].items()},
        "cuantil_alerta": {**{v: d["q"].tolist() for v, d in e["variantes"].items()},
                           "Prophet": e["q_prophet"].tolist()},
        "cuantil_alerta_origen_movil": e["q_movil"].tolist() if "q_movil" in e else None,
        "seleccion_por_horizonte": e["seleccion"]["candidato"].to_dict(),
        "criterio_seleccion": "mínimo RMSE (µg/m³) de validación sobre los mismos pares (origen, h)",
        "semilla": wc.SEMILLA, "versiones": wc.versiones_librerias(),
    }, os.path.join(carpeta, "metadatos.json"))
    print(f"{clave}: guardado en {carpeta}")
