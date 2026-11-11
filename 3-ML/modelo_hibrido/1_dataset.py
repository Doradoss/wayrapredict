# %% [markdown]
# # Experimento: variables sintéticas de actividad industrial/minera (instrucciones_15) — Pasos 1 y 2
#
# **Experimento exploratorio posterior a la evaluación principal; la prueba ya había sido observada.**
# No modifica modelos, selecciones, resultados oficiales, plataforma/ ni la base de datos.
#
# Paso 1: dataset combinado de las 3 estaciones oficiales (La Oroya SO2, Huaraucaca PM10, Ilo-02 PM10),
#         verificación de integridad y relleno de huecos (marcado; nunca se evalúa sobre días rellenados).
# Paso 2: variables de actividad inferidas de forma CAUSAL (solo con información hasta el día t) y, como
#         control de fuga, las mismas variables calculadas con ventana centrada (usan días futuros).
# Ejecutar desde la raíz: python modelo_hibrido/1_dataset.py

# %%
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.abspath("."))
import wayra_comun as wc
import wayra_hibrido as wh

BASE = os.path.join(wc.RAIZ, "modelo_hibrido")
DIR_DAT, DIR_RES, DIR_FIG = (os.path.join(BASE, d) for d in ("datos", "resultados", "figuras"))
for c in (DIR_DAT, DIR_RES, DIR_FIG):
    os.makedirs(c, exist_ok=True)
AVISO = "Experimento exploratorio posterior a la evaluación principal; la prueba ya había sido observada."
METEO = ["TEMPERATURA", "HUMEDAD_RELATIVA", "VELOCIDAD_VIENTO", "PRESION_BAROMETRICA", "PRECIPITACION", "VIENTO_SIN", "VIENTO_COS"]
UNIDADES = {"OBJETIVO": "µg/m³", "TEMPERATURA": "°C", "HUMEDAD_RELATIVA": "%", "VELOCIDAD_VIENTO": "m/s",
            "PRESION_BAROMETRICA": "mmHg", "PRECIPITACION": "mm", "VIENTO_SIN": "-", "VIENTO_COS": "-", "MAXIMO_HORARIO": "µg/m³"}
DOMINIO = {"OBJETIVO": (0, 2000), "TEMPERATURA": (-20, 45), "HUMEDAD_RELATIVA": (1, 100), "VELOCIDAD_VIENTO": (0, 30),
           "PRESION_BAROMETRICA": (400, 800), "PRECIPITACION": (0, 200), "VIENTO_SIN": (-1, 1), "VIENTO_COS": (-1, 1)}
VENTANA_NIVEL = 7          # días de la mediana móvil del nivel de emisión
DESFASE_PENDIENTE = 3      # días para medir la pendiente del nivel
TOL_PENDIENTE = 0.15       # cambio relativo que se considera "subiendo" o "bajando"
UMBRAL_OPERACION_SO2 = 40  # µg/m³: umbral oficial de OPERACION en La Oroya (confirmado por el usuario)


# %% [markdown]
# ## Feriados nacionales del Perú (calendario laboral)

# %%
def pascua(anio):
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def feriados_peru(anios):
    fs = set()
    for a in anios:
        fijos = [(1, 1), (5, 1), (6, 29), (7, 28), (7, 29), (8, 30), (10, 8), (11, 1), (12, 8), (12, 25)]
        if a >= 2022:
            fijos += [(6, 7), (8, 6), (12, 9)]
        if a >= 2023:
            fijos += [(7, 23)]
        fs |= {date(a, m, d) for m, d in fijos}
        p = pascua(a)
        fs |= {p - timedelta(days=3), p - timedelta(days=2)}       # jueves y viernes santo
    return {pd.Timestamp(f) for f in fs}


# %% [markdown]
# ## Paso 1: dataset combinado, integridad y relleno

