# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Pasco: CA-HUAR-01 (Huaraucaca) como base, rellenada con CA-COLQ-01 (Colquijirca)
#
# instrucciones_2.md. NO entrena modelos y no usa resultados de modelos.
# 1. Códigos de estado de CA-HUAR-01: misma comprobación que en CA-COLQ-01 (horario validado del
#    OEFA en 1A.csv, dic 2021).
# 2. Coincidencia HUAR vs COLQ en los días en que ambas tienen dato (r, diferencia media, cociente
#    de niveles), en total y por temporada. Si r < 0.8 (criterio fijado por el usuario) se detiene.
# 3. Ajuste de COLQ al nivel de HUAR con una regresión lineal estimada SOLO con los días comunes
#    del entrenamiento (<= 2024-12-31).
# 4. Serie combinada: HUAR propia + COLQ ajustada en los días sin dato de HUAR (columna RELLENO).
# 5. Factibilidad con los cortes de La Oroya (CA-HUAR-01 combinada y CA-TAL-01) y criterios.
#
# Entradas: salidas de 00d (02_<est>_5min_ancho.parquet, 02_<est>_diario.pkl,
# 03_dataset_CA-HUAR-01_PM10_ar_propia.pkl, 03_dataset_CA-COLQ-01_PM10_ar.pkl, 03_dataset_CA-TAL-01_PM10_ar.pkl).

# %%
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import wayra_comun as wc

sns.set_theme(style="whitegrid")
pd.set_option("display.width", 230)
pd.set_option("display.max_columns", 30)

FUENTE = "pasco_moquegua"
CARPETA_SALIDA = os.path.join(wc.CARPETA_DATOS, "inventario_estaciones")
CARPETA_FIG = os.path.join(wc.RAIZ, "figuras", "inventario_estaciones")
RUTA_1A = os.path.join(wc.RAIZ, "1A.csv")
BASE, RELLENO = "CA-HUAR-01", "CA-COLQ-01"
FIN_TRAIN = pd.Timestamp("2024-12-31")            # mismo corte que La Oroya (cortes A)
INICIO_VAL, INICIO_TEST, FIN_TEST = (pd.Timestamp(x) for x in ("2025-01-01", "2025-09-01", "2026-06-30"))
R_MINIMO = 0.8                                     # coincidencia mínima (criterio del usuario)
# Temporadas (Andes centrales): seca = mayo-setiembre (estiaje); húmeda = octubre-abril
MESES_SECA = [5, 6, 7, 8, 9]
UMBRAL_MOD = 0.5 * wc.ECA_24H["PM10"]             # INCA > 50
ECA = wc.ECA_24H["PM10"]
VENTANAS_LSTM = (7, 14)
MIN_FRACCION_OBSERVADA = 0.5
MIN_DIAS_VAL_TEST = 100
MIN_ANIOS_TRAIN = 2
MIN_DIAS_MES = 10        # un mes del año "cubierto" en train si suma >= 10 días válidos


