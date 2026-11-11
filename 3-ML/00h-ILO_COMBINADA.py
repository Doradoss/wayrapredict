# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Moquegua, alternativa: estaciones de Ilo (CA-ILO-01, CA-ILO-02 base, CA-ILO-03)
#
# instrucciones_3.md. NO entrena modelos, no usa resultados de modelos y no cambia la configuración.
# 1. Códigos de estado de PM10 en Ilo (Envidas) y comprobación con el informe REAS-012-2024 (máximos
#    de 24 h publicados por el OEFA para 2023). 1A.csv no tiene datos de Ilo.
# 2. Cobertura y episodios de cada estación (¿es CA-ILO-02 la mejor base?).
# 3. Coincidencia de CA-ILO-02 con CA-ILO-01 y CA-ILO-03 (total, por temporada y por partición).
# 4. Relleno de CA-ILO-02 (si r >= 0.8): mejor estación primero y la otra como segunda opción, cada una
#    con su ajuste lineal estimado SOLO con los días comunes del entrenamiento.
# 5. Saltos de nivel (presión, ID, nivel medio de los mismos meses entre años).
# 6. Comparación Ilo combinada vs CA-TAL-01 con los cortes de La Oroya y criterios C1-C4.
#
# Entradas: salidas de 00d (02_<est>_5min_ancho.parquet, 03_dataset_CA-ILO-0X_PM10_ar_propia.pkl,
# 01_inventario_archivos.csv, cache/) y 03_dataset_CA-TAL-01_PM10_ar.pkl.

# %%
import glob
import os
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import wayra_comun as wc

sns.set_theme(style="whitegrid")
pd.set_option("display.width", 230)
pd.set_option("display.max_columns", 40)

CARPETA_SALIDA = os.path.join(wc.CARPETA_DATOS, "inventario_estaciones")
CARPETA_CACHE = os.path.join(CARPETA_SALIDA, "cache")
CARPETA_FIG = os.path.join(wc.RAIZ, "figuras", "inventario_estaciones")
RUTA_REAS = os.path.join("Datos_crudos_ILO", "2023", "12-Diciembre", "REAS-012-2024-STEC_Ilo (ene a dic 2023)[R][R][R].pdf")
ESTACIONES = ["CA-ILO-01", "CA-ILO-02", "CA-ILO-03"]
NOMBRES = {"CA-ILO-01": "Ilo-Bolognesi", "CA-ILO-02": "Ilo-Pacocha", "CA-ILO-03": "Ilo-José Pardo"}
BASE = "CA-ILO-02"
INICIO_VAL, INICIO_TEST, FIN_TEST = (pd.Timestamp(x) for x in ("2025-01-01", "2025-09-01", "2026-06-30"))
FIN_TRAIN = INICIO_VAL - pd.Timedelta(days=1)
R_MINIMO = 0.8
# Temporadas en la costa (Ilo): invierno = mayo-octubre; verano = noviembre-abril
MESES_INVIERNO = [5, 6, 7, 8, 9, 10]
UMBRAL_MOD = 0.5 * wc.ECA_24H["PM10"]
ECA = wc.ECA_24H["PM10"]
VENTANAS_LSTM = (7, 14)
MIN_FRACCION_OBSERVADA = 0.5
MIN_DIAS_VAL_TEST, MIN_ANIOS_TRAIN, MIN_DIAS_MES = 100, 2, 10
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre",
            "octubre", "noviembre", "diciembre"]