# %%
partes, integridad, horarios = [], [], {}
for clave, fuente in wc.SERIES_GLOBAL.items():
    cfg = wc.SERIES_POR_FUENTE[fuente][clave]
    wc.SERIES[clave] = cfg
    ds = wc.cargar_dataset(clave, fuente)
    ds = ds[ds["PARTICION"] != "extra"].copy() if "extra" in set(ds["PARTICION"]) else ds.copy()
    ultimo = ds["OBJETIVO"].last_valid_index()
    ds = ds.loc[:ultimo]
    est = cfg["estacion"]
    # series horarias del contaminante (mismas fuentes y reglas que el pipeline oficial)
    fuente_ant = wc.FUENTE_DATOS
    wc.FUENTE_DATOS = fuente
    h = wh.serie_horaria(clave)
    wc.FUENTE_DATOS = fuente_ant
    horarios[est] = h
    d = pd.DataFrame(index=ds.index)
    d["estacion"] = est
    d["departamento"] = cfg["departamento"]
    d["contaminante"] = cfg["contaminante"]
    for c in ["OBJETIVO", "MAXIMO_HORARIO"] + METEO:
        d[c] = ds[c] if c in ds else np.nan
    d["relleno_tipo"] = np.where(ds["OBJETIVO"].isna(), "sin_dato",
                                 np.where(ds.get("RELLENO", pd.Series(0, index=ds.index)).eq(1), "estacion_vecina", "observado"))
    d["PARTICION"] = ds["PARTICION"]
    d["OPERACION_CAUSAL_OFICIAL"] = ds["OPERACION_CAUSAL"] if "OPERACION_CAUSAL" in ds else np.nan
    # integridad
    dup = int(d.index.duplicated().sum())
    completo = pd.date_range(d.index.min(), d.index.max())
    faltan = d["OBJETIVO"].isna()
    rachas = faltan.astype(int).groupby((~faltan).cumsum()).sum()
    fila = {"estacion": est, "contaminante": cfg["contaminante"], "desde": d.index.min().date(), "hasta": d.index.max().date(),
            "dias_calendario": len(completo), "dias_en_dataset": len(d), "duplicados_fecha": dup,
            "dias_sin_contaminante": int(faltan.sum()), "pct_sin_contaminante": round(100 * faltan.mean(), 1),
            "hueco_mas_largo_dias": int(rachas.max()), "huecos_mayores_30d": int((rachas > 30).sum()),
            "dias_estacion_vecina": int((d["relleno_tipo"] == "estacion_vecina").sum()),
            "horas_contaminante": len(h), "zona_horaria": "America/Lima (hora local; verificado: desfase 0 h con el OEFA)"}
    for c in ["OBJETIVO"] + METEO:
        v = d[c].dropna()
        lo, hi = DOMINIO[c]
        fila[f"fuera_dominio_{c}"] = int(((v < lo) | (v > hi)).sum())
    integridad.append(fila)
    partes.append(d)

comb = pd.concat(partes)
comb.index.name = "fecha"
integ = pd.DataFrame(integridad)
print(integ.T.to_string())

# Relleno de huecos (SOLO para que no haya fechas vacías; marcado y nunca usado como objetivo de evaluación):
# valor = mediana del ENTRENAMIENTO de la misma estación y el mismo mes del año (climatología mensual; no usa
# información de validación ni de prueba). Para la meteorología, igual por variable.
rellenado = []
for est, d in comb.groupby("estacion"):
    d = d.copy()
    tr = d["PARTICION"] == "train"
    for c in ["OBJETIVO", "MAXIMO_HORARIO"] + METEO:
        if d[c].notna().any():
            clima = d.loc[tr, c].groupby(d.index[tr].month).median()
            falta = d[c].isna()
            d.loc[falta, c] = pd.Series(d.index[falta].month, index=d.index[falta]).map(clima)
            d[f"{c}_rellenado"] = falta.astype(int)
    d.loc[d["relleno_tipo"] == "sin_dato", "relleno_tipo"] = "climatologia_mensual_train"
    rellenado.append(d)
comb_r = pd.concat(rellenado)
print("Fechas vacías del contaminante tras el relleno:", int(comb_r["OBJETIVO"].isna().sum()))

# %% [markdown]
# ## Paso 2: variables sintéticas de actividad (causales) y su versión con fuga (control)
#
# Para cada estación y día t:
# - nivel_t = mediana de los últimos 7 días (t-6..t) del máximo horario diario (días sin dato no cuentan).
# - intensidad_operacion = posición del nivel_t en la distribución del nivel en el ENTRENAMIENTO (0–1);
#   intensidad_0a5 = la misma, discretizada en 0–5.
# - actividad_industrial: La Oroya = nivel_t >= 40 µg/m³ (regla oficial OPERACION_CAUSAL); Huaraucaca e Ilo-02
#   = intensidad >= 0,5 (nivel por encima de la mediana del entrenamiento).
# - estado_operacion (pendiente del nivel en 3 días, cambio relativo con tolerancia 15 %):
#   A apagado (inactivo y estable o bajando), I iniciando (inactivo y subiendo, o pasó de 0 a 1 en los
#   últimos 3 días), T trabajando (activo y estable o subiendo), D detenido/parando (activo y bajando, o
#   pasó de 1 a 0 en los últimos 3 días).
# - Del horario del día t: hora_pico (hora del máximo), amplitud_diaria ((máx − mín) / (media + 1)) y
#   horas_altas (horas sobre el percentil 75 horario del entrenamiento).
# - Calendario: feriado nacional y fin de semana (se conocen de antemano también para el día pronosticado).
# Todas usan solo información hasta t. La versión "con fuga" usa una mediana centrada (t-3..t+3) y el
# estado con la pendiente hacia adelante: mira días futuros y SOLO sirve como control.