def temporada(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.where(idx.month.isin(MESES_SECA), "seca (may-set)", "húmeda (oct-abr)")


def particion(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.select([idx < INICIO_VAL, idx < INICIO_TEST, idx <= FIN_TEST], ["train", "val", "test"], "extra")


def coincidencia(c: pd.DataFrame) -> dict:
    return {"dias_comunes": len(c), "r": round(c["HUAR"].corr(c["COLQ"]), 3),
            "r_spearman": round(c["HUAR"].corr(c["COLQ"], method="spearman"), 3),
            "media_HUAR": round(c["HUAR"].mean(), 1), "media_COLQ": round(c["COLQ"].mean(), 1),
            "dif_media_HUAR_menos_COLQ": round((c["HUAR"] - c["COLQ"]).mean(), 2),
            "cociente_medias_HUAR_COLQ": round(c["HUAR"].mean() / c["COLQ"].mean(), 3),
            "cociente_mediano_diario": round((c["HUAR"] / c["COLQ"]).replace(np.inf, np.nan).median(), 3)}


# %% [markdown]
# ## 1. Códigos de estado de CA-HUAR-01 contra el horario validado del OEFA (1A.csv)
#
# CA-HUAR-01 está en 1A.csv solo en diciembre de 2021, con HORA_INICIO vacía y sin departamento
# (por eso el script 01 no la incluyó). La hora se reconstruye como en el script 01: orden de las
# filas en grupos (evaluación, estación, fecha) de exactamente 24 filas.

# %%
ruta_cache_1a = os.path.join(CARPETA_SALIDA, "08_1A_CA-HUAR-01_PM10_horario.pkl")
if os.path.exists(ruta_cache_1a):
    oefa = pd.read_pickle(ruta_cache_1a)
else:
    partes = []
    for bloque in pd.read_csv(RUTA_1A, sep=";", dtype=str, chunksize=200_000,
                              usecols=["NOMBRE_EVALUACION", "NOMBRE_PUNTO", "PERIODO", "FECHA_INICIO", "PM10"]):
        b = bloque[(bloque["NOMBRE_PUNTO"] == BASE) & (bloque["PERIODO"] == "1 hora") & (bloque["PM10"] != "-")]
        if len(b):
            partes.append(b)
    o = pd.concat(partes)
    g = o.groupby(["NOMBRE_EVALUACION", "FECHA_INICIO"])
    o = o[g["PM10"].transform("size") == 24].copy()
    o["HORA"] = o.groupby(["NOMBRE_EVALUACION", "FECHA_INICIO"]).cumcount()
    o["FECHA_HORA"] = pd.to_datetime(o["FECHA_INICIO"]) + pd.to_timedelta(o["HORA"], unit="h")
    oefa = pd.to_numeric(o.set_index("FECHA_HORA")["PM10"], errors="coerce").groupby(level=0).mean()
    oefa.to_pickle(ruta_cache_1a)
print(f"1A.csv - {BASE} PM10 horario: {oefa.notna().sum()} horas ({oefa.index.min()} -> {oefa.index.max()})")

ancho = pd.read_parquet(os.path.join(CARPETA_SALIDA, f"02_{BASE}_5min_ancho.parquet"))
cod = ancho["PM10_ESTADO"].astype("string").str.strip().fillna("(vacío)")
cod = cod.where(pd.to_numeric(cod, errors="coerce").isna(),
                pd.to_numeric(cod, errors="coerce").map(lambda x: str(int(x)) if pd.notna(x) else x))


def horario(pm10: pd.Series, paso: pd.Series) -> pd.Series:
    g = pm10.groupby(pm10.index.floor("h"))
    esperados = 60 / paso.groupby(paso.index.floor("h")).min().clip(lower=1)
    return g.mean().where(g.count() / esperados >= 0.75)


# Referencias validadas: 1A.csv (horario, dic 2021) y el libro de VALIDACION de marzo 2023
# (BD5_N3_1H horario y BD6_N3_24H diario, bandera VA = dato válido del especialista). Solo se usan
# para comprobar los códigos, no como fuente de datos.
RUTA_VALIDACION = os.path.join("Datos_crudos_CA-HUAR-01", "2023", "3-Marzo",
                               "CA-HUAR_01_VALIDACION_01-31_MARZ_2023 - SSOTO.xlsx")
ref = {"1A.csv horario (dic 2021)": oefa}
if os.path.exists(RUTA_VALIDACION):
    h5 = pd.read_excel(RUTA_VALIDACION, sheet_name="BD5_N3_1H", dtype=str)
    h5 = h5[h5["B_PM10_UGM3"] == "VA"]
    ref["VALIDACION horario N3 (mar 2023)"] = pd.to_numeric(h5["PM10_CONC"], errors="coerce").set_axis(
        pd.to_datetime(h5["date"]).dt.floor("h"))
    d6 = pd.read_excel(RUTA_VALIDACION, sheet_name="BD6_N3_24H", dtype=str)
    d6 = d6[d6["B_PM10_UGM3"] == "VA"]
    ref["VALIDACION diario N3 (mar 2023)"] = pd.to_numeric(d6["PM10_UGM3"], errors="coerce").set_axis(
        pd.to_datetime(d6["date"]).dt.floor("D"))

filas = []
for nombre, mascara in (("0, 8, 9 y 1 (criterio de CA-HUAR-01)", cod.isin(["0", "8", "9", "1"])),
                        ("0 y 8 (criterio de COLQ y TAL)", cod.isin(["0", "8"]))):
    h = horario(ancho["PM10"].where(mascara), ancho["PASO_MIN"])
    gd = h.groupby(h.index.floor("D"))
    d = gd.mean().where(gd.count() >= 18)
    for nombre_ref, r in ref.items():
        nuevo = d if "diario" in nombre_ref else h
        c = pd.concat([r.rename("ref"), nuevo.rename("nuevo")], axis=1, join="inner")
        c = c[c["ref"].notna()]
        ambos = c.dropna()
        filas.append({"codigos_validos": nombre, "referencia": nombre_ref, "periodos_ref": len(c),
                      "periodos_con_dato_nuevo": int(c["nuevo"].notna().sum()),
                      "pct_identicos_(±0.1)": round(((ambos["ref"] - ambos["nuevo"]).abs() <= 0.1).mean() * 100, 1)
                      if len(ambos) else np.nan,
                      "r": round(ambos.corr().iloc[0, 1], 4) if len(ambos) > 2 else np.nan,
                      "dif_media": round((ambos["nuevo"] - ambos["ref"]).mean(), 3) if len(ambos) else np.nan})
codigos_val = pd.DataFrame(filas)
codigos_val.to_csv(os.path.join(CARPETA_SALIDA, "08_codigos_CA-HUAR-01_vs_1A.csv"), sep=";", index=False)
print(codigos_val.to_string(index=False))
print("\nCódigos de PM10_ESTADO en CA-HUAR-01 (registros):")
print(cod.value_counts().head(12).to_string())

# %% [markdown]
# ## 2. Coincidencia HUAR vs COLQ en los días con dato en ambas

# %%
propia = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, f"03_dataset_{BASE}_PM10_ar_propia.pkl")).asfreq("D")
colq = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, f"03_dataset_{RELLENO}_PM10_ar.pkl")).asfreq("D")
par = pd.concat([propia["OBJETIVO"].rename("HUAR"), colq["OBJETIVO"].rename("COLQ")], axis=1)
comunes = par.dropna()
filas = [{"grupo": "total", **coincidencia(comunes)}]
for t, g in comunes.groupby(temporada(comunes.index)):
    filas.append({"grupo": t, **coincidencia(g)})
