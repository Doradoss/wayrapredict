# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Notebook 1b: Limpieza y EDA de los datos de alta resolución (por estación)
#
# Estructura:
# - 1b.1 Lectura y unión de todos los archivos (sin duplicados ni solapes)
# - 1b.2 Conversión de unidades (SO2 ppb -> µg/m³; presión hPa -> mmHg)
# - 1b.3 Reglas de calidad (códigos de estado, banderas, periodos anómalos, negativos,
#        dominio, rachas de ceros, valores planos) + bitácora
# - 1b.4 Agregación: registros -> horas (>= 75 % de registros) -> días (>= 18 horas)
# - 1b.5 EDA: cobertura y huecos, régimen de operación, ciclo diario, estacionalidad,
#        distribución INCA, ADF, STL y ACF/PACF
# - 1b.6 Validación cruzada con el dataset del OEFA (periodo común)
# - 1b.7 Dataset diario _v2 (mismo formato que 03_dataset_...) y serie combinada
#
# Se lee con wayra_alta_resolucion.py (solo lectura: no se modifica ningún archivo original).
# NO modifica 01-EDA-CALIDAD_AIRE_v3.py ni sus checkpoints: todo sale con sufijo _v2 /
# _combinada o en checkpoints/alta_resolucion/.
#
# Para otra estación: cambiar ESTACION y completar su entrada en CONFIG_ESTACIONES.

# %%
import os
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

import wayra_alta_resolucion as war
import wayra_comun as wc

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
pd.set_option("display.width", 230)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

# ------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------
ESTACION = "CA-CC-01"

# Configuración específica por estación (confirmada con el usuario para CA-CC-01).
# Estaciones pendientes (CA-SB-01, CA-TO-01): completar tras su inventario y estructura.
CONFIG_ESTACIONES = {
    "CA-CC-01": {
        "departamento": "JUNIN",
        "contaminante": "DIOXIDO_AZUFRE",
        "columna_contaminante": "SO2_PPB",
        "factor_a_ug": 2.62,                # ppb -> µg/m³ (25 °C, 1 atm), como en el script 01
        "columna_estado": "SO2_ESTADO",
        "estados_validos": ["4C000000", "4.00", "4", "0.00", "0", "(vacío)"],
        "estados_si_dominio": ["4C010000"],  # válidos solo si pasan las reglas de dominio
        # Todo otro código es inválido (X, -9999, 4C000400 y los de < 350 registros)
        "banderas_invalidas": ["ND"],        # LD (límite de detección) se conserva
        "presion_hpa_desde": "2025-09-01",   # PBAR en hPa aunque la columna diga mmHg
        # Periodos anómalos: (desde, hasta, variables, motivo)
        "periodos_invalidos": [
            ("2020-11-01", "2021-02-28", ["PBAR"], "PBAR constante ~752 (sensor)"),
            ("2026-02-01", "2026-03-31", ["PBAR", "TEMP", "HR", "WS", "WD", "PP", "RS"],
             "meteorología fuera de rango (TEMP ~142 °C, HR > 100 %, WS ~53 m/s)"),
            ("2026-04-01", "2026-06-30", ["HR"], "HR anómala tras cambio de equipo"),
        ],
        "regimen": True,
    },
}
CFG = CONFIG_ESTACIONES[ESTACION]
CONTAMINANTE = CFG["contaminante"]
CARPETA_ENTRADA = f"Datos_crudos_{ESTACION}"
PATRONES_RESPALDO = [r"^43i ", r"^New_"]
CARPETA_AR = os.path.join(wc.CARPETA_DATOS, "alta_resolucion")
CARPETA_FIG = os.path.join(wc.RAIZ, "figuras", "alta_resolucion")
os.makedirs(CARPETA_AR, exist_ok=True)
os.makedirs(CARPETA_FIG, exist_ok=True)

# Reglas de dominio en unidades finales (µg/m³, mmHg, °C, %, m/s, grados, mm), por registro.
# Para el contaminante, el tope del script 01 (2000 µg/m³) se definió para PROMEDIOS HORARIOS:
# los registros de 5 min pueden superarlo en episodios de fumigación y el OEFA los conserva en
# su promedio horario (verificado: cociente OEFA / promedio crudo = 1.000 en esas horas). Por
# eso, por registro solo se exige >= 0 y el tope se aplica a la media horaria (DOMINIO_HORARIO).
REGLAS_DOMINIO = {
    "CONTAMINANTE": (0, np.inf), "PBAR": (400, 800), "TEMP": (-20, 45), "HR": (1, 100),
    "WS": (0, 60), "WD": (0, 360), "PP": (0, 100), "RS": (0, 1500),
}
DOMINIO_HORARIO = {"CONTAMINANTE": (0, 2000)}   # igual que REGLAS_DOMINIO del script 01
RACHA_CEROS_MIN = 30          # ceros consecutivos del contaminante durante >= 30 min: inválidos
# Valores idénticos consecutivos durante >= N minutos: sospechosos (se excluyen los ceros de
# viento y precipitación, que pueden ser reales: calma y días secos)
PLANOS_MIN = {"CONTAMINANTE": 60, "TEMP": 180, "HR": 180, "WS": 180, "WD": 180, "PBAR": 720}
MIN_FRACCION_HORA = 0.75       # una hora es válida con >= 75 % de sus registros
MIN_HORAS_DIA = 18             # un día es válido con >= 18 horas válidas
UMBRAL_OPERACION = wc.UMBRAL_OPERACION
VENTANA_OPERACION = wc.VENTANA_OPERACION
VARIABLES_MET = ["PBAR", "TEMP", "HR", "WS", "WD", "PP", "RS"]
NOMBRES_DATASET = {"PBAR": "PRESION_BAROMETRICA", "TEMP": "TEMPERATURA", "HR": "HUMEDAD_RELATIVA",
                   "WS": "VELOCIDAD_VIENTO", "PP": "PRECIPITACION", "RS": "RADIACION_SOLAR"}