# %%
FER = feriados_peru(range(2017, 2028))


def actividad(d, est, centrada=False):
    tr = d["PARTICION"] == "train"
    base = d["MAXIMO_HORARIO"].where(d["MAXIMO_HORARIO_rellenado"] == 0)
    if centrada:
        nivel = base.rolling(VENTANA_NIVEL, center=True, min_periods=3).median()
        prev = nivel.shift(-DESFASE_PENDIENTE)
        pend = (prev - nivel) / (nivel + 1)
    else:
        nivel = base.rolling(VENTANA_NIVEL, min_periods=3).median()
        pend = (nivel - nivel.shift(DESFASE_PENDIENTE)) / (nivel.shift(DESFASE_PENDIENTE) + 1)
    nivel = nivel.ffill()
    ref = np.sort(nivel[tr].dropna().to_numpy())
    intensidad = pd.Series(np.searchsorted(ref, nivel.to_numpy(), side="right") / max(len(ref), 1), index=d.index)
    intensidad = intensidad.where(nivel.notna())
    if d["contaminante"].iloc[0] == "DIOXIDO_AZUFRE":
        act = (nivel >= UMBRAL_OPERACION_SO2).astype(float)
    else:
        act = (intensidad >= 0.5).astype(float)
    act = act.where(nivel.notna())
    cambio = act.diff(DESFASE_PENDIENTE) if not centrada else act.shift(-DESFASE_PENDIENTE) - act
    sube, baja = pend > TOL_PENDIENTE, pend < -TOL_PENDIENTE
    estado = np.select([(act == 1) & ((cambio < 0) | baja), act == 1,
                        (act == 0) & ((cambio > 0) | sube), act == 0], ["D", "T", "I", "A"], default="")
    sal = pd.DataFrame(index=d.index)
    sal["nivel_emision"] = nivel
    sal["intensidad_operacion"] = intensidad
    sal["intensidad_0a5"] = np.floor(intensidad.clip(0, 0.9999) * 6).where(intensidad.notna())
    sal["actividad_industrial"] = act
    sal["estado_operacion"] = pd.Series(estado, index=d.index).replace("", np.nan)
    return sal


filas, control_fuga = [], []
for est, d in comb_r.groupby("estacion"):
    d = d.copy()
    caus = actividad(d, est)
    fuga = actividad(d, est, centrada=True).add_suffix("_FUGA")
    # variables horarias del día t
    h = horarios[est]
    g = h.groupby(h.index.floor("D"))
    tr_h = h[h.index.floor("D").isin(d.index[d["PARTICION"] == "train"])]
    p75 = tr_h.quantile(0.75)
    diario = pd.DataFrame({"hora_pico": g.apply(lambda s: s.idxmax().hour if s.notna().any() else np.nan),
                           "amplitud_diaria": (g.max() - g.min()) / (g.mean() + 1),
                           "horas_altas": g.apply(lambda s: (s > p75).sum()), "n_horas": g.count()})
    diario = diario[diario["n_horas"] >= 18].drop(columns="n_horas").reindex(d.index)
    d = d.join(caus).join(fuga).join(diario)
    d["feriado"] = d.index.isin(FER).astype(int)
    d["fin_de_semana"] = (d.index.dayofweek >= 5).astype(int)
    filas.append(d)
    if "OPERACION_CAUSAL_OFICIAL" in d and d["OPERACION_CAUSAL_OFICIAL"].notna().any():
        ok = d[["OPERACION_CAUSAL_OFICIAL", "actividad_industrial"]].dropna()
        control_fuga.append({"estacion": est, "coincidencia_con_OPERACION_CAUSAL_oficial": round((ok.iloc[:, 0] == ok.iloc[:, 1]).mean(), 4)})
dataset = pd.concat(filas)
dataset.index.name = "fecha"