for p, g in comunes.groupby(particion(comunes.index)):
    filas.append({"grupo": f"partición {p}", **coincidencia(g)})
coinc = pd.DataFrame(filas)
coinc.to_csv(os.path.join(CARPETA_SALIDA, "08_coincidencia_HUAR_COLQ.csv"), sep=";", index=False)
print(coinc.to_string(index=False))
print(f"\nDías con dato: HUAR {par['HUAR'].notna().sum()}, COLQ {par['COLQ'].notna().sum()}, ambos {len(comunes)}, "
      f"solo COLQ (rellenables) {(par['HUAR'].isna() & par['COLQ'].notna()).sum()}")

r_total = coinc.loc[coinc["grupo"] == "total", "r"].iloc[0]
COINCIDENCIA_ALTA = bool(r_total >= R_MINIMO)
print(f"\nCoincidencia {'ALTA' if COINCIDENCIA_ALTA else 'BAJA'}: r total = {r_total} (mínimo {R_MINIMO}).")
for _, f in coinc[coinc["grupo"].str.startswith(("seca", "húmeda"))].iterrows():
    if f["r"] < R_MINIMO:
        print(f"  AVISO: r en la temporada {f['grupo']} = {f['r']} < {R_MINIMO}")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
for ax, (t, g) in zip(axes, comunes.groupby(temporada(comunes.index))):
    ax.scatter(g["COLQ"], g["HUAR"], s=8, alpha=0.5, color="#4472C4")
    lim = max(g.max().max(), 1) * 1.05
    ax.plot([0, lim], [0, lim], color="grey", ls="--", lw=0.8, label="1:1")
    ax.axhline(UMBRAL_MOD, color="#F2C12E", ls="-.", lw=0.8, label="INCA 50")
    ax.set_title(f"Temporada {t}: r = {g['HUAR'].corr(g['COLQ']):.2f} (n = {len(g)})", fontsize=10)
    ax.set_xlabel(f"PM$_{{10}}$ CA-COLQ-01 ({wc.UNIDAD})")
    ax.set_ylabel(f"PM$_{{10}}$ CA-HUAR-01 ({wc.UNIDAD})")
    ax.legend(fontsize=8)