bitacora = []
MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]


def registrar(paso: str, n: int, detalle: str = ""):
    bitacora.append({"paso": paso, "registros": n, "detalle": detalle})


def guardar_fig(nombre: str, ejes_fecha=()):
    """Guarda la figura (PNG, 300 dpi). Si se indican ejes con fechas, guarda además una
    versión para la tesis sin años visibles (solo el mes en el eje X)."""
    plt.savefig(os.path.join(CARPETA_FIG, f"{nombre}.png"), dpi=300, bbox_inches="tight")
    if ejes_fecha:
        import matplotlib.dates as mdates
        for ax in ejes_fecha:
            ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
            ax.xaxis.set_major_formatter(mticker.FuncFormatter(
                lambda x, _: MESES_ES[mdates.num2date(x).month - 1]))
            ax.set_xlabel("Mes")
        plt.savefig(os.path.join(CARPETA_FIG, f"{nombre}_sin_anio.png"), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close("all")


# %% [markdown]
# ## 1b.1 Lectura y unión de todos los archivos

# %%
archivos = war.listar_archivos(CARPETA_ENTRADA)
es_respaldo = archivos["archivo"].apply(lambda n: any(re.search(p, n) for p in PATRONES_RESPALDO))
print(f"Archivos: {len(archivos)} | principales: {(~es_respaldo).sum()} | respaldo (no se usan): {es_respaldo.sum()}")
archivos = archivos[~es_respaldo]

partes = []
for _, a in archivos.iterrows():
    df, meta = war.leer_archivo(a["ruta"])
    est, det = war.estandarizar(df, a["anio"], a["mes"])
    paso = est["FECHA_HORA"].dropna().sort_values().diff().dt.total_seconds().div(60).mode()
    est["PASO_MIN"] = float(paso.iloc[0]) if len(paso) else np.nan
    est["ARCHIVO"] = a["archivo"]
    partes.append(est)
crudo = pd.concat(partes, ignore_index=True)
registrar("Registros leídos (archivos principales)", len(crudo))

crudo = crudo.dropna(subset=["FECHA_HORA"])
registrar("Con fecha-hora válida", len(crudo), "se descartan filas vacías al final de algunos archivos")

# Marca de tiempo al minuto (algunos archivos traen segundos del registro en la BD)
crudo["FECHA_HORA"] = crudo["FECHA_HORA"].dt.floor("min")
crudo = crudo.sort_values(["FECHA_HORA", "ARCHIVO"])
n_dup = int(crudo.duplicated("FECHA_HORA").sum())
crudo = crudo.drop_duplicates("FECHA_HORA", keep="first").reset_index(drop=True)
registrar("Sin registros duplicados o solapados entre archivos", len(crudo), f"{n_dup:,} eliminados")
print(f"Periodo: {crudo['FECHA_HORA'].min()} -> {crudo['FECHA_HORA'].max()} | "
      f"registros: {len(crudo):,} | duplicados/solapes eliminados: {n_dup:,}")
print(crudo.groupby("PASO_MIN").size().rename("registros").to_string())

# %% [markdown]
# ## 1b.2 Conversión de unidades

# %%
crudo["CONTAMINANTE"] = crudo[CFG["columna_contaminante"]] * CFG["factor_a_ug"]
if CFG.get("presion_hpa_desde"):
    m = crudo["FECHA_HORA"] >= pd.Timestamp(CFG["presion_hpa_desde"])
    crudo.loc[m, "PBAR"] = crudo.loc[m, "PBAR"] * 0.750062
    print(f"PBAR convertida de hPa a mmHg desde {CFG['presion_hpa_desde']}: {int(m.sum()):,} registros")
print("Mediana mensual de PBAR tras la conversión (esperado ~485-492 mmHg):")
print(crudo.groupby(crudo["FECHA_HORA"].dt.to_period("Q"))["PBAR"].median().round(1).to_string())

# %% [markdown]
# ## 1b.3 Reglas de calidad
#
# Cada regla marca como inválidos los valores de las variables afectadas (no borra filas).
# La tabla resultante es la bitácora de calidad para la tesis.

# %%
calidad = []
VARIABLES_QC = ["CONTAMINANTE"] + [v for v in VARIABLES_MET if v in crudo]
valido = pd.DataFrame(True, index=crudo.index, columns=VARIABLES_QC)
valido &= crudo[VARIABLES_QC].notna().to_numpy()


def aplicar(regla: str, variable: str, mascara_invalida: pd.Series):
    nuevos = int((valido[variable] & mascara_invalida).sum())
    valido.loc[mascara_invalida, variable] = False
    calidad.append({"regla": regla, "variable": variable, "registros_invalidados": nuevos})


# (a) Códigos de estado del analizador
estado = crudo[CFG["columna_estado"]].fillna("(vacío)").astype(str).str.strip()
en_validos = estado.isin(CFG["estados_validos"])
condicional = estado.isin(CFG["estados_si_dominio"])
lo, hi = REGLAS_DOMINIO["CONTAMINANTE"]
cond_ok = condicional & crudo["CONTAMINANTE"].between(lo, hi)
aplicar("Código de estado inválido", "CONTAMINANTE", ~(en_validos | cond_ok))
print("Códigos de estado -> tratamiento:")
print(pd.DataFrame({"registros": estado.value_counts()}).assign(
    tratamiento=lambda d: np.where(d.index.isin(CFG["estados_validos"]), "válido",
                                   np.where(d.index.isin(CFG["estados_si_dominio"]),
                                            "válido si pasa dominio", "inválido"))).to_string())

# (b) Banderas de validación (ND = no disponible; LD se conserva)
for col, variables in (("BANDERA_SO2", ["CONTAMINANTE"]), ("BANDERA_MET", VARIABLES_QC[1:])):
    if col in crudo:
        m = crudo[col].isin(CFG["banderas_invalidas"])
        for v in variables:
            aplicar(f"Bandera {'/'.join(CFG['banderas_invalidas'])}", v, m)

# (c) Periodos anómalos confirmados
for desde, hasta, variables, motivo in CFG["periodos_invalidos"]:
    m = crudo["FECHA_HORA"].between(pd.Timestamp(desde), pd.Timestamp(hasta) + pd.Timedelta(days=1)
                                     - pd.Timedelta(minutes=1))
    for v in variables:
        if v in valido:
            aplicar(f"Periodo anómalo {desde}..{hasta}: {motivo}", v, m)

# (d) Negativos y reglas de dominio
aplicar("Valor negativo", "CONTAMINANTE", crudo["CONTAMINANTE"] < 0)
for v, (lo, hi) in REGLAS_DOMINIO.items():
    if v in valido:
        aplicar(f"Fuera de dominio [{lo}, {hi}]", v, ~crudo[v].between(lo, hi) & crudo[v].notna())


# (e) Rachas de ceros y valores planos (duración en minutos, según el paso de cada registro)
def rachas(serie: pd.Series, condicion: pd.Series) -> pd.Series:
    """Duración (min) de la racha de valores iguales a la que pertenece cada registro,
    cortando la racha en huecos de tiempo mayores al paso."""
    t = crudo["FECHA_HORA"]
    salto = t.diff().dt.total_seconds().div(60) > crudo["PASO_MIN"] * 1.5
    cambio = (serie != serie.shift()) | salto | (condicion != condicion.shift())
    grupo = cambio.cumsum()
    return crudo["PASO_MIN"].groupby(grupo).transform("sum").where(condicion, 0)


es_cero = crudo["CONTAMINANTE"] == 0
aplicar(f"Racha de ceros >= {RACHA_CEROS_MIN} min", "CONTAMINANTE",
        rachas(crudo["CONTAMINANTE"], es_cero) >= RACHA_CEROS_MIN)
for v, minutos in PLANOS_MIN.items():
    if v in valido:
        cond = crudo[v].notna() & ~((crudo[v] == 0) & (v in ("WS", "PP", "CONTAMINANTE")))
        aplicar(f"Valor plano >= {minutos} min", v, rachas(crudo[v], cond) >= minutos)

tabla_calidad = pd.DataFrame(calidad)
tabla_calidad = tabla_calidad[tabla_calidad["registros_invalidados"] > 0]
resumen_validos = pd.DataFrame({"registros_con_dato": crudo[VARIABLES_QC].notna().sum(),
                                "registros_validos": valido.sum()})
resumen_validos["% válido"] = (resumen_validos["registros_validos"]
                               / resumen_validos["registros_con_dato"] * 100).round(2)
tabla_calidad.to_csv(os.path.join(CARPETA_AR, f"02_bitacora_calidad_{ESTACION}.csv"), sep=";", index=False)
print(tabla_calidad.to_string(index=False))
print(resumen_validos.to_string())
registrar("Registros con contaminante válido", int(valido["CONTAMINANTE"].sum()))

# %% [markdown]
# ## 1b.4 Agregación: registros -> horas -> días
#
# - Hora válida: >= 75 % de los registros esperados (60 / paso) con valor válido.
# - Día válido: >= 18 horas válidas.
# - Precipitación: suma. Dirección del viento: promedio vectorial (seno y coseno).
# - La hora se asigna con floor (misma convención que el OEFA: desfase 0 h verificado).

# %%
base = crudo[["FECHA_HORA", "PASO_MIN"]].copy()
base["HORA"] = base["FECHA_HORA"].dt.floor("h")
for v in VARIABLES_QC:
    base[v] = crudo[v].where(valido[v])
rad = np.deg2rad(base["WD"]) if "WD" in base else None
if rad is not None:
    base["WD_SIN"], base["WD_COS"] = np.sin(rad), np.cos(rad)

g = base.groupby("HORA")
esperados = 60 / g["PASO_MIN"].agg(lambda s: s.mode().iloc[0])
horario = pd.DataFrame(index=esperados.index)
for v in VARIABLES_QC:
    frac = g[v].count() / esperados
    ok = frac >= MIN_FRACCION_HORA
    if v == "PP":
        horario[v] = g[v].sum(min_count=1).where(ok)
    elif v == "WD":
        horario["WD_SIN"] = g["WD_SIN"].mean().where(ok)
        horario["WD_COS"] = g["WD_COS"].mean().where(ok)
    else:
        horario[v] = g[v].mean().where(ok)
horario = horario.asfreq("h")
horario.index.name = "FECHA_HORA"
for v, (lo, hi) in DOMINIO_HORARIO.items():
    fuera = ~horario[v].between(lo, hi) & horario[v].notna()
    horario.loc[fuera, v] = np.nan
    calidad.append({"regla": f"Media horaria fuera de dominio [{lo}, {hi}]", "variable": v,
                    "registros_invalidados": f"{int(fuera.sum())} horas"})
    print(f"Horas de {v} con media fuera de [{lo}, {hi}] (invalidadas, como en el script 01): {int(fuera.sum())}")
pd.DataFrame(calidad).to_csv(os.path.join(CARPETA_AR, f"02_bitacora_calidad_{ESTACION}.csv"), sep=";", index=False)
registrar("Horas con contaminante válido (>= 75 %)", int(horario["CONTAMINANTE"].notna().sum()))
print(f"Horas: {len(horario):,} | con contaminante válido: {horario['CONTAMINANTE'].notna().sum():,} "
      f"({horario['CONTAMINANTE'].notna().mean() * 100:.1f} %)")

gd = horario.groupby(horario.index.floor("D"))
diario = pd.DataFrame(index=gd.size().index)
for v in [c for c in horario.columns]:
    horas = gd[v].count()
    ok = horas >= MIN_HORAS_DIA
    diario[v] = (gd[v].sum(min_count=1) if v == "PP" else gd[v].mean()).where(ok)
diario["MAXIMO_HORARIO"] = gd["CONTAMINANTE"].max().where(gd["CONTAMINANTE"].count() >= MIN_HORAS_DIA)
diario["HORAS_VALIDAS"] = gd["CONTAMINANTE"].count()
diario = diario.asfreq("D")
diario.index.name = "FECHA"
registrar("Días con contaminante válido (>= 18 h)", int(diario["CONTAMINANTE"].notna().sum()))
print(f"Días: {len(diario):,} | con contaminante válido: {diario['CONTAMINANTE'].notna().sum():,} "
      f"({diario['CONTAMINANTE'].notna().mean() * 100:.1f} %)")

tabla_bitacora = pd.DataFrame(bitacora)
tabla_bitacora.to_csv(os.path.join(CARPETA_AR, f"02_bitacora_limpieza_{ESTACION}.csv"), sep=";", index=False)
print(tabla_bitacora.to_string(index=False))

# %% [markdown]
# ## 1b.5 EDA
# ### Cobertura y huecos

# %%
cob = (diario["CONTAMINANTE"].notna().groupby(diario.index.to_period("M")).mean() * 100).round(1)
tabla_cob = cob.to_frame("% días válidos").assign(anio=lambda d: d.index.year, mes=lambda d: d.index.month) \
    .pivot(index="anio", columns="mes", values="% días válidos")
tabla_cob.columns = MESES_ES[:len(tabla_cob.columns)] if len(tabla_cob.columns) == 12 else tabla_cob.columns
tabla_cob.to_csv(os.path.join(CARPETA_AR, f"02_cobertura_mensual_{ESTACION}.csv"), sep=";")
print("% de días con contaminante válido por mes:")
print(tabla_cob.to_string())

hueco = diario["CONTAMINANTE"].isna()
bloques = (hueco != hueco.shift()).cumsum()
huecos = (diario[hueco].groupby(bloques[hueco])
          .apply(lambda d: pd.Series({"desde": d.index.min().date(), "hasta": d.index.max().date(),
                                      "dias": len(d)})))
huecos = huecos[huecos["dias"] >= 3].sort_values("desde")
print(f"\nHuecos de 3 o más días: {len(huecos)}")
print(huecos.to_string(index=False))

fig, ax = plt.subplots(figsize=(10, 0.5 * len(tabla_cob) + 1.5))
sns.heatmap(tabla_cob, cmap="Blues", vmin=0, vmax=100, annot=True, fmt=".0f", ax=ax,
            cbar_kws={"label": "% días válidos"})
ax.set_title(f"{ESTACION}: disponibilidad mensual de {wc.NOMBRE_VAR[CONTAMINANTE]} (alta resolución)")
ax.set_xlabel("Mes")
ax.set_ylabel("")
guardar_fig(f"fig01b_disponibilidad_{ESTACION}")

# %% [markdown]
# ### Régimen de operación (histograma del máximo horario diario y umbral)
#
# Este periodo incluye la reactivación del complejo metalúrgico: se revisa si el umbral de
# 40 µg/m³ sigue cayendo en el valle entre los dos modos.

# %%
if CFG["regimen"]:
    s = diario["MAXIMO_HORARIO"]
    log_s = np.log10(s.dropna().clip(lower=0.1))
    conteo, bordes = np.histogram(log_s, bins=60)
    centros = (bordes[:-1] + bordes[1:]) / 2
    suave = pd.Series(conteo).rolling(5, center=True, min_periods=1).mean().to_numpy()
    zona = (centros > np.log10(10)) & (centros < np.log10(300))
    valle = 10 ** centros[zona][np.argmin(suave[zona])]
    print(f"Valle del histograma (suavizado) entre 10 y 300 µg/m³: ~{valle:.0f} µg/m³ | "
          f"umbral vigente: {UMBRAL_OPERACION} µg/m³")
    for u in (20, 30, UMBRAL_OPERACION, 60, 80):
        print(f"  umbral {u:>3}: {(s > u).mean() * 100:5.1f} % de los días con máximo horario > umbral")

    mediana = s.rolling(VENTANA_OPERACION, center=True, min_periods=3).median()
    diario["OPERACION"] = (mediana > UMBRAL_OPERACION).astype(float).where(mediana.notna())
    mediana_c = s.rolling(VENTANA_OPERACION, min_periods=3).median()
    diario["OPERACION_CAUSAL"] = (mediana_c > UMBRAL_OPERACION).astype(float).where(mediana_c.notna())
    print(f"Días con OPERACION = 1: {diario['OPERACION'].eq(1).mean() * 100:.1f} % | "
          f"coincidencia centrada vs causal: "
          f"{(diario['OPERACION'] == diario['OPERACION_CAUSAL']).where(diario['OPERACION'].notna() & diario['OPERACION_CAUSAL'].notna()).mean() * 100:.1f} %")
    print("\n% de días operando por año:")
    print((diario["OPERACION"].groupby(diario.index.year).mean() * 100).round(1).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(15, 4), gridspec_kw={"width_ratios": [1, 2.5]})
    axes[0].hist(log_s, bins=60, color="#4472C4")
    axes[0].axvline(np.log10(UMBRAL_OPERACION), color="red", ls="--", label=f"umbral {UMBRAL_OPERACION} {wc.UNIDAD}")
    axes[0].axvline(np.log10(valle), color="orange", ls=":", label=f"valle ~{valle:.0f} {wc.UNIDAD}")
    axes[0].set_title(f"{ESTACION}: máximo horario diario de {wc.NOMBRE_VAR[CONTAMINANTE]}")
    axes[0].set_xlabel(f"log$_{{10}}$ (máximo horario, {wc.UNIDAD})")
    axes[0].set_ylabel("N.º de días")
    axes[0].legend(fontsize=8)
    axes[1].plot(s.index, s.values, lw=0.6, color="#4472C4", label="máximo horario diario")
    axes[1].fill_between(diario.index, 0, np.nanmax(s.values), where=diario["OPERACION"].eq(1),
                         color="orange", alpha=0.15, label="OPERACION = 1")
    axes[1].set_title(f"{ESTACION}: régimen de operación estimado (alta resolución)")
    axes[1].set_ylabel(wc.UNIDAD)
    axes[1].set_xlabel("Fecha")
    axes[1].legend(loc="upper left", fontsize=8)
    plt.tight_layout()
    guardar_fig(f"fig02b_regimen_operacion_{ESTACION}", ejes_fecha=[axes[1]])

# %% [markdown]
# ### Serie diaria con ECA, guía OMS e INCA

# %%
eca, oms = wc.ECA_24H[CONTAMINANTE], wc.OMS_24H[CONTAMINANTE]
fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(diario.index, diario["CONTAMINANTE"], lw=0.7, color="#4472C4", label="promedio diario")
ax.axhline(eca, color="#D7263D", ls="--", label=f"ECA 24 h ({eca} {wc.UNIDAD})")
ax.axhline(oms, color="#2E9E44", ls=":", label=f"Guía OMS 24 h ({oms} {wc.UNIDAD})")
ax.axhline(eca * 0.5, color="#F2C12E", ls="-.", lw=0.8, label="INCA 50 (Buena/Moderada)")
ax.set_title(f"{wc.NOMBRE_VAR[CONTAMINANTE]} - {ESTACION} ({wc.NOMBRE_DEP[CFG['departamento']]}): "
             "promedio diario (alta resolución)")
ax.set_ylabel(f"Concentración ({wc.UNIDAD})")
ax.set_xlabel("Fecha")
ax.legend(fontsize=8, ncol=4, loc="upper left")
plt.tight_layout()
guardar_fig(f"fig03b_serie_diaria_{ESTACION}", ejes_fecha=[ax])

# %% [markdown]
# ### Ciclo diario (por régimen) y estacionalidad mensual

# %%
h = horario[["CONTAMINANTE"]].dropna().assign(HORA=lambda d: d.index.hour, FECHA=lambda d: d.index.floor("D"))
if CFG["regimen"]:
    h["REGIMEN"] = h["FECHA"].map(diario["OPERACION"]).map({1.0: "Operando", 0.0: "Detenida"})
fig, axes = plt.subplots(1, 2, figsize=(14, 4))
if CFG["regimen"]:
    sns.lineplot(data=h.dropna(subset=["REGIMEN"]), x="HORA", y="CONTAMINANTE", hue="REGIMEN",
                 estimator="median", errorbar=("pi", 50), ax=axes[0])
    print("Hora del máximo de la mediana horaria (operando):",
          int(h[h["REGIMEN"] == "Operando"].groupby("HORA")["CONTAMINANTE"].median().idxmax()), "h")
else:
    sns.lineplot(data=h, x="HORA", y="CONTAMINANTE", estimator="median", errorbar=("pi", 50), ax=axes[0])
axes[0].set_title(f"Ciclo diario de {wc.NOMBRE_VAR[CONTAMINANTE]} (mediana y RIC)")
axes[0].set_xlabel("Hora del día (hora de Perú)")
axes[0].set_ylabel(f"Concentración horaria ({wc.UNIDAD})")
d = diario.dropna(subset=["CONTAMINANTE"])
sns.boxplot(x=d.index.month, y=d["CONTAMINANTE"], ax=axes[1], color="#4472C4", fliersize=2)
axes[1].axhline(eca, color="#D7263D", ls="--", lw=1, label="ECA 24 h")
axes[1].set_xticklabels(MESES_ES)
axes[1].set_title("Variación mensual del promedio diario")
axes[1].set_xlabel("Mes")
axes[1].set_ylabel(f"Promedio diario ({wc.UNIDAD})")
axes[1].legend(fontsize=8)
plt.tight_layout()
guardar_fig(f"fig05b_ciclo_estacionalidad_{ESTACION}")

# %% [markdown]
# ### Distribución INCA, ECA y guía OMS (por año; en la tesis no se muestran los años)

# %%
d = diario.dropna(subset=["CONTAMINANTE"]).copy()
d["CATEGORIA_INCA"] = wc.categoria_inca(d["CONTAMINANTE"], CONTAMINANTE).values
tabla_inca = pd.crosstab(d.index.year, d["CATEGORIA_INCA"], normalize="index").mul(100).round(1)
tabla_inca = tabla_inca.reindex(columns=[c for c in wc.CATEGORIAS_INCA if c in tabla_inca.columns])
tabla_inca["días válidos"] = d.groupby(d.index.year).size()
tabla_inca["días > ECA"] = (d["CONTAMINANTE"] > eca).groupby(d.index.year).sum()
tabla_inca["% días > OMS"] = ((d["CONTAMINANTE"] > oms).groupby(d.index.year).mean() * 100).round(1)
total = pd.Series({c: round((d["CATEGORIA_INCA"] == c).mean() * 100, 1) for c in tabla_inca.columns
                   if c in wc.CATEGORIAS_INCA})
total["días válidos"] = len(d)
total["días > ECA"] = int((d["CONTAMINANTE"] > eca).sum())
total["% días > OMS"] = round((d["CONTAMINANTE"] > oms).mean() * 100, 1)
tabla_inca.loc["Total"] = total
tabla_inca.to_csv(os.path.join(CARPETA_AR, f"02_tabla_inca_{ESTACION}.csv"), sep=";")
print(tabla_inca.to_string())

# %% [markdown]
# ### Estacionariedad (ADF), STL y ACF/PACF

# %%
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.seasonal import STL
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

s = diario["CONTAMINANTE"].interpolate(limit=7).dropna()
estad, p, *_ = adfuller(s, autolag="AIC")
print(f"ADF: estadístico={estad:.3f}, p-valor={p:.4f} -> "
      f"{'estacionaria' if p < 0.05 else 'no estacionaria'} (p<0.05), n={len(s)} "
      "(interpolación de huecos <= 7 días solo para esta prueba)")
pd.DataFrame([{"Estación": ESTACION, "Contaminante": CONTAMINANTE, "n": len(s), "ADF": round(estad, 3),
               "p-valor": round(p, 4)}]).to_csv(os.path.join(CARPETA_AR, f"02_tabla_adf_{ESTACION}.csv"),
                                                sep=";", index=False)
# STL sobre el tramo continuo más largo (STL no admite huecos)
serie_c = diario["CONTAMINANTE"].interpolate(limit=7, limit_area="inside")
bloque = serie_c.notna().ne(serie_c.notna().shift()).cumsum()
largo = serie_c.notna().groupby(bloque).transform("sum").where(serie_c.notna(), 0)
tramo = serie_c[bloque == bloque[largo.idxmax()]]
periodo = 365 if len(tramo) >= 2 * 365 else 7
print(f"STL sobre el tramo continuo más largo: {tramo.index.min().date()} -> {tramo.index.max().date()} "
      f"({len(tramo)} días, periodo = {periodo})")
stl = STL(tramo, period=periodo, robust=True).fit()
fig = stl.plot()
fig.set_size_inches(12, 7)
fig.suptitle(f"Descomposición STL - {wc.NOMBRE_VAR[CONTAMINANTE]} {ESTACION} ({wc.UNIDAD})", y=1.02)
guardar_fig(f"fig09b_stl_{ESTACION}", ejes_fecha=fig.axes)

fig, axes = plt.subplots(1, 2, figsize=(13, 3.5))
plot_acf(s, lags=60, ax=axes[0], title=f"ACF - {wc.NOMBRE_VAR[CONTAMINANTE]} {ESTACION}")
plot_pacf(s, lags=60, ax=axes[1], title=f"PACF - {wc.NOMBRE_VAR[CONTAMINANTE]} {ESTACION}", method="ywm")
for ax in axes:
    ax.set_xlabel("Rezago (días)")
plt.tight_layout()
guardar_fig(f"fig10b_acf_pacf_{ESTACION}")

# %% [markdown]
# ## 1b.6 Validación cruzada con el dataset del OEFA (periodo común)

# %%
clave = f"{ESTACION}_{CONTAMINANTE}"
original = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, f"03_dataset_{clave}.pkl"))
pares = {"OBJETIVO": "CONTAMINANTE", "TEMPERATURA": "TEMP", "HUMEDAD_RELATIVA": "HR",
         "VELOCIDAD_VIENTO": "WS", "PRESION_BAROMETRICA": "PBAR", "PRECIPITACION": "PP"}
