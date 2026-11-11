# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Notebook 1 (v3): Colecta, limpieza, EDA y transformación - datos OEFA
#
# Estructura:
# - 2.1 Colectar los datos
#     - 2.1.b (Opcional) Meteorología externa Open-Meteo / ERA5-Land
# - 2.2 Calidad y limpieza
#     - 2.2.1 Formato "una fila = una medición"
#     - 2.2.2 Periodos y unidades de SO2
#     - 2.2.3 Fecha y hora (reconstrucción + validación contra el valor oficial 24 h)
#     - 2.2.4 Duplicados
#     - 2.2.5 Reglas de dominio y rachas de ceros
#     - 2.2.6 Bitácora de limpieza
# - 2.3 EDA
#     - 2.3.1 Estadística descriptiva
#     - 2.3.2 Cobertura por estación y selección de series de modelado
#     - 2.3.3 Serie diaria (criterio 75%) + INCA + ECA
#     - 2.3.4 Régimen de operación de la fuente (CA-CC-01)
#     - 2.3.5 Figuras para la tesis
#     - 2.3.6 Correlaciones por estación
#     - 2.3.7 Estacionariedad, descomposición y autocorrelación
# - 2.4 Transformación: dataset diario por serie (input de modelado)
#
# Cambios v3 respecto a v2:
#  - Se recuperan describe(), histogramas, boxplots y la sección opcional de Open-Meteo
#    (ahora por estación y con ERA5-Land).
#  - Selección automática de series con criterios explícitos (para el Cap. 5).
#  - Semáforo INCA (R.M. 181-2016-MINAM) calculado junto con el ECA y la guía OMS.
#  - Variable de régimen de operación de la fuente (riesgo R02 del Project Charter).
#  - Agregación diaria correcta por tipo de variable: la precipitación se SUMA y la
#    dirección del viento se promedia como vector (seno/coseno).
#  - Prueba ADF, descomposición STL y ACF/PACF.
#  - Todas las figuras se guardan en PNG (300 dpi) en la carpeta "figuras".
#  - Bitácora de limpieza (tabla de filas por paso, lista para la tesis).

# %%
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 200)

# ------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------
RUTA_DATOS = "1A.csv"  # En Colab: "/content/drive/MyDrive/Tesis/data/1A.csv"
DEPARTAMENTOS_PILOTO = ["JUNIN", "PASCO", "MOQUEGUA"]
CARPETA_CHECKPOINTS = "checkpoints"
CARPETA_FIGURAS = "figuras"
os.makedirs(CARPETA_CHECKPOINTS, exist_ok=True)
os.makedirs(CARPETA_FIGURAS, exist_ok=True)

COLUMNAS_MEDICION = [
    "DIOXIDO_AZUFRE", "DIRECCION_VIENTO", "HUMEDAD_RELATIVA", "PM10", "PM2.5",
    "MONOXIDO_CARBONO", "OZONO", "PRECIPITACION", "PRESION_BAROMETRICA",
    "RADIACION_SOLAR", "SULFURO_HIDROGENO", "TEMPERATURA", "VELOCIDAD_VIENTO",
]
COLUMNAS_USADAS = [
    "NOMBRE_EVALUACION", "NOMBRE_PUNTO", "ESTE", "NORTE", "ALTITUD", "ZONA",
    "DEPARTAMENTO", "PROVINCIA", "DISTRITO", "TIPO_ANALISIS", "PERIODO",
    "FECHA_INICIO", "HORA_INICIO", "UNIDAD_MEDIDA", "FECHA_CORTE",
] + COLUMNAS_MEDICION

CONTAMINANTES = ["PM2.5", "PM10", "DIOXIDO_AZUFRE"]
METEOROLOGICAS = ["TEMPERATURA", "HUMEDAD_RELATIVA", "VELOCIDAD_VIENTO",
                  "PRESION_BAROMETRICA", "PRECIPITACION", "DIRECCION_VIENTO"]

# Umbrales normativos (ug/m3, 24 h)
ECA_24H = {"PM2.5": 50, "PM10": 100, "DIOXIDO_AZUFRE": 250}        # D.S. 003-2017-MINAM
OMS_24H = {"PM2.5": 15, "PM10": 45, "DIOXIDO_AZUFRE": 40}          # Guías OMS 2021
# Valor umbral del estado de cuidado (VUEC) -> límite naranja/rojo del INCA.
# VERIFICAR en D.S. 009-2003-SA y su modificatoria. Para SO2 la norma usa promedio
# móvil de 3 h; aquí se aplica al promedio diario solo como referencia.
VUEC = {"PM10": 250, "DIOXIDO_AZUFRE": 500}
CATEGORIAS_INCA = ["Buena", "Moderada", "Mala", "Umbral de cuidado"]
COLORES_INCA = {"Buena": "#2E9E44", "Moderada": "#F2C12E",
                "Mala": "#F28C28", "Umbral de cuidado": "#D7263D"}
# Rótulos para las figuras de la tesis
NOMBRE_VAR = {"DIOXIDO_AZUFRE": "SO$_2$", "PM10": "PM$_{10}$", "PM2.5": "PM$_{2.5}$"}
UNIDAD = "µg/m³"
NOMBRE_DEP = {"JUNIN": "Junín", "PASCO": "Pasco", "MOQUEGUA": "Moquegua"}

FACTOR_SO2_PPB_A_UG = 2.62  # 25 °C y 1 atm; solo si no existe el dato en ug/m3

REGLAS_DOMINIO = {
    "PM2.5": (0, 500), "PM10": (0, 600), "DIOXIDO_AZUFRE": (0, 2000),
    "MONOXIDO_CARBONO": (0, 50000), "OZONO": (0, 500), "SULFURO_HIDROGENO": (0, 500),
    "HUMEDAD_RELATIVA": (1, 100), "TEMPERATURA": (-20, 45),
    "VELOCIDAD_VIENTO": (0, 60), "DIRECCION_VIENTO": (0, 360),
    "PRESION_BAROMETRICA": (400, 800), "PRECIPITACION": (0, 100),
}
VARIABLES_CERO_SOSPECHOSO = ["PM2.5", "PM10", "DIOXIDO_AZUFRE"]
MIN_RACHA_CEROS = 3
MIN_HORAS_DIA = 18  # 75% de 24 h