plt.suptitle("PM$_{10}$ diario: Huaraucaca vs Colquijirca en los días con dato en ambas")
plt.tight_layout()
plt.savefig(os.path.join(CARPETA_FIG, "fig04_coincidencia_HUAR_COLQ.png"), dpi=300, bbox_inches="tight")
plt.close("all")

# %% [markdown]
# ## 3. Ajuste de COLQ al nivel de HUAR (solo con los días comunes del entrenamiento)
#
# Regresión lineal HUAR = a + b·COLQ (mínimos cuadrados), estimada con los días comunes <= 2024-12-31.
# El cociente de medias se reporta como referencia. No se usa información de validación ni de prueba.

# %%
if not COINCIDENCIA_ALTA:
    raise SystemExit("Coincidencia baja: no se rellena. Revisar con el usuario antes de seguir.")
tr = comunes.loc[:FIN_TRAIN]
b, a = np.polyfit(tr["COLQ"], tr["HUAR"], 1)
cociente = tr["HUAR"].mean() / tr["COLQ"].mean()
pred_lin, pred_coc = a + b * tr["COLQ"], cociente * tr["COLQ"]
ajuste = pd.DataFrame([
    {"transformacion": "lineal (elegida)", "formula": f"HUAR = {a:.3f} + {b:.3f}·COLQ", "dias_train": len(tr),
     "R2_train": round(1 - ((tr["HUAR"] - pred_lin) ** 2).sum() / ((tr["HUAR"] - tr["HUAR"].mean()) ** 2).sum(), 3),
     "RMSE_train": round(np.sqrt(((tr["HUAR"] - pred_lin) ** 2).mean()), 2)},
    {"transformacion": "cociente (referencia)", "formula": f"HUAR = {cociente:.3f}·COLQ", "dias_train": len(tr),
     "R2_train": round(1 - ((tr["HUAR"] - pred_coc) ** 2).sum() / ((tr["HUAR"] - tr["HUAR"].mean()) ** 2).sum(), 3),
     "RMSE_train": round(np.sqrt(((tr["HUAR"] - pred_coc) ** 2).mean()), 2)}])
ajuste.to_csv(os.path.join(CARPETA_SALIDA, "08_ajuste_COLQ_a_HUAR.csv"), sep=";", index=False)
print(ajuste.to_string(index=False))

# %% [markdown]
# ## 4. Serie combinada CA-HUAR-01 (RELLENO = 0 propio, 1 = Colquijirca ajustada)

# %%
inicio = min(propia["OBJETIVO"].first_valid_index(), colq["OBJETIVO"].first_valid_index())
idx = pd.date_range(inicio, max(propia.index.max(), colq.index.max()), freq="D")
ds = propia.reindex(idx)
colq_aj = (a + b * colq["OBJETIVO"].reindex(idx)).clip(lower=0)
rellenar = ds["OBJETIVO"].isna() & colq_aj.notna()
ds["RELLENO"] = np.where(rellenar, 1.0, 0.0)
ds.loc[rellenar, "OBJETIVO"] = colq_aj[rellenar]
# Máximo horario de los días rellenados: el de COLQ con la misma transformación
ds.loc[rellenar, "MAXIMO_HORARIO"] = (a + b * colq["MAXIMO_HORARIO"].reindex(idx)[rellenar]).clip(lower=0)
ds["INCA"] = wc.valor_inca(ds["OBJETIVO"], "PM10")
ds["CATEGORIA_INCA"] = wc.categoria_inca(ds["OBJETIVO"], "PM10").values
ds["SUPERA_ECA"] = (ds["OBJETIVO"] > ECA).where(ds["OBJETIVO"].notna())
ds["SUPERA_OMS"] = (ds["OBJETIVO"] > wc.OMS_24H["PM10"]).where(ds["OBJETIVO"].notna())
ds["DEPARTAMENTO"], ds["NOMBRE_PUNTO"], ds["CONTAMINANTE"] = "PASCO", BASE, "PM10"
ds["DIA_SEMANA"], ds["MES"] = ds.index.dayofweek, ds.index.month
ds = ds.loc[ds["OBJETIVO"].first_valid_index():]
ds.index.name = "FECHA"
nombre = f"03_dataset_{BASE}_PM10_ar"
ds.to_pickle(os.path.join(wc.CARPETA_DATOS, f"{nombre}.pkl"))
ds.to_csv(os.path.join(wc.CARPETA_DATOS, f"{nombre}.csv"), sep=";")
print(f"{nombre}: {len(ds)} días ({ds.index.min().date()} -> {ds.index.max().date()}); PM10 válido "
      f"{ds['OBJETIVO'].notna().sum()} (propios {int((ds['RELLENO'] == 0).sum() - ds['OBJETIVO'].isna().sum())}, "
      f"rellenados {int(ds['RELLENO'].sum())})")