filas_val = []
for col_o, col_n in pares.items():
    if col_o in original and col_n in diario:
        comun = pd.concat([original[col_o].rename("oefa"), diario[col_n].rename("nuevo")],
                          axis=1, join="inner").dropna()
        if len(comun) < 10:
            continue
        dif = comun["nuevo"] - comun["oefa"]
        filas_val.append({"variable": col_o, "dias_comunes": len(comun),
                          "desde": comun.index.min().date(), "hasta": comun.index.max().date(),
                          "correlacion": round(comun["oefa"].corr(comun["nuevo"]), 4),
                          "dif_media": round(dif.mean(), 3), "dif_absoluta_media": round(dif.abs().mean(), 3),
                          "media_oefa": round(comun["oefa"].mean(), 2), "media_nuevo": round(comun["nuevo"].mean(), 2)})
validacion = pd.DataFrame(filas_val)
validacion.to_csv(os.path.join(CARPETA_AR, f"02_validacion_cruzada_{ESTACION}.csv"), sep=";", index=False)
print(validacion.to_string(index=False))
solo_oefa = original["OBJETIVO"].notna() & ~original.index.isin(diario.index[diario["CONTAMINANTE"].notna()])
solo_nuevo = diario["CONTAMINANTE"].notna() & ~diario.index.isin(original.index[original["OBJETIVO"].notna()])
rango_comun = (diario.index >= original.index.min()) & (diario.index <= original.index.max())
print(f"En el periodo común: días válidos solo en el OEFA = {int(solo_oefa[original.index >= diario.index.min()].sum())}, "
      f"solo en los datos nuevos = {int(solo_nuevo[rango_comun].sum())}")