def temporada(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.where(idx.month.isin(MESES_INVIERNO), "invierno (may-oct)", "verano (nov-abr)")


def particion(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.select([idx < INICIO_VAL, idx < INICIO_TEST, idx <= FIN_TEST], ["train", "val", "test"], "extra")


def coincidencia(c: pd.DataFrame, a: str, b: str) -> dict:
    if len(c) < 3:
        return {"dias_comunes": len(c)}
    return {"dias_comunes": len(c), "r": round(c[a].corr(c[b]), 3),
            "r_spearman": round(c[a].corr(c[b], method="spearman"), 3),
            f"media_{a}": round(c[a].mean(), 1), f"media_{b}": round(c[b].mean(), 1),
            "dif_media_base_menos_otra": round((c[a] - c[b]).mean(), 2),
            "cociente_medias_base_otra": round(c[a].mean() / c[b].mean(), 3),
            "cociente_mediano_diario": round((c[a] / c[b]).replace(np.inf, np.nan).median(), 3)}


propias = {e: pd.read_pickle(os.path.join(wc.CARPETA_DATOS, f"03_dataset_{e}_PM10_ar_propia.pkl")).asfreq("D")
           for e in ESTACIONES}
inv = pd.read_csv(os.path.join(CARPETA_SALIDA, "01_inventario_archivos.csv"), sep=";")
inv = inv[inv["estacion"].isin(ESTACIONES)]

# %% [markdown]
# ## 1. Códigos de estado de PM10 (valores ANTES de filtrar, desde la caché de lectura de 00d)

# %%
import hashlib


def md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


filas = []
for est in ESTACIONES:
    for _, a in inv[(inv["estacion"] == est) & (inv["estado"] == "principal")].iterrows():
        ruta = next(iter(glob.glob(os.path.join("Datos_crudos_ILO", str(a["anio"]), "**", a["archivo"]), recursive=True)
                         + glob.glob(os.path.join("Datos_crudos_ILO", str(a["anio"]), a["archivo"]))), None)
        if ruta is None:
            continue
        caches = glob.glob(os.path.join(CARPETA_CACHE, f"{md5(ruta)}_*.pkl"))
        if not caches:
            continue
        std = pd.read_pickle(caches[0])[0]
        if std is None or "PM10" not in std:
            continue
        cod = std["PM10_ESTADO"].astype("string").str.strip() if "PM10_ESTADO" in std else pd.Series("(sin columna)", index=std.index)
        cod = cod.fillna("(vacío)").str.replace(r"\.0+$", "", regex=True)
        filas.append(pd.DataFrame({"estacion": est, "codigo": cod.to_numpy(), "PM10": std["PM10"].to_numpy(),
                                   "anio": std["FECHA_HORA"].dt.year.to_numpy()}))
cods = pd.concat(filas)
cods["PM10_valido"] = cods["PM10"].where(cods["PM10"] != -9999)
tabla_cod = cods.groupby(["estacion", "codigo"]).agg(
    registros=("PM10", "size"), con_valor=("PM10_valido", "count"), mediana=("PM10_valido", "median"),
    p95=("PM10_valido", lambda x: x.quantile(0.95)), anios=("anio", lambda x: f"{x.min()}-{x.max()}")).round(2)
tabla_cod["%"] = (tabla_cod["registros"] / tabla_cod.groupby(level=0)["registros"].transform("sum") * 100).round(2)
tabla_cod.to_csv(os.path.join(CARPETA_SALIDA, "09_codigos_ILO.csv"), sep=";")
print(tabla_cod.to_string())

# %% [markdown]
# ### Comprobación con el informe REAS-012-2024 (máximo de 24 h de PM10 de 2023 por estación)
#
# El informe del OEFA (datos validados) anota en cada figura de PM10 el máximo de 24 h del periodo.
# Se compara con el máximo diario de la serie propia (criterio: código 1 y "sin columna").

# %%
ref_reas = []
if os.path.exists(RUTA_REAS):
    import pdfplumber
    with pdfplumber.open(RUTA_REAS) as pdf:
        for pag in pdf.pages:
            t = pag.extract_text() or ""
            if "ECA PM10 (24 horas)" not in t:
                continue
            # el pie de figura trae el subíndice del PM ("10") en una línea aparte
            resto = t.split("ECA PM10 (24 horas)")[1]
            valor = re.search(r"(\d+,\d)\s*ug/m3", resto.split("Figura")[0])
            pie = resto.split("Figura")[1] if "Figura" in resto else ""
            est = re.search(r"(CA-ILO-0\d)", pie)
            per = re.search(r"(" + "|".join(MESES_ES) + r")\s+a\s+(" + "|".join(MESES_ES) + r")\s+(?:de\s+)?2023", pie, re.I)
            pag.flush_cache()
            if est and valor and per:
                ini, fin = MESES_ES.index(per.group(1).lower()) + 1, MESES_ES.index(per.group(2).lower()) + 1
                ref_reas.append({"estacion": est.group(1), "periodo": f"{per.group(1)}-{per.group(2)} 2023",
                                 "max_24h_REAS": float(valor.group(1).replace(",", ".")),
                                 "desde": pd.Timestamp(2023, ini, 1),
                                 "hasta": pd.Timestamp(2023, fin, 1) + pd.offsets.MonthEnd(0)})
filas = []
for r in ref_reas:
    s = propias[r["estacion"]]["OBJETIVO"].loc[r["desde"]:r["hasta"]]
    filas.append({**{k: v for k, v in r.items() if k not in ("desde", "hasta")},
                  "max_diario_serie_propia": round(s.max(), 1), "fecha_max": s.idxmax().date() if s.notna().any() else None,
                  "dias_validos_periodo": int(s.notna().sum())})
reas = pd.DataFrame(filas).drop_duplicates(["estacion"])
reas.to_csv(os.path.join(CARPETA_SALIDA, "09_comprobacion_REAS_ILO.csv"), sep=";", index=False)
print(reas.to_string(index=False))

# %% [markdown]
# ## 2. Cobertura y episodios de cada estación de Ilo (¿CA-ILO-02 es la mejor base?)

# %%
filas = []
for est, d in propias.items():
    s = d["OBJETIVO"]
    for p in ("total", "train", "val", "test"):
        g = s if p == "total" else s[particion(s.index) == p]
        filas.append({"estacion": est, "nombre": NOMBRES[est], "particion": p,
                      "desde": g.first_valid_index().date() if g.notna().any() else None,
                      "dias_validos": int(g.notna().sum()), "moderada_o_peor": int((g > UMBRAL_MOD).sum()),
                      "sobre_ECA": int((g > ECA).sum()), "media": round(g.mean(), 1), "p95": round(g.quantile(0.95), 1)})
base_tab = pd.DataFrame(filas)
base_tab.to_csv(os.path.join(CARPETA_SALIDA, "09_cobertura_episodios_ILO.csv"), sep=";", index=False)
print(base_tab.pivot(index="estacion", columns="particion",
                     values=["dias_validos", "moderada_o_peor", "sobre_ECA"]).to_string())

for est, d in propias.items():
    s = d["OBJETIVO"]
    c = (s.notna().groupby(s.index.to_period("M")).mean() * 100).round(0)
    t = c.to_frame("pct").assign(anio=c.index.year, mes=c.index.month).pivot(index="anio", columns="mes", values="pct")
    print(f"\n{est} ({NOMBRES[est]}) - % de días con PM10 diario válido")
    print(t.reindex(columns=range(1, 13)).to_string())

# %% [markdown]
# ## 3. Coincidencia de CA-ILO-02 con CA-ILO-01 y CA-ILO-03

# %%
filas, comunes = [], {}
for otra in [e for e in ESTACIONES if e != BASE]:
    c = pd.concat([propias[BASE]["OBJETIVO"].rename("base"), propias[otra]["OBJETIVO"].rename("otra")], axis=1).dropna()
    comunes[otra] = c
    filas.append({"otra": otra, "grupo": "total", **coincidencia(c, "base", "otra")})
    for t, g in c.groupby(temporada(c.index)):
        filas.append({"otra": otra, "grupo": t, **coincidencia(g, "base", "otra")})
    for p, g in c.groupby(particion(c.index)):
        filas.append({"otra": otra, "grupo": f"partición {p}", **coincidencia(g, "base", "otra")})
coinc = pd.DataFrame(filas)
coinc.to_csv(os.path.join(CARPETA_SALIDA, "09_coincidencia_ILO.csv"), sep=";", index=False)
print(coinc.to_string(index=False))

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
for ax, (otra, c) in zip(axes, comunes.items()):
    ax.scatter(c["otra"], c["base"], s=8, alpha=0.5, color="#4472C4")
    lim = max(c.max().max(), 1) * 1.05
    ax.plot([0, lim], [0, lim], color="grey", ls="--", lw=0.8, label="1:1")
    ax.axhline(UMBRAL_MOD, color="#F2C12E", ls="-.", lw=0.8, label="INCA 50")
    ax.set_title(f"{BASE} vs {otra}: r = {c['base'].corr(c['otra']):.2f} (n = {len(c)})", fontsize=10)
    ax.set_xlabel(f"PM$_{{10}}$ {otra} ({wc.UNIDAD})")
    ax.set_ylabel(f"PM$_{{10}}$ {BASE} ({wc.UNIDAD})")
    ax.legend(fontsize=8)
plt.suptitle("PM$_{10}$ diario en Ilo: días con dato en ambas estaciones")
plt.tight_layout()
plt.savefig(os.path.join(CARPETA_FIG, "fig06_coincidencia_ILO.png"), dpi=300, bbox_inches="tight")
plt.close("all")

# %% [markdown]
# ## 4. Relleno de CA-ILO-02 (solo estaciones con r >= 0.8 en total; ajuste con días comunes de train)

# %%
r_tot = coinc[coinc["grupo"] == "total"].set_index("otra")["r"]
candidatas = [e for e in r_tot.sort_values(ascending=False).index if r_tot[e] >= R_MINIMO]
print("r total con la base:", r_tot.to_dict(), "-> candidatas para rellenar (orden):", candidatas)
RELLENAR = len(candidatas) > 0
if not RELLENAR:
    print("Ninguna estación cumple r >= 0.8: NO se rellena (revisar con el usuario).")

ds = propias[BASE].copy()
ds["RELLENO"] = np.where(ds["OBJETIVO"].notna(), 0.0, np.nan)
ds["RELLENO_ORIGEN"] = np.where(ds["OBJETIVO"].notna(), BASE, "")
ajustes = []
for otra in candidatas:
    tr = comunes[otra].loc[:FIN_TRAIN]
    b, a = np.polyfit(tr["otra"], tr["base"], 1)
    pred = a + b * tr["otra"]
    ajustes.append({"estacion_relleno": otra, "formula": f"{BASE} = {a:.3f} + {b:.3f}·{otra}", "dias_train": len(tr),
                    "R2_train": round(1 - ((tr["base"] - pred) ** 2).sum() / ((tr["base"] - tr["base"].mean()) ** 2).sum(), 3),
                    "RMSE_train": round(np.sqrt(((tr["base"] - pred) ** 2).mean()), 2),
                    "cociente_train": round(tr["base"].mean() / tr["otra"].mean(), 3)})
    otra_aj = (a + b * propias[otra]["OBJETIVO"].reindex(ds.index)).clip(lower=0)
    m = ds["OBJETIVO"].isna() & otra_aj.notna()
    ds.loc[m, "OBJETIVO"] = otra_aj[m]
    ds.loc[m, "MAXIMO_HORARIO"] = (a + b * propias[otra]["MAXIMO_HORARIO"].reindex(ds.index)[m]).clip(lower=0)
    ds.loc[m, "RELLENO"] = 1.0
    ds.loc[m, "RELLENO_ORIGEN"] = otra
    ajustes[-1]["dias_rellenados"] = int(m.sum())
ajustes = pd.DataFrame(ajustes)
if len(ajustes):
    ajustes.to_csv(os.path.join(CARPETA_SALIDA, "09_ajustes_ILO.csv"), sep=";", index=False)
    print(ajustes.to_string(index=False))
ds["RELLENO"] = ds["RELLENO"].fillna(0.0)
ds["INCA"] = wc.valor_inca(ds["OBJETIVO"], "PM10")
ds["CATEGORIA_INCA"] = wc.categoria_inca(ds["OBJETIVO"], "PM10").values
ds["SUPERA_ECA"] = (ds["OBJETIVO"] > ECA).where(ds["OBJETIVO"].notna())
ds["SUPERA_OMS"] = (ds["OBJETIVO"] > wc.OMS_24H["PM10"]).where(ds["OBJETIVO"].notna())
ds = ds.loc[ds["OBJETIVO"].first_valid_index():]
ds.index.name = "FECHA"
# Estación final de Moquegua (instrucciones_4.md): CA-ILO-02 con datos propios, sin relleno; el
# recorte desde jun 2022 lo aplica la configuración (wayra_comun, "inicio_datos")
nombre = f"03_dataset_{BASE}_PM10_ar"
ds.to_pickle(os.path.join(wc.CARPETA_DATOS, f"{nombre}.pkl"))
ds.to_csv(os.path.join(wc.CARPETA_DATOS, f"{nombre}.csv"), sep=";")
print(f"\n{nombre}: {len(ds)} días ({ds.index.min().date()} -> {ds.index.max().date()}); válidos "
      f"{int(ds['OBJETIVO'].notna().sum())}; origen: {ds.loc[ds['OBJETIVO'].notna(), 'RELLENO_ORIGEN'].value_counts().to_dict()}")

fig, ax = plt.subplots(figsize=(13, 4))
colores = {BASE: "#4472C4", "CA-ILO-01": "#C55A11", "CA-ILO-03": "#70AD47"}
for origen, color in colores.items():
    s = ds["OBJETIVO"].where(ds["RELLENO_ORIGEN"] == origen)
    if s.notna().any():
        ax.plot(ds.index, s, lw=0.6, color=color, label=f"{origen} ({'propio' if origen == BASE else 'relleno ajustado'})")
for p, color, et in (("val", "#F2C12E", "validación"), ("test", "#D7263D", "prueba")):
    f = ds.index[particion(ds.index) == p]
    ax.axvspan(f.min(), f.max(), color=color, alpha=0.12, label=et)
ax.axhline(ECA, color="#D7263D", ls="--", lw=0.8, label="ECA 24 h")
ax.axhline(UMBRAL_MOD, color="#F2C12E", ls="-.", lw=0.8, label="INCA 50")
ax.set_title(f"PM$_{{10}}$ diario - {BASE} ({NOMBRES[BASE]}) combinada")
ax.set_ylabel(f"Promedio diario ({wc.UNIDAD})")
ax.set_xlabel("Fecha")
ax.legend(fontsize=8, ncol=4, loc="upper left")
plt.tight_layout()
plt.savefig(os.path.join(CARPETA_FIG, "fig07_serie_combinada_CA-ILO-02.png"), dpi=300, bbox_inches="tight")
plt.close("all")

# %% [markdown]
# ## 5. Saltos de nivel: presión, ID / sitio y nivel medio de los mismos meses entre años

# %%
for est in ESTACIONES:
    i = inv[(inv["estacion"] == est) & (inv["estado"] == "principal")]
    print(f"\n{est}: IDs en los archivos: {i['id_estacion'].dropna().astype(str).value_counts().to_dict()} | "
          f"formatos: {i['formato'].value_counts().to_dict()}")
pres = pd.DataFrame({e: d["PRESION_BAROMETRICA"].groupby(d.index.to_period("M")).median() for e, d in propias.items()})
pres.to_csv(os.path.join(CARPETA_SALIDA, "09_presion_mensual_ILO.csv"), sep=";")
print("\nPresión mediana mensual (mmHg):")
print(pres.round(1).to_string())
print("\nDiferencias de presión entre estaciones por año (mediana, mmHg):")
dif = pd.DataFrame({"ILO01-ILO02": pres["CA-ILO-01"] - pres["CA-ILO-02"], "ILO03-ILO02": pres["CA-ILO-03"] - pres["CA-ILO-02"]})
print(dif.groupby(dif.index.year).median().round(2).to_string())
nivel = pd.DataFrame({e: d["OBJETIVO"].groupby([d.index.year, d.index.month]).mean() for e, d in propias.items()})
nivel.index.names = ["anio", "mes"]
nivel.to_csv(os.path.join(CARPETA_SALIDA, "09_nivel_mensual_ILO.csv"), sep=";")
print("\nPM10 medio por mes del año y año:")
for est in ESTACIONES:
    print(f"\n{est}")
    print(nivel[est].unstack(0).round(1).to_string())

fig, axes = plt.subplots(2, 1, figsize=(13, 6), sharex=True)
for est in ESTACIONES:
    axes[0].plot(pres.index.to_timestamp(), pres[est], marker=".", lw=0.8, label=est)
    m = propias[est]["OBJETIVO"].resample("MS").mean()
    axes[1].plot(m.index, m, marker=".", lw=0.8, label=est)
axes[0].set_ylabel("Presión mediana (mmHg)")
axes[1].set_ylabel(f"PM$_{{10}}$ medio mensual ({wc.UNIDAD})")
axes[0].set_title("Estaciones de Ilo: presión y PM$_{10}$ mensual (saltos de nivel)")
axes[0].legend(fontsize=8)
axes[1].set_xlabel("Fecha")
plt.tight_layout()
plt.savefig(os.path.join(CARPETA_FIG, "fig08_saltos_nivel_ILO.png"), dpi=300, bbox_inches="tight")
plt.close("all")

# %% [markdown]
# ## 6. Ilo combinada vs CA-TAL-01 (cortes de La Oroya, criterios C1-C4)

# %%
def muestras_lstm(s: pd.Series, ventana: int, part: np.ndarray) -> dict:
    obs = s.notna().to_numpy()
    n, salida = len(s), {}
    for i in range(ventana - 1, n - 1):
        if obs[i - ventana + 1:i + 1].mean() < MIN_FRACCION_OBSERVADA or not obs[i + 1:i + 4].any():
            continue
        p = part[min(i + 3, n - 1)]
        salida[p] = salida.get(p, 0) + 1
    return salida


tal = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, "03_dataset_CA-TAL-01_PM10_ar.pkl")).asfreq("D")
series = {f"{BASE} combinada": ds.asfreq("D"), "CA-TAL-01": tal}
filas, crit = [], []
for nombre_s, d in series.items():
    part = particion(d.index)
    rel = d["RELLENO"] if "RELLENO" in d else pd.Series(0.0, index=d.index)
    for p in ("train", "val", "test"):
        m = part == p
        v, r = d.loc[m, "OBJETIVO"], rel[m]
        filas.append({"serie": nombre_s, "particion": p, "dias_validos": int(v.notna().sum()),
                      "propios": int((v.notna() & (r == 0)).sum()), "rellenados": int((r == 1).sum()),
                      "pct_relleno": round((r == 1).sum() / max(v.notna().sum(), 1) * 100, 1),
                      "moderada_o_peor": int((v > UMBRAL_MOD).sum()), "sobre_ECA": int((v > ECA).sum()),
                      "media": round(v.mean(), 1)})
    t = pd.DataFrame(filas)
    t = t[t["serie"] == nombre_s].set_index("particion")
    tr = d.loc[part == "train", "OBJETIVO"].dropna()
    anios = (tr.index.max() - tr.index.min()).days / 365.25 if len(tr) else 0
    meses = int((tr.groupby(tr.index.month).size() >= MIN_DIAS_MES).sum())
    r_c = r_tot[candidatas].max() if nombre_s.startswith(BASE) and candidatas else np.nan
    m7 = muestras_lstm(d["OBJETIVO"], 7, part)
    crit.append({"serie": nombre_s, "train_anios": round(anios, 1), "train_meses_con_>=10_dias": meses,
                 "C1": anios >= MIN_ANIOS_TRAIN and meses == 12,
                 "C2": bool(t.loc["val", "dias_validos"] >= MIN_DIAS_VAL_TEST and t.loc["test", "dias_validos"] >= MIN_DIAS_VAL_TEST),
                 "test_pct_propios": round(t.loc["test", "propios"] / max(t.loc["test", "dias_validos"], 1) * 100, 1),
                 "C3": bool(t.loc["test", "propios"] > t.loc["test", "dias_validos"] / 2),
                 "r_relleno": r_c, "C4": bool(r_c >= R_MINIMO) if pd.notna(r_c) else "no aplica",
                 "alertas_evaluables": bool(t.loc["val", "moderada_o_peor"] > 0 and t.loc["test", "moderada_o_peor"] > 0),
                 "muestras_LSTM_v7_train": m7.get("train", 0),
                 "episodios_antes_de_prueba": int(t.loc["train", "moderada_o_peor"] + t.loc["val", "moderada_o_peor"])})
comp = pd.DataFrame(filas)
crit = pd.DataFrame(crit)
comp.to_csv(os.path.join(CARPETA_SALIDA, "09_comparacion_ILO_TAL_particiones.csv"), sep=";", index=False)
crit.to_csv(os.path.join(CARPETA_SALIDA, "09_comparacion_ILO_TAL_criterios.csv"), sep=";", index=False)
print(comp.to_string(index=False))
print(crit.T.to_string())

filas = []
for nombre_s, d in series.items():
    s = d.loc[particion(d.index) != "test", "OBJETIVO"]
    s = s[particion(s.index) != "extra"]
    for per, g in s.groupby(s.index.to_period("Q")):
        filas.append({"serie": nombre_s, "trimestre": str(per), "moderada_o_peor": int((g > UMBRAL_MOD).sum())})
epi = pd.DataFrame(filas)
epi.to_csv(os.path.join(CARPETA_SALIDA, "09_episodios_trimestre_ILO_TAL.csv"), sep=";", index=False)
print(epi.pivot(index="trimestre", columns="serie", values="moderada_o_peor").fillna(0).astype(int).to_string())