fig, ax = plt.subplots(figsize=(13, 4))
prop = ds["OBJETIVO"].where(ds["RELLENO"] == 0)
rell = ds["OBJETIVO"].where(ds["RELLENO"] == 1)
ax.plot(ds.index, prop, lw=0.6, color="#4472C4", label="CA-HUAR-01 (propio)")
ax.plot(ds.index, rell, lw=0.6, color="#C55A11", label="rellenado con CA-COLQ-01 ajustada")
for p, color, etiqueta in (("val", "#F2C12E", "validación"), ("test", "#D7263D", "prueba")):
    f = ds.index[particion(ds.index) == p]
    ax.axvspan(f.min(), f.max(), color=color, alpha=0.12, label=etiqueta)
ax.axhline(ECA, color="#D7263D", ls="--", lw=0.8, label="ECA 24 h")
ax.axhline(UMBRAL_MOD, color="#F2C12E", ls="-.", lw=0.8, label="INCA 50")
ax.set_title("PM$_{10}$ diario - CA-HUAR-01 combinada (Huaraucaca + Colquijirca ajustada)")
ax.set_ylabel(f"Promedio diario ({wc.UNIDAD})")
ax.set_xlabel("Fecha")
ax.legend(fontsize=8, ncol=6, loc="upper left")
plt.tight_layout()
plt.savefig(os.path.join(CARPETA_FIG, "fig05_serie_combinada_CA-HUAR-01.png"), dpi=300, bbox_inches="tight")
plt.close("all")

# %% [markdown]
# ## 5. Factibilidad con los cortes de La Oroya (sin entrenar)

# %%
def muestras_lstm(s: pd.Series, ventana: int, part: pd.Series) -> dict:
    """Orígenes con ventana válida (>= 50 % de días observados) y algún objetivo en t+1..t+3,
    asignados a la partición de su último objetivo (como en 03/04c)."""
    obs = s.notna().to_numpy()
    n, salida = len(s), {}
    for i in range(ventana - 1, n - 1):
        if obs[i - ventana + 1:i + 1].mean() < MIN_FRACCION_OBSERVADA or not obs[i + 1:i + 4].any():
            continue
        p = part.iloc[min(i + 3, n - 1)]
        salida[p] = salida.get(p, 0) + 1
    return salida


series = {"CA-HUAR-01_PM10": wc.cargar_dataset("CA-HUAR-01_PM10", FUENTE),
          "CA-TAL-01_PM10": wc.cargar_dataset("CA-TAL-01_PM10", FUENTE)}
filas = []
for clave, d in series.items():
    rel = d["RELLENO"] if "RELLENO" in d else pd.Series(0.0, index=d.index)
    for p in ("train", "val", "test"):
        g = d[d["PARTICION"] == p]
        v, r = g["OBJETIVO"], rel[g.index]
        filas.append({"serie": clave, "particion": p, "desde": g.index.min().date(), "hasta": g.index.max().date(),
                      "dias": len(g), "dias_validos": int(v.notna().sum()),
                      "propios": int((v.notna() & (r == 0)).sum()), "rellenados": int((r == 1).sum()),
                      "moderada_o_peor": int((v > UMBRAL_MOD).sum()),
                      "moderada_o_peor_propios": int(((v > UMBRAL_MOD) & (r == 0)).sum()),
                      "sobre_ECA": int((v > ECA).sum()), "media": round(v.mean(), 1)})