comun = pd.concat([original["OBJETIVO"].rename("oefa"), diario["CONTAMINANTE"].rename("nuevo")],
                  axis=1, join="inner").dropna()
fig, ax = plt.subplots(figsize=(5.5, 5))
ax.scatter(comun["oefa"], comun["nuevo"], s=8, alpha=0.5, color="#4472C4")
lim = [0, max(comun.max()) * 1.05]
ax.plot(lim, lim, color="black", lw=0.8, ls="--", label="1:1")
ax.set_xlim(lim)
ax.set_ylim(lim)
ax.set_xlabel(f"OEFA (1A.csv), promedio diario ({wc.UNIDAD})")
ax.set_ylabel(f"Alta resolución, promedio diario ({wc.UNIDAD})")
ax.set_title(f"{wc.NOMBRE_VAR[CONTAMINANTE]} - {ESTACION}: validación cruzada\n"
             f"r = {comun['oefa'].corr(comun['nuevo']):.4f}, n = {len(comun)} días")
ax.legend()
guardar_fig(f"fig11b_validacion_cruzada_{ESTACION}")

# %% [markdown]
# ## 1b.7 Dataset diario _v2 y serie combinada
#
# Mismo formato que 03_dataset_<estación>_<contaminante>.pkl del script 01. La serie combinada
# usa el dataset del OEFA hasta el día anterior al inicio de los datos nuevos y los datos
# nuevos desde entonces; el régimen de operación se recalcula sobre la serie combinada.