# Criterios de selección de series de modelado (Cap. 5)
MIN_DIAS_CON_DATO = 365
MIN_RACHA_CONTINUA = 180

# Régimen de operación de la fuente: estaciones donde se estima y umbral (ug/m3)
# sobre la mediana móvil (7 días) del máximo horario diario. Revisar el histograma
# de la sección 2.3.4 y ajustar si hace falta.
ESTACIONES_REGIMEN = {"CA-CC-01": "DIOXIDO_AZUFRE"}
UMBRAL_OPERACION = 40
VENTANA_OPERACION = 7

USAR_METEO_EXTERNA = False  # 2.1.b: activar solo si falta meteorología en alguna serie


def guardar_fig(nombre: str):
    """Guarda la figura actual en PNG (300 dpi) y la muestra."""
    plt.savefig(os.path.join(CARPETA_FIGURAS, f"{nombre}.png"), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close("all")


bitacora = []  # (paso, filas) -> tabla de limpieza para la tesis


def registrar(paso: str, df: pd.DataFrame):
    bitacora.append({"paso": paso, "filas": len(df)})


# %% [markdown]
# ## 2.1 Colectar los datos

# %%
def colectar_datos(ruta_csv: str, departamentos=None, chunksize=500_000) -> pd.DataFrame:
    """Lee el CSV por bloques y, dentro de cada bloque, lo pasa al formato largo
    (VARIABLE, VALOR). Así nunca se tiene en memoria la tabla ancha completa ni el
    resultado de un melt sobre todas las filas (cuidado de memoria con 1.2 GB).
    El índice de pandas es continuo entre bloques: sirve como orden de fila del archivo."""
    partes = []
    total = filas_piloto = 0
    lector = pd.read_csv(
        ruta_csv, sep=";", encoding="utf-8", usecols=COLUMNAS_USADAS,
        dtype=str, na_values=["-", "", "NA"], keep_default_na=False, chunksize=chunksize,
    )
    for bloque in lector:
        total += len(bloque)
        bloque["DEPARTAMENTO"] = bloque["DEPARTAMENTO"].str.strip().str.upper()
        if departamentos:
            bloque = bloque[bloque["DEPARTAMENTO"].isin(departamentos)]
        filas_piloto += len(bloque)
        bloque = bloque.assign(ORDEN_ARCHIVO=bloque.index)  # única pista de la hora cuando falta
        base = bloque.drop(columns=COLUMNAS_MEDICION).set_index("ORDEN_ARCHIVO")
        largo = (bloque[["ORDEN_ARCHIVO"] + COLUMNAS_MEDICION]
                 .melt(id_vars="ORDEN_ARCHIVO", var_name="VARIABLE", value_name="VALOR")
                 .dropna(subset=["VALOR"]))
        partes.append(base.join(largo.set_index("ORDEN_ARCHIVO"), how="inner").reset_index())
    df = pd.concat(partes, ignore_index=True).sort_values("ORDEN_ARCHIVO", ignore_index=True)
    bitacora.append({"paso": "Archivo original (nacional)", "filas": total})
    bitacora.append({"paso": "Filtro departamentos piloto", "filas": filas_piloto})
    print(f"Filas totales: {total:,} | en departamentos piloto: {filas_piloto:,} | "
          f"mediciones no vacías: {len(df):,}")
    return df


df_raw = colectar_datos(RUTA_DATOS, DEPARTAMENTOS_PILOTO)
print(df_raw["DEPARTAMENTO"].value_counts().to_string())

# %%
# Radiografía de la estructura: tipo de análisis x periodo x unidad
print(pd.crosstab([df_raw["TIPO_ANALISIS"].fillna("(vacío)"), df_raw["PERIODO"].fillna("(vacío)")],
                  df_raw["UNIDAD_MEDIDA"].fillna("(vacío)")).to_string())

# %%
# Catálogo de estaciones (para la tabla del caso de estudio)
catalogo_estaciones = (
    df_raw.groupby(["DEPARTAMENTO", "PROVINCIA", "DISTRITO", "NOMBRE_PUNTO"])
    .agg(ESTE=("ESTE", "first"), NORTE=("NORTE", "first"), ZONA=("ZONA", "first"),
         ALTITUD=("ALTITUD", "first"), evaluaciones=("NOMBRE_EVALUACION", "nunique"))
    .reset_index()
)
print(catalogo_estaciones.to_string(index=False))

# %% [markdown]
# ## 2.2 Calidad y limpieza
# ### 2.2.1 Formato "una fila = una medición" (VARIABLE, VALOR)
#
# El paso a formato largo ya se hizo por bloques al leer; aquí se convierte el valor a
# número y se descartan las mediciones cuya unidad no corresponde a la variable.

# %%
UNIDAD_ESPERADA = {
    "PRESION_BAROMETRICA": {"mmhg"}, "HUMEDAD_RELATIVA": {"%"},
    "VELOCIDAD_VIENTO": {"m/s"}, "PRECIPITACION": {"mm"},
    "TEMPERATURA": {"°c"}, "DIRECCION_VIENTO": {"°c", "°", "grados"},  # OEFA la rotula "°c"
    "PM10": {"ug/m3"}, "PM2.5": {"ug/m3"}, "DIOXIDO_AZUFRE": {"ug/m3", "ppb"},
}


def a_formato_medicion(largo: pd.DataFrame) -> pd.DataFrame:
    largo = largo.copy()
    largo["VALOR"] = pd.to_numeric(largo["VALOR"].str.replace(",", "."), errors="coerce")
    no_numerico = int(largo["VALOR"].isna().sum())
    largo = largo.dropna(subset=["VALOR"])

    largo["UNIDAD_MEDIDA"] = largo["UNIDAD_MEDIDA"].str.strip().str.lower()
    pares_validos = pd.DataFrame([(v, u) for v, us in UNIDAD_ESPERADA.items() for u in us],
                                 columns=["VARIABLE", "UNIDAD_MEDIDA"]).assign(_ok=True)
    marca = largo[["VARIABLE", "UNIDAD_MEDIDA"]].merge(pares_validos, how="left")["_ok"]
    sin_regla = ~largo["VARIABLE"].isin(list(UNIDAD_ESPERADA)).to_numpy()
    coincide = marca.notna().to_numpy() | sin_regla
    print(f"Valores no numéricos (descartados): {no_numerico:,}")
    print(f"Valores con unidad que no corresponde a la variable (descartados): {(~coincide).sum():,}")
    return largo[coincide].copy()


df_med = a_formato_medicion(df_raw)
del df_raw
registrar("Formato una fila = una medición", df_med)
print(df_med.groupby(["VARIABLE", "PERIODO"], dropna=False).size().to_string())

# %% [markdown]
# ### 2.2.2 Periodos y unidades de SO2
#
# - "1 hora" y meteorología (sin periodo) -> serie base.
# - "24 horas" -> valor oficial de OEFA, se guarda aparte para validar.
# - "3 horas móviles" -> derivado de la serie horaria, se descarta.
# - SO2 viene duplicado en ppb y ug/m3 (misma medición): se conserva ug/m3.

# %%
df_oficial_24h = df_med[df_med["PERIODO"] == "24 horas"].copy()
df_med = df_med[df_med["PERIODO"].isna() | (df_med["PERIODO"] == "1 hora")].copy()
registrar("Solo periodo 1 hora / meteorología", df_med)


def unificar_so2(df: pd.DataFrame) -> pd.DataFrame:
    es_so2 = df["VARIABLE"] == "DIOXIDO_AZUFRE"
    llave = ["NOMBRE_EVALUACION", "NOMBRE_PUNTO", "FECHA_INICIO"]
    dias_con_ug = (df.loc[es_so2 & (df["UNIDAD_MEDIDA"] == "ug/m3"), llave]
                   .drop_duplicates().assign(_hay_ug=True))
    es_ppb = es_so2 & (df["UNIDAD_MEDIDA"] == "ppb")
    hay_ug = df[llave].merge(dias_con_ug, on=llave, how="left")["_hay_ug"].notna().to_numpy()
    redundante = es_ppb & hay_ug
    df = df[~redundante].copy()
    convertir = (df["VARIABLE"] == "DIOXIDO_AZUFRE") & (df["UNIDAD_MEDIDA"] == "ppb")
    df.loc[convertir, "VALOR"] *= FACTOR_SO2_PPB_A_UG
    df.loc[convertir, "UNIDAD_MEDIDA"] = "ug/m3"
    print(f"SO2 ppb duplicado eliminado: {redundante.sum():,} | convertido a ug/m3: {convertir.sum():,}")
    return df


df_med = unificar_so2(df_med)
df_oficial_24h = unificar_so2(df_oficial_24h)
registrar("SO2 unificado en ug/m3", df_med)

# %% [markdown]
# ### 2.2.3 Fecha y hora
#
# - "1899-12-31 18:00:00" -> 18:00. "1899-12-31" sin hora -> 00:00 (Excel omite la medianoche).
# - Vacío -> la hora se reconstruye con el orden de las filas dentro de cada
#   estación-día-variable, solo si el grupo tiene exactamente 24 filas.

# %%
def construir_fecha_hora(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["FECHA"] = pd.to_datetime(df["FECHA_INICIO"], errors="coerce").dt.normalize()
    hora_txt = df["HORA_INICIO"].astype("string")
    hora = hora_txt.str.extract(r"(\d{1,2}):\d{2}(?::\d{2})?\s*$")[0].astype(float)
    solo_fecha = hora_txt.str.fullmatch(r"\s*\d{4}-\d{2}-\d{2}\s*").fillna(False)
    hora[solo_fecha] = 0

    df["HORA_ORIGEN"] = np.where(hora.notna(), "archivo", "desconocida")
    grupo = ["NOMBRE_EVALUACION", "NOMBRE_PUNTO", "FECHA", "VARIABLE"]
    df = df.sort_values(grupo + ["ORDEN_ARCHIVO"])
    hora = hora.reindex(df.index)
    posicion = df.groupby(grupo).cumcount()
    tamano = df.groupby(grupo)["VALOR"].transform("size")
    reconstruible = hora.isna() & (tamano == 24)
    hora[reconstruible] = posicion[reconstruible]
    df.loc[reconstruible, "HORA_ORIGEN"] = "reconstruida"

    df["FECHA_HORA"] = df["FECHA"] + pd.to_timedelta(hora, unit="h")
    print(pd.crosstab(df["DEPARTAMENTO"], df["HORA_ORIGEN"]).to_string())
    return df


df_med = construir_fecha_hora(df_med)


# %%
# Validación: el promedio de las 24 horas debe coincidir con el valor oficial "24 horas"
def validar_contra_oficial(df_h: pd.DataFrame, df_24: pd.DataFrame) -> pd.DataFrame:
    df_24 = df_24.assign(FECHA=pd.to_datetime(df_24["FECHA_INICIO"]).dt.normalize())
    llave = ["NOMBRE_PUNTO", "VARIABLE", "FECHA"]
    calc = df_h[df_h["VARIABLE"].isin(CONTAMINANTES)].groupby(llave)["VALOR"].agg(["mean", "size"])
    ofi = df_24.groupby(llave)["VALOR"].mean().rename("oficial")
    comp = calc.join(ofi, how="inner")
    comp = comp[comp["size"] == 24]
    comp["error_rel_%"] = (comp["mean"] - comp["oficial"]).abs() / comp["oficial"].replace(0, np.nan) * 100
    resumen = comp.groupby(level=["NOMBRE_PUNTO", "VARIABLE"])["error_rel_%"].agg(
        dias="size", error_mediano="median", p95=lambda s: s.quantile(0.95))
    print(f"Días comparados: {len(comp):,} | error relativo mediano global: "
          f"{comp['error_rel_%'].median():.2f}%")
    return resumen.round(2)


validacion = validar_contra_oficial(df_med, df_oficial_24h)
print(validacion.to_string())

# %% [markdown]
# ### 2.2.4 Duplicados (con la hora ya asignada)

# %%
con_hora = df_med["FECHA_HORA"].notna()
n_sin_hora = int((~con_hora).sum())
print("Filas sin hora asignable por estación/variable (grupos != 24 filas):")
print(df_med[~con_hora].groupby(["NOMBRE_PUNTO", "VARIABLE"]).size().to_string())
df_med = df_med[con_hora].drop_duplicates(
    subset=["NOMBRE_EVALUACION", "NOMBRE_PUNTO", "VARIABLE", "FECHA_HORA"])
registrar("Con fecha-hora válida y sin duplicados", df_med)

# Una misma estación puede aparecer en dos evaluaciones que se solapan en el tiempo.
# Si no se controla, esa hora se cuenta dos veces en el criterio de 18 h y en el promedio.
LLAVE_HORA = ["NOMBRE_PUNTO", "VARIABLE", "FECHA_HORA"]
iguales = df_med.duplicated(LLAVE_HORA + ["VALOR"])
df_med = df_med[~iguales]
conflicto = df_med.duplicated(LLAVE_HORA, keep=False)
print(f"\nHoras repetidas entre evaluaciones con el mismo valor (eliminadas): {int(iguales.sum()):,}")
print(f"Horas repetidas entre evaluaciones con valor distinto: {int(conflicto.sum()):,} filas")
if conflicto.any():
    print(df_med[conflicto].groupby(["NOMBRE_PUNTO", "VARIABLE"]).size().to_string())
registrar("Sin horas repetidas entre evaluaciones", df_med)

# %% [markdown]
# ### 2.2.5 Reglas de dominio y rachas de ceros (se marcan, luego se excluyen)

# %%
def marcar_calidad(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rango = df["VARIABLE"].map(REGLAS_DOMINIO)
    lo = rango.map(lambda r: r[0] if isinstance(r, tuple) else -np.inf)
    hi = rango.map(lambda r: r[1] if isinstance(r, tuple) else np.inf)
    df["FLAG_DOMINIO"] = ~df["VALOR"].between(lo, hi)

    df = df.sort_values(["NOMBRE_PUNTO", "VARIABLE", "FECHA_HORA"])
    es_cero = (df["VALOR"] == 0) & df["VARIABLE"].isin(VARIABLES_CERO_SOSPECHOSO)
    bloque = (es_cero != es_cero.shift()).cumsum()
    largo_racha = es_cero.groupby([df["NOMBRE_PUNTO"], df["VARIABLE"], bloque]).transform("sum")
    df["FLAG_CERO_RACHA"] = es_cero & (largo_racha >= MIN_RACHA_CEROS)
    print(df.groupby("VARIABLE")[["FLAG_DOMINIO", "FLAG_CERO_RACHA"]].sum().to_string())
    return df


df_med = marcar_calidad(df_med)
df_med.to_pickle(os.path.join(CARPETA_CHECKPOINTS, "01_mediciones_marcadas.pkl"))
df_ok = df_med[~df_med["FLAG_DOMINIO"] & ~df_med["FLAG_CERO_RACHA"]].copy()
registrar("Sin atípicos de dominio ni rachas de ceros", df_ok)

# %% [markdown]
# ### 2.2.6 Bitácora de limpieza (tabla para la tesis)

# %%
tabla_bitacora = pd.DataFrame(bitacora)
tabla_bitacora["variación"] = tabla_bitacora["filas"].diff()
tabla_bitacora.to_csv(os.path.join(CARPETA_CHECKPOINTS, "00_bitacora_limpieza.csv"), sep=";", index=False)
print(tabla_bitacora.to_string(index=False))

# %% [markdown]
# ## 2.3 EDA
# ### 2.3.1 Estadística descriptiva (valores horarios válidos)

# %%
descriptiva = (
    df_ok.groupby(["DEPARTAMENTO", "NOMBRE_PUNTO", "VARIABLE"])["VALOR"]
    .describe(percentiles=[0.25, 0.5, 0.75, 0.95]).round(2)
)
print(descriptiva.to_string())

# %% [markdown]
# ### 2.3.2 Cobertura por estación y selección de series de modelado

# %%
def racha_mas_larga(fechas: pd.Series) -> int:
    dias = pd.Series(sorted(fechas.unique()))
    if dias.empty:
        return 0
    corte = dias.diff().dt.days.ne(1).cumsum()
    return int(corte.value_counts().max())


cobertura = (
    df_ok[df_ok["VARIABLE"].isin(CONTAMINANTES)]
    .groupby(["DEPARTAMENTO", "NOMBRE_PUNTO", "VARIABLE"])
    .agg(inicio=("FECHA", "min"), fin=("FECHA", "max"), dias_con_dato=("FECHA", "nunique"),
         racha_max_dias=("FECHA", racha_mas_larga))
    .reset_index()
)
cobertura["seleccionada"] = (cobertura["dias_con_dato"] >= MIN_DIAS_CON_DATO) & \
                            (cobertura["racha_max_dias"] >= MIN_RACHA_CONTINUA)
cobertura["motivo"] = np.where(
    cobertura["seleccionada"], "Cumple criterios",
    np.where(cobertura["dias_con_dato"] < MIN_DIAS_CON_DATO,
             f"< {MIN_DIAS_CON_DATO} días con dato", f"Racha continua < {MIN_RACHA_CONTINUA} días"))
cobertura = cobertura.sort_values(["seleccionada", "dias_con_dato"], ascending=False)
cobertura.to_csv(os.path.join(CARPETA_CHECKPOINTS, "02_cobertura_estaciones.csv"), sep=";", index=False)

SERIES = list(cobertura.loc[cobertura["seleccionada"], ["DEPARTAMENTO", "NOMBRE_PUNTO", "VARIABLE"]]
              .itertuples(index=False, name=None))
print("Series seleccionadas para modelado:")
for s in SERIES:
    print("  ", s)
print(cobertura.to_string(index=False))

# %%
# Mapa de disponibilidad: % de días del mes con dato válido, por serie estación-variable
disp = (
    df_ok[df_ok["VARIABLE"].isin(CONTAMINANTES + METEOROLOGICAS)]
    .assign(MES=lambda d: d["FECHA"].dt.to_period("M"))
    .groupby(["NOMBRE_PUNTO", "VARIABLE", "MES"])["FECHA"].nunique()
    .unstack("MES")
)
disp = disp.div(disp.columns.to_timestamp().days_in_month, axis=1).mul(100).fillna(0)
plt.figure(figsize=(14, max(4, 0.3 * len(disp))))
sns.heatmap(disp, cmap="Blues", vmin=0, vmax=100, cbar_kws={"label": "% días con dato"})
plt.title("Disponibilidad mensual de datos por estación y variable")
plt.xlabel("Mes")
plt.ylabel("")
guardar_fig("fig01_disponibilidad_mensual")

# %% [markdown]
# ### 2.3.3 Serie diaria (criterio 75%) + INCA + ECA + OMS
#
# Agregación diaria según el tipo de variable:
# - Contaminantes y meteorología: promedio con >= 18 h válidas.
# - Precipitación: SUMA diaria (mm/día).
# - Dirección del viento: promedio vectorial (seno y coseno), no promedio simple.

# %%
horario = df_ok.copy()
horario["HORA"] = horario["FECHA_HORA"].dt.hour

agg = (horario.groupby(["DEPARTAMENTO", "NOMBRE_PUNTO", "VARIABLE", "FECHA"])["VALOR"]
       .agg(media="mean", suma="sum", maximo="max", horas="size").reset_index())
agg = agg[agg["horas"] >= MIN_HORAS_DIA].copy()
agg["valor_dia"] = np.where(agg["VARIABLE"] == "PRECIPITACION", agg["suma"], agg["media"])

# Dirección del viento: promedio vectorial
dv = horario[horario["VARIABLE"] == "DIRECCION_VIENTO"].copy()
rad = np.deg2rad(dv["VALOR"])
dv = dv.assign(SIN=np.sin(rad), COS=np.cos(rad))
viento_dir = (dv.groupby(["DEPARTAMENTO", "NOMBRE_PUNTO", "FECHA"])
              .agg(VIENTO_SIN=("SIN", "mean"), VIENTO_COS=("COS", "mean"), horas=("SIN", "size"))
              .reset_index())
viento_dir = viento_dir[viento_dir["horas"] >= MIN_HORAS_DIA].drop(columns="horas")


def categoria_inca(valor: pd.Series, variable: str) -> pd.Series:
    """INCA = concentración / ECA x 100. Verde 0-50, amarillo 51-100,
    naranja 101-VUEC, rojo > VUEC (R.M. 181-2016-MINAM)."""
    inca = valor * 100 / ECA_24H[variable]
    if variable in VUEC:
        tope = VUEC[variable] * 100 / ECA_24H[variable]
        cat = pd.cut(inca, [-np.inf, 50, 100, tope, np.inf], labels=CATEGORIAS_INCA)
    else:  # sin VUEC definido: solo buena / moderada / mala
        cat = pd.cut(inca, [-np.inf, 50, 100, np.inf], labels=CATEGORIAS_INCA[:3])
    return cat.astype(str)


diario_cont = agg[agg["VARIABLE"].isin(CONTAMINANTES)].copy()
diario_cont["INCA"] = diario_cont["media"] * 100 / diario_cont["VARIABLE"].map(ECA_24H)
diario_cont["CATEGORIA_INCA"] = ""
for var in CONTAMINANTES:
    m = diario_cont["VARIABLE"] == var
    if m.any():
        diario_cont.loc[m, "CATEGORIA_INCA"] = categoria_inca(diario_cont.loc[m, "media"], var).values
diario_cont["SUPERA_ECA"] = diario_cont["media"] > diario_cont["VARIABLE"].map(ECA_24H)
diario_cont["SUPERA_OMS"] = diario_cont["media"] > diario_cont["VARIABLE"].map(OMS_24H)

# %%
# Tabla resumen por serie seleccionada: INCA + ECA + OMS (para la tesis)
filas = []
for dep, est, var in SERIES:
    s = diario_cont[(diario_cont["NOMBRE_PUNTO"] == est) & (diario_cont["VARIABLE"] == var)]
    fila = {"Departamento": dep, "Estación": est, "Contaminante": var, "Días válidos": len(s)}
    dist = s["CATEGORIA_INCA"].value_counts(normalize=True).mul(100)
    for c in CATEGORIAS_INCA:
        fila[f"% {c}"] = round(dist.get(c, 0), 1)
    fila["% días > ECA"] = round(s["SUPERA_ECA"].mean() * 100, 2)
    fila["% días > guía OMS"] = round(s["SUPERA_OMS"].mean() * 100, 1)
    filas.append(fila)
tabla_semaforo = pd.DataFrame(filas)
tabla_semaforo.to_csv(os.path.join(CARPETA_CHECKPOINTS, "02_tabla_semaforo_inca.csv"), sep=";", index=False)
print(tabla_semaforo.to_string(index=False))

# %% [markdown]
# ### 2.3.4 Régimen de operación de la fuente (CA-CC-01)
#
# El SO2 de La Oroya alterna entre días con picos altos (fuente operando) y días con
# un nivel de fondo bajo y estable (fuente detenida). Se estima una variable binaria
# OPERACION con la mediana móvil del máximo horario diario. En producción esta variable
# vendría de información operativa conocida de antemano (covariable exógena, R02).

# %%
regimen = {}
regimen_causal = {}
for est, var in ESTACIONES_REGIMEN.items():
    s = agg[(agg["NOMBRE_PUNTO"] == est) & (agg["VARIABLE"] == var)].set_index("FECHA")["maximo"]
    if s.empty:
        continue
    s = s.asfreq("D")
    mediana = s.rolling(VENTANA_OPERACION, center=True, min_periods=3).median()
    operacion = (mediana > UMBRAL_OPERACION).astype(float).where(mediana.notna())
    regimen[est] = operacion
    # Versión causal (solo el día actual y los 6 anteriores): es el "último estado conocido"
    # que se puede usar al pronosticar sin mirar el futuro.
    mediana_causal = s.rolling(VENTANA_OPERACION, min_periods=3).median()
    regimen_causal[est] = (mediana_causal > UMBRAL_OPERACION).astype(float).where(mediana_causal.notna())

    fig, axes = plt.subplots(1, 2, figsize=(15, 4), gridspec_kw={"width_ratios": [1, 2.5]})
    axes[0].hist(np.log10(s.dropna().clip(lower=0.1)), bins=60, color="#4472C4")
    axes[0].axvline(np.log10(UMBRAL_OPERACION), color="red", linestyle="--",
                    label=f"umbral {UMBRAL_OPERACION} {UNIDAD}")
    axes[0].set_title(f"{est}: máximo horario diario de {NOMBRE_VAR[var]}")
    axes[0].set_xlabel(f"log$_{{10}}$ (máximo horario, {UNIDAD})")
    axes[0].set_ylabel("N.º de días")
    axes[0].legend()
    axes[1].plot(s.index, s.values, lw=0.6, color="#4472C4", label="máximo horario diario")
    axes[1].fill_between(operacion.index, 0, s.max(), where=operacion.eq(1),
                         color="orange", alpha=0.15, label="OPERACION = 1")
    axes[1].set_title(f"{est}: régimen de operación estimado")
    axes[1].set_ylabel(UNIDAD)
    axes[1].legend(loc="upper left")
    plt.tight_layout()
    guardar_fig(f"fig02_regimen_operacion_{est}")
    print(f"{est}: {operacion.eq(1).mean() * 100:.1f}% de días con OPERACION = 1 | "
          f"coincidencia centrada vs causal: "
          f"{(operacion == regimen_causal[est]).where(operacion.notna() & regimen_causal[est].notna()).mean() * 100:.1f}%")

# %% [markdown]
# ### 2.3.5 Figuras para la tesis

# %%
# (a) Serie diaria por serie seleccionada, con ECA y guía OMS (los huecos quedan visibles)
for dep, est, var in SERIES:
    s = diario_cont[(diario_cont["NOMBRE_PUNTO"] == est) & (diario_cont["VARIABLE"] == var)]
    s = s.set_index("FECHA")["media"].asfreq("D")
    plt.figure(figsize=(13, 4))
    plt.plot(s.index, s.values, lw=0.8, color="#4472C4", label="promedio diario")
    plt.axhline(ECA_24H[var], color="#D7263D", ls="--", label=f"ECA 24 h ({ECA_24H[var]} {UNIDAD})")
    plt.axhline(OMS_24H[var], color="#2E9E44", ls=":", label=f"Guía OMS 24 h ({OMS_24H[var]} {UNIDAD})")
    plt.axhline(ECA_24H[var] * 0.5, color="#F2C12E", ls="-.", lw=0.8, label="INCA 50 (Buena/Moderada)")
    plt.title(f"{NOMBRE_VAR[var]} - {est} ({NOMBRE_DEP.get(dep, dep.title())}): promedio diario")
    plt.ylabel(f"Concentración ({UNIDAD})")
    plt.xlabel("Fecha")
    plt.legend(fontsize=8, ncol=4, loc="upper right")
    plt.tight_layout()
    guardar_fig(f"fig03_serie_diaria_{est}_{var}")

# %%
# (b) Distribución de las concentraciones diarias
if SERIES:
    fig, axes = plt.subplots(1, len(SERIES), figsize=(5 * len(SERIES), 4), squeeze=False)
    for ax, (dep, est, var) in zip(axes[0], SERIES):
        s = diario_cont[(diario_cont["NOMBRE_PUNTO"] == est) & (diario_cont["VARIABLE"] == var)]["media"]
        sns.histplot(s, bins=50, kde=True, ax=ax, color="#4472C4")
        ax.axvline(ECA_24H[var], color="#D7263D", ls="--", label=f"ECA 24 h ({ECA_24H[var]})")
        ax.axvline(OMS_24H[var], color="#2E9E44", ls=":", label=f"Guía OMS ({OMS_24H[var]})")
        ax.set_title(f"{NOMBRE_VAR[var]} - {est}")
        ax.set_xlabel(f"Promedio diario ({UNIDAD})")
        ax.set_ylabel("N.º de días")
        ax.legend(fontsize=8)
    plt.tight_layout()
    guardar_fig("fig04_histogramas")

# %%
# (c) Estacionalidad mensual
if SERIES:
    fig, axes = plt.subplots(1, len(SERIES), figsize=(5.5 * len(SERIES), 4), squeeze=False)
    for ax, (dep, est, var) in zip(axes[0], SERIES):
        s = diario_cont[(diario_cont["NOMBRE_PUNTO"] == est) & (diario_cont["VARIABLE"] == var)]
        sns.boxplot(data=s.assign(MES=s["FECHA"].dt.month), x="MES", y="media", ax=ax, color="#4472C4",
                    fliersize=2)
        ax.axhline(ECA_24H[var], color="#D7263D", ls="--", lw=1, label="ECA 24 h")
        ax.set_title(f"{NOMBRE_VAR[var]} - {est}: variación mensual")
        ax.set_xlabel("Mes")
        ax.set_ylabel(f"Promedio diario ({UNIDAD})")
        ax.legend(fontsize=8)
    plt.tight_layout()
    guardar_fig("fig05_estacionalidad_mensual")

# %%
# (d) Ciclo diario (perfil horario). En estaciones con régimen se separa operación / detenida.
if SERIES:
    fig, axes = plt.subplots(1, len(SERIES), figsize=(5.5 * len(SERIES), 4), squeeze=False)
    for ax, (dep, est, var) in zip(axes[0], SERIES):
        h = horario[(horario["NOMBRE_PUNTO"] == est) & (horario["VARIABLE"] == var)].copy()
        if est in regimen:
            h["REGIMEN"] = h["FECHA"].map(regimen[est]).map({1.0: "Operando", 0.0: "Detenida"})
            sns.lineplot(data=h.dropna(subset=["REGIMEN"]), x="HORA", y="VALOR", hue="REGIMEN",
                         estimator="median", errorbar=("pi", 50), ax=ax)
        else:
            sns.lineplot(data=h, x="HORA", y="VALOR", estimator="median", errorbar=("pi", 50),
                         ax=ax, color="#4472C4")
        ax.set_title(f"{NOMBRE_VAR[var]} - {est}: ciclo diario (mediana y RIC)")
        ax.set_xlabel("Hora del día")
        ax.set_ylabel(f"Concentración horaria ({UNIDAD})")
    plt.tight_layout()
    guardar_fig("fig06_ciclo_diario")

# %%
# (e) Distribución de categorías INCA por serie
if len(tabla_semaforo):
    t = tabla_semaforo.set_index(tabla_semaforo["Estación"] + " - " + tabla_semaforo["Contaminante"].map(NOMBRE_VAR))
    t = t[[f"% {c}" for c in CATEGORIAS_INCA]]
    ax = t.plot(kind="barh", stacked=True, figsize=(10, 0.8 * len(t) + 1.5),
                color=[COLORES_INCA[c] for c in CATEGORIAS_INCA])
    ax.set_xlabel("% de días")
    ax.set_ylabel("")
    ax.set_title("Distribución de días por categoría INCA")
    ax.legend(CATEGORIAS_INCA, bbox_to_anchor=(1.01, 1), loc="upper left")
    plt.tight_layout()
    guardar_fig("fig07_distribucion_inca")

# %% [markdown]
# ### 2.3.6 Correlaciones por estación (Spearman, promedios diarios)
#
# En estaciones con régimen de operación se calcula solo con días OPERACION = 1, para que
# los días de fuente detenida no diluyan la relación con la meteorología.

# %%
diario_met = agg[agg["VARIABLE"].isin(METEOROLOGICAS) & (agg["VARIABLE"] != "DIRECCION_VIENTO")]
for dep, est, var in SERIES:
    obj = diario_cont[(diario_cont["NOMBRE_PUNTO"] == est) & (diario_cont["VARIABLE"] == var)] \
        .set_index("FECHA")["media"].rename(var)
    met = diario_met[diario_met["NOMBRE_PUNTO"] == est].pivot(index="FECHA", columns="VARIABLE",
                                                              values="valor_dia")
    tabla = pd.concat([obj, met], axis=1)
    if est in regimen:
        tabla = tabla[tabla.index.map(regimen[est]).to_series(index=tabla.index).eq(1)]
    if tabla.shape[1] < 2 or tabla[var].notna().sum() < 30:
        print(f"{est}: datos insuficientes para correlación")
        continue
    plt.figure(figsize=(7, 5.5))
    sns.heatmap(tabla.corr(method="spearman"), annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1)
    extra = " (solo días con fuente operando)" if est in regimen else ""
    plt.title(f"Correlación de Spearman - {est}{extra}")
    plt.tight_layout()
    guardar_fig(f"fig08_correlacion_{est}")

# %% [markdown]
# ### 2.3.7 Estacionariedad (ADF), descomposición STL y ACF/PACF
#
# Requiere statsmodels. La interpolación se usa solo para estas pruebas, no para modelar.

# %%
try:
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.tsa.seasonal import STL
    from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
    HAY_STATSMODELS = True
except ImportError:
    HAY_STATSMODELS = False
    print("statsmodels no instalado: pip install statsmodels")

if HAY_STATSMODELS:
    resultados_adf = []
    for dep, est, var in SERIES:
        s = diario_cont[(diario_cont["NOMBRE_PUNTO"] == est) & (diario_cont["VARIABLE"] == var)]
        s = s.set_index("FECHA")["media"].asfreq("D").interpolate(limit=7).dropna()
        if len(s) < 60:
            continue
        estad, p, *_ = adfuller(s, autolag="AIC")
        resultados_adf.append({"Estación": est, "Contaminante": var, "n": len(s),
                               "ADF": round(estad, 3), "p-valor": round(p, 4),
                               "¿Estacionaria (p<0.05)?": "Sí" if p < 0.05 else "No"})

        periodo = 365 if len(s) >= 2 * 365 else 7
        stl = STL(s, period=periodo, robust=True).fit()
        fig = stl.plot()
        fig.set_size_inches(12, 7)
        fig.suptitle(f"Descomposición STL (periodo = {periodo} días) - {NOMBRE_VAR[var]} {est} ({UNIDAD})",
                     y=1.02)
        guardar_fig(f"fig09_stl_{est}_{var}")

        lags = min(60, len(s) // 2 - 1)
        fig, axes = plt.subplots(1, 2, figsize=(13, 3.5))
        plot_acf(s, lags=lags, ax=axes[0], title=f"ACF - {NOMBRE_VAR[var]} {est}")
        plot_pacf(s, lags=lags, ax=axes[1], title=f"PACF - {NOMBRE_VAR[var]} {est}", method="ywm")
        for ax in axes:
            ax.set_xlabel("Rezago (días)")
        plt.tight_layout()
        guardar_fig(f"fig10_acf_pacf_{est}_{var}")
    tabla_adf = pd.DataFrame(resultados_adf)
    tabla_adf.to_csv(os.path.join(CARPETA_CHECKPOINTS, "02_tabla_adf.csv"), sep=";", index=False)
    print(tabla_adf.to_string(index=False))

# %% [markdown]
# ## 2.1.b (Opcional) Meteorología externa Open-Meteo / ERA5-Land
#
# Solo si alguna serie seleccionada no tiene meteorología propia en sus fechas.
# Se descarga POR ESTACIÓN (coordenadas UTM de OEFA -> lat/lon), no por departamento.

# %%
if USAR_METEO_EXTERNA:
    import requests
    from pyproj import Transformer

    def utm_a_latlon(este, norte, zona):
        t = Transformer.from_crs(f"+proj=utm +zone={int(zona)} +south +datum=WGS84",
                                 "EPSG:4326", always_xy=True)
        lon, lat = t.transform(float(este), float(norte))
        return lat, lon

    meteo_frames = []
    for dep, est, var in SERIES:
        fila = catalogo_estaciones[catalogo_estaciones["NOMBRE_PUNTO"] == est].iloc[0]
        lat, lon = utm_a_latlon(fila["ESTE"], fila["NORTE"], fila["ZONA"])
        rango = diario_cont[diario_cont["NOMBRE_PUNTO"] == est]["FECHA"]
        resp = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=180, params={
            "latitude": lat, "longitude": lon, "models": "era5_land",
            "start_date": rango.min().strftime("%Y-%m-%d"), "end_date": rango.max().strftime("%Y-%m-%d"),
            "daily": "temperature_2m_mean,relative_humidity_2m_mean,wind_speed_10m_mean,"
                     "precipitation_sum,surface_pressure_mean",
            "timezone": "America/Lima"})
        resp.raise_for_status()
        m = pd.DataFrame(resp.json()["daily"]).rename(columns={"time": "FECHA"})
        m["FECHA"] = pd.to_datetime(m["FECHA"])
        m["NOMBRE_PUNTO"] = est
        meteo_frames.append(m)
        print(f"{est}: lat={lat:.4f}, lon={lon:.4f}, {len(m)} días descargados")
    df_meteo_externa = pd.concat(meteo_frames, ignore_index=True)
    df_meteo_externa.to_pickle(os.path.join(CARPETA_CHECKPOINTS, "00_meteo_era5land.pkl"))

# %% [markdown]
# ## 2.4 Transformación: dataset diario por serie (input de modelado)
#
# Una tabla por serie seleccionada con frecuencia diaria continua (los huecos quedan como
# NaN): objetivo, meteorología de la misma estación, dirección del viento vectorial,
# régimen de operación (si aplica), calendario, INCA y banderas ECA/OMS.
# La imputación y el escalado se hacen en el notebook de modelado, DESPUÉS de separar
# train/test, para no filtrar información del futuro.

# %%
datasets = {}
for dep, est, var in SERIES:
    obj = diario_cont[(diario_cont["NOMBRE_PUNTO"] == est) & (diario_cont["VARIABLE"] == var)] \
        .set_index("FECHA")[["media", "INCA", "CATEGORIA_INCA", "SUPERA_ECA", "SUPERA_OMS"]] \
        .rename(columns={"media": "OBJETIVO"})
    met = diario_met[diario_met["NOMBRE_PUNTO"] == est].pivot(index="FECHA", columns="VARIABLE",
                                                              values="valor_dia")
    vd = viento_dir[viento_dir["NOMBRE_PUNTO"] == est].set_index("FECHA")[["VIENTO_SIN", "VIENTO_COS"]]
    ds = obj.join([met, vd], how="left")
    if USAR_METEO_EXTERNA:
        ext = df_meteo_externa[df_meteo_externa["NOMBRE_PUNTO"] == est].set_index("FECHA") \
            .drop(columns="NOMBRE_PUNTO").add_suffix("_ERA5L")
        ds = ds.join(ext, how="left")
    ds = ds.asfreq("D")
    if est in regimen:
        ds["OPERACION"] = regimen[est].reindex(ds.index)
        ds["OPERACION_CAUSAL"] = regimen_causal[est].reindex(ds.index)
    ds["DIA_SEMANA"] = ds.index.dayofweek
    ds["MES"] = ds.index.month
    ds.insert(0, "CONTAMINANTE", var)
    ds.insert(0, "NOMBRE_PUNTO", est)
    ds.insert(0, "DEPARTAMENTO", dep)
    ds.index.name = "FECHA"
    datasets[(est, var)] = ds

    nombre = f"03_dataset_{est}_{var}"
    ds.to_pickle(os.path.join(CARPETA_CHECKPOINTS, f"{nombre}.pkl"))
    ds.to_csv(os.path.join(CARPETA_CHECKPOINTS, f"{nombre}.csv"), sep=";")
    completitud = ds.drop(columns=["DEPARTAMENTO", "NOMBRE_PUNTO", "CONTAMINANTE"]).notna().mean().mul(100)
    print(f"\n{nombre}: {len(ds):,} días")
    print(completitud.round(1).to_string())

# Tabla horaria ancha (por si se modela a nivel horario más adelante)
ancho_horario = horario.pivot_table(index=["DEPARTAMENTO", "NOMBRE_PUNTO", "FECHA_HORA"],
                                    columns="VARIABLE", values="VALOR", aggfunc="mean").reset_index()
ancho_horario.to_pickle(os.path.join(CARPETA_CHECKPOINTS, "03_dataset_horario_completo.pkl"))
print("\nCheckpoints en ./checkpoints y figuras en ./figuras")

# %% [markdown]
# ## Resumen de la fase
#
# - El archivo OEFA viene en formato largo, con la hora vacía en los departamentos piloto,
#   SO2 duplicado en ppb y ug/m3, y periodos mezclados (1 h, 3 h móviles y 24 h).
# - La hora se reconstruyó con el orden del archivo y se validó contra el promedio oficial
#   de 24 h de OEFA (tabla `validacion`).
# - Las series de modelado se eligieron con criterios explícitos de cobertura
#   (tabla `cobertura`, columna `motivo`).
# - Cada día se clasifica con el INCA y se compara con el ECA y la guía OMS
#   (tabla `tabla_semaforo`).
# - En CA-CC-01 se estimó el régimen de operación de la fuente como covariable exógena.
# - Salidas: 03_dataset_<estación>_<contaminante>.pkl/.csv (input del notebook 2),
#   tablas CSV y figuras PNG para la tesis.