# Estadísticas y diagnóstico de fuga: correlación de cada versión con el objetivo del día SIGUIENTE
estad, fuga_diag = [], []
for est, d in dataset.groupby("estacion"):
    obs = d["OBJETIVO"].where(d["relleno_tipo"].isin(["observado", "estacion_vecina"]))
    y1 = obs.shift(-1)
    for v in ["actividad_industrial", "intensidad_operacion", "hora_pico", "amplitud_diaria", "horas_altas", "feriado", "fin_de_semana"]:
        estad.append({"estacion": est, "variable": v, "media": round(d[v].mean(), 3), "faltantes": int(d[v].isna().sum())})
    for e in ["A", "I", "T", "D"]:
        estad.append({"estacion": est, "variable": f"estado_operacion = {e}", "media": round((d["estado_operacion"] == e).mean(), 3),
                      "faltantes": int(d["estado_operacion"].isna().sum())})
    for v in ["intensidad_operacion", "actividad_industrial"]:
        fuga_diag.append({"estacion": est, "variable": v,
                          "r_con_y(t+1)_causal": round(d[v].corr(y1), 3),
                          "r_con_y(t+1)_con_fuga": round(d[f"{v}_FUGA"].corr(y1), 3),
                          "r_con_y(t)_causal": round(d[v].corr(obs), 3)})
estad, fuga_diag = pd.DataFrame(estad), pd.DataFrame(fuga_diag)
print(estad.to_string(index=False))
print(fuga_diag.to_string(index=False))
print(control_fuga)

# %% Guardar
dataset.to_pickle(os.path.join(DIR_DAT, "dataset_combinado_enriquecido.pkl"))
dataset.to_csv(os.path.join(DIR_DAT, "dataset_combinado_enriquecido.csv"), sep=";", encoding="utf-8-sig")
for nombre, df in (("A1_integridad", integ), ("A2_estadisticas_actividad", estad), ("A3_diagnostico_fuga", fuga_diag),
                   ("A4_relleno_por_estacion", dataset.groupby(["estacion", "relleno_tipo"]).size().rename("dias").reset_index())):
    df = df.copy()
    df.insert(0, "nota", AVISO)
    df.to_csv(os.path.join(DIR_RES, f"{nombre}.csv"), sep=";", index=False, encoding="utf-8-sig")
print(dataset.groupby(["estacion", "relleno_tipo"]).size())

# %% Figuras: picos detectados y etiquetas sobre la serie (último año de entrenamiento + validación + prueba)
COL_EST = {"A": "#A5A5A5", "I": "#F2C12E", "T": "#D7263D", "D": "#2F5597"}
NOM = {"CA-CC-01": "La Oroya – SO₂", "CA-HUAR-01": "Huaraucaca – PM₁₀", "CA-ILO-02": "Ilo-02 – PM₁₀"}
fig, axes = plt.subplots(3, 1, figsize=(14, 12))
for ax, (est, d) in zip(axes, dataset.groupby("estacion")):
    d = d.loc[d.index.max() - pd.Timedelta(days=730):]
    obs = d["OBJETIVO"].where(d["relleno_tipo"].isin(["observado", "estacion_vecina"]))
    ax.plot(d.index, obs, color="#404040", lw=0.8, label="Promedio diario observado")
    ax.plot(d.index, d["OBJETIVO"].where(d["relleno_tipo"] == "climatologia_mensual_train"), color="#9DC3E6", lw=0.8,
            label="Relleno climatológico (no se evalúa)")
    ax.plot(d.index, d["nivel_emision"], color="#7030A0", lw=1.2, label="Nivel (mediana causal 7 d del máximo horario)")
    for e, col in COL_EST.items():
        m = d["estado_operacion"] == e
        ax.scatter(d.index[m], np.full(m.sum(), -0.04 * d["nivel_emision"].max()), color=col, s=6, marker="s",
                   label=f"Estado {e}")
    ax.set_yscale("symlog", linthresh=10)
    ax.set_title(f"{NOM[est]}: nivel de emisión y estado de operación inferidos (causales)", fontsize=10)
    ax.set_ylabel("µg/m³ (escala log)")
axes[0].legend(fontsize=7, ncol=3, loc="upper left")
plt.tight_layout()
plt.savefig(os.path.join(DIR_FIG, "A1_etiquetas_actividad.png"), dpi=200, bbox_inches="tight")
plt.close("all")
print("Listo:", os.path.join(DIR_DAT, "dataset_combinado_enriquecido.pkl"))