# %%
def armar_dataset(d: pd.DataFrame) -> pd.DataFrame:
    ds = pd.DataFrame(index=d.index)
    ds["OBJETIVO"] = d["CONTAMINANTE"]
    ds["INCA"] = wc.valor_inca(ds["OBJETIVO"], CONTAMINANTE)
    ds["CATEGORIA_INCA"] = wc.categoria_inca(ds["OBJETIVO"], CONTAMINANTE).values
    ds["SUPERA_ECA"] = (ds["OBJETIVO"] > eca).where(ds["OBJETIVO"].notna())
    ds["SUPERA_OMS"] = (ds["OBJETIVO"] > oms).where(ds["OBJETIVO"].notna())
    for v, nombre in NOMBRES_DATASET.items():
        if v in d and nombre in original.columns:
            ds[nombre] = d[v]
    ds["VIENTO_SIN"], ds["VIENTO_COS"] = d.get("WD_SIN"), d.get("WD_COS")
    ds["MAXIMO_HORARIO"] = d["MAXIMO_HORARIO"]
    return ds


def agregar_regimen_y_calendario(ds: pd.DataFrame) -> pd.DataFrame:
    ds = ds.asfreq("D")
    if CFG["regimen"]:
        s = ds["MAXIMO_HORARIO"]
        med = s.rolling(VENTANA_OPERACION, center=True, min_periods=3).median()
        ds["OPERACION"] = (med > UMBRAL_OPERACION).astype(float).where(med.notna())
        med_c = s.rolling(VENTANA_OPERACION, min_periods=3).median()
        ds["OPERACION_CAUSAL"] = (med_c > UMBRAL_OPERACION).astype(float).where(med_c.notna())
    ds["DIA_SEMANA"] = ds.index.dayofweek
    ds["MES"] = ds.index.month
    ds.insert(0, "CONTAMINANTE", CONTAMINANTE)
    ds.insert(0, "NOMBRE_PUNTO", ESTACION)
    ds.insert(0, "DEPARTAMENTO", CFG["departamento"])
    ds.index.name = "FECHA"
    return ds