part_tab = pd.DataFrame(filas)
part_tab.to_csv(os.path.join(CARPETA_SALIDA, "08_factibilidad_particiones.csv"), sep=";", index=False)
print(part_tab.to_string(index=False))

# Criterios de datos (fijados por el usuario antes de ver resultados de modelos)
criterios, cc = [], wc.cargar_dataset("CA-CC-01_DIOXIDO_AZUFRE", "combinada")
for clave, d in series.items():
    t = part_tab[part_tab["serie"] == clave].set_index("particion")
    tr = d.loc[d["PARTICION"] == "train", "OBJETIVO"].dropna()
    anios = (tr.index.max() - tr.index.min()).days / 365.25
    meses = int((tr.groupby(tr.index.month).size() >= MIN_DIAS_MES).sum())
    r_c = r_total if clave.startswith(BASE) else np.nan
    m = {w: muestras_lstm(d["OBJETIVO"], w, d["PARTICION"]) for w in VENTANAS_LSTM}
    criterios.append({
        "serie": clave,
        "train_anios": round(anios, 1), "train_meses_del_anio_con_>=10_dias": meses,
        "C1_train_>=2_anios_y_12_meses": anios >= MIN_ANIOS_TRAIN and meses == 12,
        "val_dias_validos": int(t.loc["val", "dias_validos"]), "test_dias_validos": int(t.loc["test", "dias_validos"]),
        "C2_val_y_test_>=100_dias": bool(t.loc["val", "dias_validos"] >= MIN_DIAS_VAL_TEST
                                        and t.loc["test", "dias_validos"] >= MIN_DIAS_VAL_TEST),
        "test_pct_propios": round(t.loc["test", "propios"] / max(t.loc["test", "dias_validos"], 1) * 100, 1),
        "C3_mayoria_test_propia": bool(t.loc["test", "propios"] > t.loc["test", "dias_validos"] / 2),
        "r_dias_comunes": r_c, "C4_r_>=0.8": bool(r_c >= R_MINIMO) if pd.notna(r_c) else "no aplica (sin relleno)",
        "alertas_evaluables_en_prueba": bool(t.loc["val", "moderada_o_peor"] > 0 and t.loc["test", "moderada_o_peor"] > 0),
        **{f"muestras_LSTM_v{w}_train": m[w].get("train", 0) for w in VENTANAS_LSTM}})
crit = pd.DataFrame(criterios)
crit.to_csv(os.path.join(CARPETA_SALIDA, "08_factibilidad_criterios.csv"), sep=";", index=False)
print(crit.T.to_string())
m_cc = muestras_lstm(cc["OBJETIVO"], 7, cc["PARTICION"]).get("train", 0)
print(f"\nLSTM global (ventana 7, train): CC-01 {m_cc} + HUAR {crit.iloc[0]['muestras_LSTM_v7_train']} + "
      f"TAL {crit.iloc[1]['muestras_LSTM_v7_train']} = {m_cc + crit['muestras_LSTM_v7_train'].sum()}")

# Episodios por trimestre antes de la prueba (insumo de la calibración con origen móvil)
filas = []
for clave, d in series.items():
    s = d.loc[d["PARTICION"].isin(["train", "val"]), "OBJETIVO"]
    for per, g in s.groupby(s.index.to_period("Q")):
        filas.append({"serie": clave, "trimestre": str(per), "dias_validos": int(g.notna().sum()),
                      "moderada_o_peor": int((g > UMBRAL_MOD).sum())})
epi = pd.DataFrame(filas)
epi.to_csv(os.path.join(CARPETA_SALIDA, "08_episodios_por_trimestre.csv"), sep=";", index=False)
print(epi.pivot(index="trimestre", columns="serie", values="moderada_o_peor").fillna(0).astype(int).to_string())