def guardar_dataset(ds: pd.DataFrame, sufijo: str):
    nombre = f"03_dataset_{clave}{sufijo}"
    ds.to_pickle(os.path.join(wc.CARPETA_DATOS, f"{nombre}.pkl"))
    ds.to_csv(os.path.join(wc.CARPETA_DATOS, f"{nombre}.csv"), sep=";")
    compl = ds.drop(columns=["DEPARTAMENTO", "NOMBRE_PUNTO", "CONTAMINANTE"]).notna().mean().mul(100)
    print(f"\n{nombre}: {len(ds):,} días ({ds.index.min().date()} -> {ds.index.max().date()})")
    print(compl.round(1).to_string())


# Dataset _v2 (solo datos nuevos)
v2 = agregar_regimen_y_calendario(armar_dataset(diario))
faltan = [c for c in original.columns if c not in v2.columns]
print("Columnas del dataset original que no están en _v2:", faltan or "ninguna")
guardar_dataset(v2, "_v2")

# Serie combinada: OEFA antes del inicio de los datos nuevos + datos nuevos desde entonces.
# El máximo horario diario del tramo OEFA se toma del checkpoint horario del script 01.
inicio_nuevo = diario.index[diario["CONTAMINANTE"].notna()].min()
tramo_oefa = original.loc[:inicio_nuevo - pd.Timedelta(days=1)].copy()
horario_oefa = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, "01_mediciones_marcadas.pkl"))
horario_oefa = horario_oefa[(horario_oefa["NOMBRE_PUNTO"] == ESTACION) & (horario_oefa["VARIABLE"] == CONTAMINANTE)
                            & ~horario_oefa["FLAG_DOMINIO"] & ~horario_oefa["FLAG_CERO_RACHA"]]
gmax = horario_oefa.groupby("FECHA")["VALOR"].agg(["max", "size"])
tramo_oefa["MAXIMO_HORARIO"] = gmax["max"].where(gmax["size"] >= MIN_HORAS_DIA).reindex(tramo_oefa.index)
columnas = [c for c in v2.columns if c not in ("DEPARTAMENTO", "NOMBRE_PUNTO", "CONTAMINANTE",
                                                "OPERACION", "OPERACION_CAUSAL", "DIA_SEMANA", "MES")]
combinada = pd.concat([tramo_oefa.reindex(columns=columnas), v2.loc[inicio_nuevo:, columnas]])
combinada["FUENTE"] = np.where(combinada.index < inicio_nuevo, "OEFA (1A.csv)", "alta resolución")
combinada = agregar_regimen_y_calendario(combinada)
guardar_dataset(combinada, "_combinada")
print(f"\nSerie combinada: OEFA {combinada.index.min().date()} -> {(inicio_nuevo - pd.Timedelta(days=1)).date()} "
      f"+ alta resolución {inicio_nuevo.date()} -> {combinada.index.max().date()}")

# Tabla horaria (por si se modela a nivel horario más adelante)
horario.to_pickle(os.path.join(CARPETA_AR, f"03_dataset_horario_{ESTACION}_v2.pkl"))

# %% [markdown]
# ## Resumen de la fase
#
# - Se unieron todos los archivos principales (sin duplicados ni solapes), se convirtieron las
#   unidades y se aplicaron las reglas de calidad confirmadas (bitácora 02_bitacora_*).
# - Agregación 5 min -> hora (>= 75 %) -> día (>= 18 h), con los criterios del script 01.
# - EDA de la estación y revisión del umbral de operación con la reactivación del complejo.
# - Validación cruzada con el OEFA en el periodo común (02_validacion_cruzada_*).
# - Datasets 03_dataset_<estación>_<contaminante>_v2 y _combinada, con el formato del original.
