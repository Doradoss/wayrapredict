# %% [markdown]
# # Plataforma de Analítica Predictiva - Calidad del Aire
# ## Inventario y comparación de estaciones candidatas: Pasco y Moquegua
#
# Tarea SOLO de inventario y comparación (instrucciones_1.md): no entrena modelos, no modifica
# los scripts del pipeline (01, 01b, 02, 03, 04c, 05, wayra_comun.py) ni nada de La Oroya.
#
# - Pasco:    CA-COLQ-01 (Colquijirca, nueva)  vs  CA-SB-01 (Simón Bolívar, 1A.csv).
# - Moquegua: CA-TAL-01  (Tala, nueva)         vs  CA-TO-01 (Torata, 1A.csv).
# - Pasco (instrucciones_2.md): CA-HUAR-01 (Huaraucaca) pasa a ser la estación base; sus meses
#   faltantes se buscan también en la carpeta de CA-COLQ-01 (archivos u hojas de Huaraucaca).
#   La serie combinada HUAR + COLQ se arma en 00f-HUARAUCACA_COMBINADA.py.
#
# Secciones:
# 1. Inventario de archivos (formato, periodo, estación, variables, unidades, resolución, estado).
# 2. Conversión de PDF con datos continuos a CSV (pdfplumber) + verificación y log.
# 3. Unificación preliminar por estación (fecha-hora, variable, valor, unidad), limpieza con las
#    reglas ya usadas, hora local vs UTC, códigos de estado, horas (>= 75 %) y días (>= 18 h).
# 4. Cobertura mensual (tabla y mapa de calor) y huecos > 30 días.
# 5. Comparación por departamento y evaluación de PM2.5.
# Nada de esto define hiperparámetros ni calibraciones.
#
# Salidas: checkpoints/inventario_estaciones/ y figuras/inventario_estaciones/.
# Los CSV de los PDF van a Datos_crudos_<ESTACION>/convertidos_pdf/ (los originales no se tocan).

# %%
import gc
import io
import hashlib
import os
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import wayra_comun as wc
import wayra_alta_resolucion as war

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 300)
pd.set_option("display.max_colwidth", 60)

# ------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------
CARPETA_SALIDA = os.path.join(wc.CARPETA_DATOS, "inventario_estaciones")
CARPETA_CACHE = os.path.join(CARPETA_SALIDA, "cache")
CARPETA_FIG = os.path.join(wc.RAIZ, "figuras", "inventario_estaciones")
for _c in (CARPETA_SALIDA, CARPETA_CACHE, CARPETA_FIG):
    os.makedirs(_c, exist_ok=True)

ESTACIONES_NUEVAS = {
    "CA-COLQ-01": {"departamento": "PASCO", "id_estacion": "28",
                   # otra estación dentro de la carpeta (ID 29): se excluye
                   "otra_estacion": [r"Huaraucaca|CA-HUAR"],
                   # logger de nombre desconocido en jun 2024: se registra, no se unifica
                   "no_unificar": [r"CR300Series_maigrai"]},
    # Estación base de Pasco (decisión del usuario, instrucciones_2.md). Se publica junto con
    # CA-COLQ-01: los meses que faltan en su carpeta se buscan en la de Colquijirca.
    "CA-HUAR-01": {"departamento": "PASCO", "id_estacion": "29",
                   # copias de archivos de Colquijirca dentro de la carpeta (md5 idéntico)
                   "otra_estacion": [r"COLQUIJIRCA|Colquijirca|CA-COLQ"],
                   # estación meteorológica auxiliar (MAIGRAI / Campbell), igual que en CA-COLQ-01;
                   # libro de VALIDACION (niveles N1-N3: prevalidados, no se usan); copias "data
                   # manual"; tablas internas del logger (caseta, NO2, SO2, información de tablas)
                   "no_unificar": [r"maigra[iy]|MAIGRAI", r"huarau_Table", r"^RM\.txt$", r"VALIDACION",
                                   r"(?i)data manual", r"DataTableInfo|TermoHidro|_5M_In\.dat|_5M_NO2|_5M_SO2"],
                   # libros con varias hojas (ambas estaciones juntas)
                   "hojas": {"Enero_huaraucaca_datos crudos.xlsx": "CA-HUAR-01 GRIMM",
                             "Febrero_huaraucaca_datos crudos.xlsx": "CA-HUAR-01 PM"},
                   # abril de 2025: el Excel dice ID 28, pero es Huaraucaca (presión mediana 466,7 mmHg
                   # como en marzo, 466,6; Colquijirca 459,9; valores distintos al Excel de Colquijirca)
                   "id_corregido": {"Huaraucaca CA-HUAR-01_05_05_2025_07h_48m_24s.xlsx": "29"},
                   # meses faltantes: archivos u hojas de Huaraucaca en la carpeta de Colquijirca
                   "buscar_en": {"carpeta": "Datos_crudos_CA-COLQ-01", "archivo": r"Huaraucaca|CA-HUAR",
                                 "hoja": r"^CA-HUAR-01"},
                   # informe de evaluación (REAS), no es registro continuo: solo se inventaría
                   "pdf_informe": [r"REAS-"],
                   # Códigos 9 y 1 (solo ene-mar 2023): el libro de VALIDACION de marzo 2023 (hoja
                   # BD3_N1_5M, validación del especialista) los marca como VA (dato válido): 7 401/7 463
                   # registros con 9 y 639/639 con 1; -2147483648 sale EE/MA (inválido).
                   "codigos_validos_extra": {"9", "1"}},
    "CA-TAL-01": {"departamento": "MOQUEGUA", "id_estacion": "34", "otra_estacion": [],
                  "no_unificar": [r"^Tala_Oct\.txt$"],         # estación Davis de 5 días (solo met)
                  "hojas": {"12 Anexo 2 - Datos Crudos CA-TAL-01_01-31_Diciembre 2022.xlsx": "BD2_N1_5M"},
                  # desde el 11/07/2025 los archivos dicen CA-TAL-02 (posible reubicación)
                  "cambio_codigo": ("2025-07-11", "CA-TAL-02")},
    # Moquegua, alternativa (instrucciones_3.md): estaciones de Ilo. Carpeta común con subcarpetas por
    # año; la estación sale del nombre del archivo y el mes de la subcarpeta o del nombre (2020: un
    # archivo anual; 2021: archivos sueltos). Se verifica con ID_ESTACION (10, 11, 12) y la presión.
    **{e: {"departamento": "MOQUEGUA", "id_estacion": i, "carpeta": "Datos_crudos_ILO", "patron": e,
           "otra_estacion": [], "no_unificar": [],
           # descargas manuales de los equipos (respaldo, no validadas), muestreo manual de metales y
           # de bajo volumen, comprimidos e informe: solo se inventarían
           "no_leer": [r"(?i)manual", r"\.zip$", r"(?i)metales|lowvol", r"REAS-"],
           # Estado de PM10 en Ilo (Envidas: PM10_ENVIDAS / PM10_0_ESTADO / PM10_ESTADO): 1 = dato
           # normal; 0 viene con -9999; 3 en pocos registros. Las exportaciones de 2021 no traen columna
           # de estado ("(sin columna)": se aceptan; los inválidos vienen como "---").
           "codigos_validos": {"1", "(sin columna)"}}
       for e, i in (("CA-ILO-01", "10"), ("CA-ILO-02", "11"), ("CA-ILO-03", "12"))},
}
MESES_ABR = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9,
             "sep": 9, "oct": 10, "nov": 11, "dic": 12}


def listar(est: str, cfg: dict) -> pd.DataFrame:
    """Archivos de la estación. Con "patron" (Ilo), la carpeta es común a varias estaciones."""
    carpeta = cfg.get("carpeta", f"Datos_crudos_{est}")
    if "patron" not in cfg:
        return war.listar_archivos(carpeta).assign(carpeta=carpeta)
    filas = []
    for raiz, _, nombres in os.walk(carpeta):
        partes = os.path.relpath(raiz, carpeta).split(os.sep)
        if not partes[0].isdigit():
            continue
        for n in sorted(nombres):
            if cfg["patron"] not in n:
                continue
            m = re.match(r"(\d+)", partes[1]) if len(partes) > 1 else None
            mes = int(m.group(1)) if m else None
            if mes is None:
                m = re.search(r"\b(ene|feb|mar|abr|may|jun|jul|ago|set|sep|oct|nov|dic)[a-z]*\b", n.lower())
                mes = MESES_ABR[m.group(1)] if m else 0          # 0: sin mes (se toma de los datos)
            filas.append({"anio": int(partes[0]), "mes": mes, "archivo": n,
                          "extension": os.path.splitext(n)[1].lower(), "ruta": os.path.join(raiz, n),
                          "carpeta": carpeta})
    return pd.DataFrame(filas).sort_values(["anio", "mes", "archivo"]).reset_index(drop=True)


def codigos_de(est: str) -> set:
    cfg = ESTACIONES_NUEVAS[est]
    return set(cfg.get("codigos_validos", CODIGOS_VALIDOS)) | cfg.get("codigos_validos_extra", set())
REFERENCIA_1A = {"PASCO": "CA-SB-01", "MOQUEGUA": "CA-TO-01"}

# Posiciones de la fila de datos en los PDF de CA-TAL-02 (las columnas vacías de la tabla
# -BYPASS, FREQUENCY, NOISE, FILTER_LOAD- no dejan texto; verificado contra el Excel de julio 2025)
COLUMNAS_PDF = ["PBAR", "PP", "TEMP", "HR", "ws", "wd", "PM10_CONC", "PM10_FLOW", "PM10_ESTADO",
                "PM25_CONC", "PM25_FLOW", "PM25_ESTADO", "TEMP_INT_CASETA", "HUM_INT_CASETA"]
RE_FILA_PDF = re.compile(
    r"^(?P<fecha0>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: UTC)?|\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2})\s*"
    r"(?P<id>\d{2})\s*(?P<fecha>\d{1,2}/\d{1,2}/\d{4}) (?P<hora>\d{1,2}:\d{2}:\d{2})\s+(?P<valores>.*)$")

# Mapeo de variantes de columnas (propio de estas estaciones; no modifica wayra_alta_resolucion)
MAPEO = {
    "PM10": ["PM10_CONC", "PM10_0_UGM3", "PM10_UGM3", "Conc_PM10", "Val_GRIMM_PM10", "PM10_CONC_GRIMM"],
    "PM25": ["PM25_CONC", "PM02_5_UGM3", "PM25_UGM3", "Conc_PM25", "Val_GRIMM_PM25", "PM25_CONC_GRIMM"],
    "PM10_ESTADO": ["PM10_ESTADO", "PM10_0_ESTADO", "Status", "Val_GRIMM_Estado", "PM10_ENVIDAS"],
    "PM25_ESTADO": ["PM25_ESTADO", "PM02_5_ESTADO", "Status", "Val_GRIMM_Estado"],
    "SO2": ["TH43iQ_SO2_meas_Avg", "SO2_PPB", "SO2_CONC"],
    "PBAR": ["PBAR", "PBAR_HPa", "BP_mbar_Avg", "Pres_hPa_Avg", "VALOR_PRES_BAROMETRICA"],
    "PP": ["PP", "PP_mm", "Rain_mm_Tot", "Rain_mm_Avg", "VALOR_PRECIPITACION"],
    "TEMP": ["TEMP", "TEMP_°C", "AirTC_Avg", "VALOR_TEMPERATURA"],
    "HR": ["HR", "HR_%", "RH_Avg", "VALOR_HUMEDAD_RELATIVA"],
    "WS": ["ws", "ws_m/s", "WS", "WS_ms", "VALOR_VELOCIDAD_VIENTO"],
    "WD": ["wd", "wd_°", "WD", "WindDir", "VALOR_DIRECCION_VIENTO"],
}
TEXTO = {"PM10_ESTADO", "PM25_ESTADO"}
UNIDADES = {"PM10": "µg/m³", "PM25": "µg/m³", "SO2": "ppb", "PBAR": "mmHg", "PP": "mm", "TEMP": "°C",
            "HR": "%", "WS": "m/s", "WD": "grados"}
COLUMNAS_FECHA = ["date", "TIMESTAMP"]

# Reglas de limpieza (las mismas del proyecto: script 01 y 01b)
DOMINIO_REGISTRO = {"PM10": (0, np.inf), "PM25": (0, np.inf), "SO2": (0, np.inf), "PBAR": (400, 800),
                    "TEMP": (-20, 45), "HR": (1, 100), "WS": (0, 60), "WD": (0, 360), "PP": (0, 100)}
DOMINIO_HORARIO = {"PM10": (0, 600), "PM25": (0, 500)}      # REGLAS_DOMINIO del script 01 (medias horarias)
RACHA_CEROS_MIN = 30
PLANOS_MIN = {"PM10": 60, "PM25": 60, "TEMP": 180, "HR": 180, "WS": 180, "WD": 180, "PBAR": 720}
UMBRAL_HPA = 560        # PBAR > 560 -> está en hPa (a ~3 300-4 200 m: 460-520 mmHg = 610-690 hPa)
MIN_FRACCION_HORA, MIN_HORAS_DIA = 0.75, 18
# Códigos de PM10_ESTADO / PM25_ESTADO (sin significado oficial; criterio confirmado por el usuario:
# solo los que claramente corresponden a datos válidos; el resto -incluido "sin código"- es faltante).
# Evidencia: 0 es el estado normal más frecuente; con 8 se reproducen los promedios horarios
# VALIDADOS del OEFA (1A.csv, dic 2021): CA-COLQ-01 98.8 % de horas idénticas incluyendo 8 frente a
# 46/260 horas sin él; CA-TAL-01 95.8 % frente a 92.5 %. -9999, -2147483648 y X traen PM nulo o 0.
CODIGOS_VALIDOS = {"0", "8"}
FILTRAR_ESTADOS = True
REUBICACION_TAL = "2025-07-11"     # CA-TAL-01: el equipo se reubicó (archivos rotulados CA-TAL-02)


def normalizar_codigo(c: pd.Series) -> pd.Series:
    c = c.astype("string").str.strip().fillna("(vacío)")
    num = pd.to_numeric(c, errors="coerce")
    return c.where(num.isna(), num.map(lambda x: str(int(x)) if pd.notna(x) and float(x).is_integer() else str(x)))
VARIABLES = ["PM10", "PM25", "SO2", "PBAR", "PP", "TEMP", "HR", "WS", "WD"]
ECA_PM25 = 50
MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]


def md5(ruta: str) -> str:
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_fig(nombre: str):
    plt.savefig(os.path.join(CARPETA_FIG, f"{nombre}.png"), dpi=300, bbox_inches="tight")
    plt.show()
    plt.close("all")


# %% [markdown]
# ## 2. Conversión de los PDF a CSV (antes del inventario, que usa sus resultados)
#
# Los PDF de CA-TAL-02 son el "Anexo 2 - Registro de datos crudos" del OEFA: tabla de registros
# de 5 minutos con texto (no escaneados). Con la tolerancia vertical por defecto pdfplumber mezcla
# filas (el interlineado, 2.76 pt, es menor que 3 pt); se extrae con y_tolerance = 1.

# %%
import pdfplumber


RE_INICIO = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: UTC)?|\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2})")
RE_IZQUIERDA = re.compile(r"(?P<id>\d{2})?\s*(?P<fecha>\d{1,2}/\d{1,2}/\d{4})\s+(?P<hora>\d{1,2}:\d{2}:\d{2})\s*$")


def lineas_con_palabras(pagina) -> list:
    """Palabras con posición agrupadas por fila (tolerancia vertical de 1 pt)."""
    palabras = sorted(pagina.extract_words(x_tolerance=1.5, y_tolerance=1), key=lambda w: (w["top"], w["x0"]))
    lineas = []
    for w in palabras:
        if lineas and abs(w["top"] - lineas[-1]["top"]) < 1.0:
            lineas[-1]["palabras"].append(w)
        else:
            lineas.append({"top": w["top"], "palabras": [w]})
    for ln in lineas:
        ln["palabras"].sort(key=lambda w: w["x0"])
        ln["texto"] = " ".join(w["text"] for w in ln["palabras"])
    return lineas


def convertir_pdf(ruta: str, carpeta_salida: str) -> tuple:
    """Cada valor se asigna a su columna por la POSICIÓN horizontal: las celdas vacías no dejan
    texto en el PDF, así que el orden no basta. Los centros de columna se estiman en cada página
    con las filas completas (14 valores); si una página tiene pocas, con las de todo el documento."""
    filas, problemas, lineas_no_datos = [], [], 0
    with pdfplumber.open(ruta) as pdf:
        n_paginas = len(pdf.pages)
        paginas = [lineas_con_palabras(p) for p in pdf.pages]
    sin_texto = sum(1 for p in paginas if not p)

    def centros(lineas):
        """Posición de referencia de cada columna: el borde (izquierdo o derecho) más estable en
        las filas completas; un '0' angosto y un '507,4707' ancho comparten ese borde, no el centro."""
        x0, x1, borde = [], [], []
        for ln in lineas:
            m = RE_FILA_PDF.match(ln["texto"])
            if m and len(m.group("valores").split()) == len(COLUMNAS_PDF):
                vals = ln["palabras"][-len(COLUMNAS_PDF):]
                x0.append([w["x0"] for w in vals])
                x1.append([w["x1"] for w in vals])
                borde.append(ln["palabras"][-len(COLUMNAS_PDF) - 1]["x1"])
        if not x0:
            return None, None, 0
        x0, x1 = np.array(x0), np.array(x1)
        usa_derecho = x1.std(axis=0) < x0.std(axis=0)
        ref = np.where(usa_derecho, np.median(x1, axis=0), np.median(x0, axis=0))
        return (ref, usa_derecho), float(np.median(borde)), len(x0)

    centros_doc, borde_doc, n_doc = centros([ln for p in paginas for ln in p])
    for ip, lineas in enumerate(paginas):
        cen, borde, n = centros(lineas)
        if n < 20:
            cen, borde = centros_doc, borde_doc
        if cen is None:
            problemas.append({"pagina": ip + 1, "problema": "sin filas completas para ubicar columnas", "texto": ""})
            continue
        ref, usa_derecho = cen
        tolerancia = 0.5 * np.min(np.abs(np.diff(ref)))
        for ln in lineas:
            m0 = RE_INICIO.match(ln["texto"])
            if not m0:
                lineas_no_datos += 1
                continue
            izquierda = [w for w in ln["palabras"] if w["x1"] <= borde + 0.5]
            derecha = [w for w in ln["palabras"] if w["x1"] > borde + 0.5]
            texto_izq = " ".join(w["text"] for w in izquierda)[len(m0.group(1)):]
            mi = RE_IZQUIERDA.search(texto_izq)
            fila = {"date": m0.group(1), "ID_ESTACION": mi.group("id") if mi else "",
                    "FECHA_DATA": mi.group("fecha") if mi else "", "HORA_DATA": mi.group("hora") if mi else "",
                    **{c: "" for c in COLUMNAS_PDF}, "_pagina": ip + 1, "_top": round(ln["top"], 2)}
            ambiguo = False
            if len(derecha) == len(COLUMNAS_PDF):   # fila completa: la asignación por orden es inequívoca
                fila.update({c: w["text"] for c, w in zip(COLUMNAS_PDF, derecha)})
                derecha = []
            for w in derecha:
                d = np.abs(ref - np.where(usa_derecho, w["x1"], w["x0"]))
                j = int(np.argmin(d))
                if d[j] > tolerancia or fila[COLUMNAS_PDF[j]] != "":
                    ambiguo = True
                    break
                fila[COLUMNAS_PDF[j]] = w["text"]
            if ambiguo:
                problemas.append({"pagina": ip + 1, "problema": "valor sin columna clara (no se convierte)",
                                  "texto": ln["texto"][:160]})
                continue
            vacias = sum(fila[c] == "" for c in COLUMNAS_PDF)
            fila["_celdas_vacias"] = vacias
            if vacias or not mi:
                problemas.append({"pagina": ip + 1, "problema": f"{vacias} celdas vacías" + ("" if mi else
                                  "; sin ID/FECHA_DATA/HORA_DATA"), "texto": ln["texto"][:160]})
            filas.append(fila)
    df = pd.DataFrame(filas)
    nombre = os.path.splitext(os.path.basename(ruta))[0] + ".csv"
    os.makedirs(carpeta_salida, exist_ok=True)
    df.drop(columns=["_pagina", "_top", "_celdas_vacias"]).to_csv(os.path.join(carpeta_salida, nombre), sep=";",
                                                                  index=False)
    return df, problemas, {"paginas": n_paginas, "paginas_sin_texto": sin_texto, "lineas_no_datos": lineas_no_datos,
                           "filas_completas_referencia": n_doc, "csv": os.path.join(carpeta_salida, nombre)}


def verificar_pdf(ruta: str, df: pd.DataFrame, anio: int, mes: int, n_muestras: int = 6) -> dict:
    """Relectura independiente de filas al azar (caracteres del PDF a la altura de la fila) y
    controles de coherencia: pasos de 5 min, duplicados, decimales, rangos."""
    rng = np.random.default_rng(wc.SEMILLA)
    # Mitad de las muestras entre filas completas y mitad entre filas con celdas vacías (si las hay)
    completas = np.flatnonzero(df["_celdas_vacias"].to_numpy() == 0)
    parciales = np.flatnonzero(df["_celdas_vacias"].to_numpy() > 0)
    k = min(n_muestras // 2, len(parciales))
    idx = np.concatenate([rng.choice(completas, size=min(n_muestras - k, len(completas)), replace=False),
                          rng.choice(parciales, size=k, replace=False) if k else np.array([], dtype=int)])
    coincidencias, detalle = 0, []
    with pdfplumber.open(ruta) as pdf:
        for i in idx:
            f = df.iloc[i]
            pag = pdf.pages[int(f["_pagina"]) - 1]
            chars = sorted([c for c in pag.chars if abs(c["top"] - f["_top"]) < 0.8], key=lambda c: c["x0"])
            texto, prev = "", None
            for c in chars:   # espacio cuando el hueco supera medio ancho de carácter
                if prev is not None and c["x0"] - prev["x1"] > 0.5 * (prev["x1"] - prev["x0"]):
                    texto += " "
                texto += c["text"]
                prev = c
            esperado = " ".join(str(f[c]) for c in COLUMNAS_PDF if str(f[c]) != "")
            ok = esperado in re.sub(r"\s+", " ", texto)
            coincidencias += ok
            detalle.append({"pagina": int(f["_pagina"]), "fecha": f["date"], "celdas_vacias": int(f["_celdas_vacias"]),
                            "coincide": ok, "valores_csv": esperado[:90], "relectura_pdf": texto[-110:]})
    fechas, orden, _ = war.parsear_fecha(df["date"], anio, mes)
    paso = fechas.sort_values().diff().dt.total_seconds().div(60)
    num = df[COLUMNAS_PDF].apply(lambda s: pd.to_numeric(s.astype(str).str.replace(",", "."), errors="coerce"))
    con_decimal = df[["PBAR", "TEMP", "HR", "PM10_CONC"]].astype(str).apply(
        lambda s: s.str.contains(r"[.,]").mean()).round(3).to_dict()
    return {"muestras_verificadas": len(idx), "muestras_coinciden": coincidencias,
            "desde": fechas.min(), "hasta": fechas.max(), "orden_fecha": orden,
            "fechas_invalidas": int(fechas.isna().sum()), "fechas_repetidas": int(fechas.duplicated().sum()),
            "pct_paso_5min": round((paso == 5).mean() * 100, 2),
            "registros_esperados_mes": pd.Period(f"{anio}-{mes:02d}").days_in_month * 288,
            "separador_decimal": "coma" if df["TEMP"].astype(str).str.contains(",").mean() > 0.5 else "punto",
            "fraccion_con_decimales": con_decimal,
            "PM10_min_max": (num["PM10_CONC"].min(), num["PM10_CONC"].max()),
            "TEMP_min_max": (num["TEMP"].min(), num["TEMP"].max()),
            "HR_min_max": (num["HR"].min(), num["HR"].max()),
            "PBAR_mediana": num["PBAR"].median(),
            "valores_no_numericos": int(num.isna().sum().sum() - df[COLUMNAS_PDF].isna().sum().sum()),
            "detalle_muestras": detalle}


RECONVERTIR_PDF = False   # True para rehacer la conversión aunque ya existan los CSV y el log
log_pdf, problemas_pdf = [], []
ruta_log = os.path.join(CARPETA_SALIDA, "log_conversion_pdf.csv")
for est, cfg in ESTACIONES_NUEVAS.items():
    archivos = listar(est, cfg)
    if archivos.empty:
        continue
    for _, a in archivos[archivos["extension"] == ".pdf"].iterrows():
        if any(re.search(p, a["archivo"]) for p in cfg.get("pdf_informe", [])):
            print(f"{a['archivo']}: informe de evaluación (no es registro continuo); no se convierte")
            continue
        csv_pdf = os.path.join(f"Datos_crudos_{est}", "convertidos_pdf", os.path.splitext(a["archivo"])[0] + ".csv")
        if not RECONVERTIR_PDF and os.path.exists(csv_pdf) and os.path.exists(ruta_log):
            print(f"{a['archivo']}: ya convertido ({csv_pdf}); se reutiliza")
            continue
        salida = os.path.join(f"Datos_crudos_{est}", "convertidos_pdf")
        df, probs, meta = convertir_pdf(a["ruta"], salida)
        ver = verificar_pdf(a["ruta"], df, a["anio"], a["mes"])
        for p in probs:
            problemas_pdf.append({"estacion": est, "archivo": a["archivo"], **p})
        log_pdf.append({"estacion": est, "anio": a["anio"], "mes": a["mes"], "archivo_origen": a["archivo"],
                        "csv": meta["csv"], "paginas": meta["paginas"], "paginas_sin_texto": meta["paginas_sin_texto"],
                        "filas_extraidas": len(df), "filas_completas": int((df["_celdas_vacias"] == 0).sum()),
                        "filas_con_celdas_vacias": int((df["_celdas_vacias"] > 0).sum()),
                        "filas_no_convertidas": sum(p["problema"].startswith("valor sin") for p in probs),
                        **{k: v for k, v in ver.items() if k != "detalle_muestras"}})
        print(f"\n{a['archivo']}: {meta['paginas']} págs, {len(df):,} filas (esperadas {ver['registros_esperados_mes']:,}), "
              f"{len(probs)} problemas | {ver['desde']} -> {ver['hasta']} | paso 5 min: {ver['pct_paso_5min']} % | "
              f"muestras al azar que coinciden con la relectura: {ver['muestras_coinciden']}/{ver['muestras_verificadas']}")
        print(pd.DataFrame(ver["detalle_muestras"]).to_string(index=False))
        del df
        gc.collect()
if log_pdf:
    log_pdf = pd.DataFrame(log_pdf)
    log_pdf.to_csv(ruta_log, sep=";", index=False)
    pd.DataFrame(problemas_pdf).to_csv(os.path.join(CARPETA_SALIDA, "log_conversion_pdf_problemas.csv"), sep=";",
                                       index=False)
else:
    log_pdf = pd.read_csv(ruta_log, sep=";")
    problemas_pdf = pd.read_csv(os.path.join(CARPETA_SALIDA, "log_conversion_pdf_problemas.csv"), sep=";").to_dict("records")
print("\nLog de conversión:")
print(log_pdf.drop(columns=["csv"]).to_string(index=False))
if problemas_pdf:
    print("\nProblemas (primeros 20):")
    print(pd.DataFrame(problemas_pdf).head(20).to_string(index=False))

# %% [markdown]
# ## 1. Inventario de archivos (incluye los PDF y su CSV convertido)

# %%
def leer_envidas(ruta: str):
    """Exportación de Envidas (Ilo 2021): línea "Site OEFA n ...", cabecera "Date & Time", fila de
    unidades, ';' como separador, '---' = sin dato y hora con "a. m./p. m." en algunos meses."""
    texto, _ = war.leer_texto(ruta)
    lineas = texto.splitlines()
    i = next(k for k, l in enumerate(lineas[:15]) if l.lstrip("\ufeff").strip('"').startswith("Date & Time"))
    sitio = lineas[0].split(";")[0].strip() if i > 0 else ""
    df = pd.read_csv(io.StringIO("\n".join([lineas[i]] + lineas[i + 2:])), sep=";", dtype=str,
                     keep_default_na=False, na_values=["", "---", "NAN", "NaN"])
    df.columns = [str(c).strip() for c in df.columns]
    f = (df["Date & Time"].astype(str).str.replace(r"\s*a\.\s*m\.", " AM", regex=True)
         .str.replace(r"\s*p\.\s*m\.", " PM", regex=True).str.strip())
    fechas = pd.to_datetime(f, format="%d/%m/%Y %I:%M %p", errors="coerce")
    fechas = fechas.fillna(pd.to_datetime(f, format="%d/%m/%Y %H:%M", errors="coerce"))
    df.insert(0, "date", fechas.dt.strftime("%Y-%m-%d %H:%M:%S"))
    return df.loc[:, ~df.columns.duplicated()], {"formato": f"Envidas CSV ({sitio or 'sin línea de sitio'})"}


def es_envidas(ruta: str) -> bool:
    if not ruta.lower().endswith(".csv"):
        return False
    with open(ruta, "rb") as f:
        return b"Date & Time" in f.read(4000)


def leer_tabular(ruta: str, hoja: str = None):
    if es_envidas(ruta):
        return leer_envidas(ruta)
    if hoja:
        df = pd.read_excel(ruta, sheet_name=hoja, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        return df, {"formato": f"Excel (hoja {hoja})"}
    df, meta = war.leer_archivo(ruta)
    return df.loc[:, ~df.columns.duplicated()], meta


def estandarizar(df: pd.DataFrame, anio: int, mes: int) -> tuple:
    """Columnas estándar (VARIABLES + estados) con FECHA_HORA y el paso de registro."""
    col = next((c for c in COLUMNAS_FECHA if c in df.columns), None)
    if col is None:
        return None, {}
    serial = pd.to_numeric(df[col], errors="coerce")
    if serial.between(30000, 60000).mean() > 0.9:     # fecha como número de serie de Excel (feb 2022)
        fechas = pd.to_datetime(serial, unit="D", origin="1899-12-30").dt.round("s")
    else:
        fechas = war.parsear_fecha(df[col], anio, mes)[0]
    out = pd.DataFrame({"FECHA_HORA": fechas.dt.floor("min")})
    usadas = {}
    coma = war.decimal_con_coma(df)
    for est, variantes in MAPEO.items():
        c = next((v for v in variantes if v in df.columns), None)
        if c is None:
            continue
        usadas[est] = c
        s = df[c].astype("string").str.strip()
        if est in TEXTO:
            out[est] = s
        else:
            if coma or s.str.contains(",").fillna(False).mean() > 0.3:   # fillna: columnas vacías
                s = s.str.replace(",", ".", regex=False)
            out[est] = pd.to_numeric(s, errors="coerce").astype("float64")
    paso = out["FECHA_HORA"].dropna().sort_values().diff().dt.total_seconds().div(60)
    return out, {"columnas": usadas, "paso_min": float(paso.mode().iloc[0]) if len(paso.dropna()) else np.nan}


def archivos_otra_carpeta(buscar: dict) -> pd.DataFrame:
    """Archivos (u hojas de Excel) de la estación que están en la carpeta de otra estación."""
    import openpyxl
    filas = []
    for _, a in war.listar_archivos(buscar["carpeta"]).iterrows():
        if "convertidos_pdf" in a["ruta"]:
            continue
        if re.search(buscar["archivo"], a["archivo"]):
            filas.append({**a.to_dict(), "hoja": None})
        elif a["extension"] == ".xlsx":
            wb = openpyxl.load_workbook(a["ruta"], read_only=True)
            hojas = [h for h in wb.sheetnames if re.search(buscar["hoja"], h)]
            wb.close()
            if hojas:
                filas.append({**a.to_dict(), "hoja": hojas[0]})
    return pd.DataFrame(filas)


inventario, estandar = [], {}
for est, cfg in ESTACIONES_NUEVAS.items():
    archivos = listar(est, cfg)
    archivos = archivos[~archivos["ruta"].str.contains("convertidos_pdf")]
    archivos["hoja"] = archivos["archivo"].map(cfg.get("hojas", {}))
    if "buscar_en" in cfg:
        extra = archivos_otra_carpeta(cfg["buscar_en"]).assign(carpeta=cfg["buscar_en"]["carpeta"])
        print(f"{est}: {len(extra)} archivos/hojas encontrados en {cfg['buscar_en']['carpeta']}")
        archivos = pd.concat([archivos, extra], ignore_index=True)
    vistos = {}
    for _, a in archivos.iterrows():
        nombre, ruta, hoja = a["archivo"], a["ruta"], a["hoja"] if isinstance(a["hoja"], str) else None
        fila = {"estacion": est, "anio": a["anio"], "mes": a["mes"], "archivo": nombre, "extension": a["extension"],
                "tamano_kb": round(os.path.getsize(ruta) / 1024, 1)}
        if a["carpeta"] != f"Datos_crudos_{est}":
            fila["notas"] = f"en {a['carpeta']}"
        if hoja:
            fila["hoja"] = hoja
        firma = md5(ruta)
        if nombre.startswith("~$"):
            fila.update({"estado": "temporal de Excel (vacío)", "formato": "bloqueo de Excel"})
            inventario.append(fila)
            continue
        if any(re.search(p, nombre) for p in cfg.get("no_leer", [])):
            fila.update({"estado": "respaldo / descarga o muestreo manual / informe (no se usa)",
                         "formato": a["extension"]})
            inventario.append(fila)
            continue
        if any(re.search(p, nombre) for p in cfg.get("pdf_informe", [])):
            fila.update({"estado": "informe (no es registro continuo; no se convierte)", "formato": "PDF"})
            inventario.append(fila)
            continue
        clave_firma = firma + (f"|{hoja}" if hoja else "")
        if clave_firma in vistos:
            fila["estado"] = f"duplicado exacto de {vistos[clave_firma]}"
        vistos.setdefault(clave_firma, f"{a['carpeta']}/{a['anio']}/{a['mes']:02d}/{nombre}")
        ruta_lectura = ruta
        if a["extension"] == ".pdf":
            fila["formato"] = "PDF con texto (registro continuo 5 min)"
            ruta_lectura = os.path.join(f"Datos_crudos_{est}", "convertidos_pdf", os.path.splitext(nombre)[0] + ".csv")
        firma_lectura = firma if ruta_lectura == ruta else md5(ruta_lectura)   # PDF: firma del CSV convertido
        sufijo_hoja = f"_{re.sub(r'[^A-Za-z0-9]+', '_', hoja)}" if hoja else ""
        cache = os.path.join(CARPETA_CACHE, f"{firma_lectura}_{a['anio']}_{a['mes']}{sufijo_hoja}.pkl")
        try:
            if os.path.exists(cache):
                std, info, n, ids, meta_fmt = pd.read_pickle(cache)
            else:
                df, meta = leer_tabular(ruta_lectura, hoja)
                std, info = estandarizar(df, a["anio"], a["mes"])
                n = len(df)
                ids = ",".join(df["ID_ESTACION"].dropna().astype(str).unique()[:3]) if "ID_ESTACION" in df else ""
                meta_fmt = meta.get("formato")
                pd.to_pickle((std, info, n, ids, meta_fmt), cache)
                del df
                gc.collect()
        except Exception as e:
            fila.update({"estado": f"ilegible: {type(e).__name__}: {str(e)[:80]}"})
            inventario.append(fila)
            continue
        fila.setdefault("formato", meta_fmt)
        if nombre in cfg.get("id_corregido", {}):
            fila["notas"] = f"ID {ids} en el archivo; corregido a {cfg['id_corregido'][nombre]} (ver configuración)"
            ids = cfg["id_corregido"][nombre]
        fila.update({"n_registros": n, "id_estacion": ids})
        if any(re.search(p, nombre) for p in cfg["no_unificar"]):
            fila.setdefault("estado", "complementario (no se unifica; ver notas)")
        if std is None or std["FECHA_HORA"].notna().sum() == 0:
            fila.setdefault("estado", "sin fecha reconocible / vacío")
            inventario.append(fila)
            continue
        f = std["FECHA_HORA"].dropna()
        if not fila["mes"]:
            fila["mes"] = int(f.dt.month.mode().iloc[0])
            fila["notas"] = (fila.get("notas", "") + " mes tomado de los datos").strip()
        fila.update({"desde": f.min(), "hasta": f.max(), "resolucion_min": info["paso_min"],
                     "variables": ",".join(v for v in VARIABLES if v in std and std[v].notna().any()),
                     "variables_vacias": ",".join(v for v in VARIABLES if v in std and std[v].isna().all()),
                     "columnas_origen": "; ".join(f"{k}={v}" for k, v in info["columnas"].items()),
                     "PBAR_mediana": std["PBAR"].median() if "PBAR" in std else np.nan,
                     "PM10_mediana": std["PM10"].median() if "PM10" in std else np.nan,
                     "pct_PM10_cero": round((std["PM10"] == 0).mean() * 100, 1) if "PM10" in std else np.nan})
        if any(re.search(p, nombre) for p in cfg["otra_estacion"]) or (ids and cfg["id_estacion"] not in ids.split(",")):
            fila.setdefault("estado", f"otra estación (ID {ids})")
        fila.setdefault("estado", "principal")
        if fila["estado"] == "principal":   # solo los principales entran a la unificación
            nombre_u = f"{a['anio']}-{a['mes']:02d}/{nombre}" if "patron" in cfg else nombre
            estandar[(est, a["anio"], a["mes"], nombre)] = std.assign(ARCHIVO=nombre_u, PASO_MIN=info["paso_min"])
        if "CA-TAL-02" in nombre:
            fila["notas"] = "código CA-TAL-02 (¿reubicación?)"
        inventario.append(fila)
    print(f"{est}: {len(archivos)} archivos revisados")

# Archivos de CA-SB-01 (fuente nueva de Simón Bolívar)
for _, a in war.listar_archivos("Datos_crudos_CA-SB-01").iterrows():
    df, meta = war.leer_archivo(a["ruta"])
    inventario.append({"estacion": "CA-SB-01", "anio": a["anio"], "mes": a["mes"], "archivo": a["archivo"],
                       "extension": a["extension"], "tamano_kb": round(os.path.getsize(a["ruta"]) / 1024, 1),
                       "formato": meta["formato"], "n_registros": len(df), "resolucion_min": 60,
                       "estado": "fuente nueva de CA-SB-01 (solo este mes)",
                       "variables": "PM10 (TEOM, sin encabezado)" if "PM10" in a["archivo"] else "meteorología (Davis)"})
inv = pd.DataFrame(inventario).sort_values(["estacion", "anio", "mes", "archivo"])
inv.to_csv(os.path.join(CARPETA_SALIDA, "01_inventario_archivos.csv"), sep=";", index=False)
cols = ["estacion", "anio", "mes", "archivo", "formato", "n_registros", "desde", "hasta", "resolucion_min",
        "id_estacion", "variables", "variables_vacias", "PBAR_mediana", "pct_PM10_cero", "estado"]
print(inv[[c for c in cols if c in inv]].to_string(index=False))

for est in ESTACIONES_NUEVAS:
    n_mes = pd.concat([d["FECHA_HORA"].dropna().dt.to_period("M") for k, d in estandar.items() if k[0] == est]
                      ).value_counts()
    presentes = set(n_mes[n_mes >= 288].index)          # al menos un día de registros de 5 min
    todos = pd.period_range(min(presentes), max(presentes), freq="M")
    faltan = [str(p) for p in todos if p not in presentes]
    print(f"\n{est}: meses sin registros en los archivos principales: {faltan}")

# %% [markdown]
# ## 3. Unificación preliminar por estación
#
# Reglas (las mismas del proyecto): -9999 y filas con todas las variables en cero -> inválidas;
# negativos, dominio, rachas de ceros (>= 30 min) y valores planos; presión en hPa -> mmHg;
# duplicados por fecha-hora (si dos fuentes cubren el mismo registro, se usa la primera con
# valor válido, en el orden: Excel/CSV principales, luego .dat). Los códigos de ESTADO solo se
# describen (no se filtran) hasta confirmarlos con el usuario.

# %%
def unificar(est: str, codigos_validos=None):
    codigos_validos = codigos_de(est) if codigos_validos is None else codigos_validos
    partes = [d for k, d in estandar.items() if k[0] == est]
    if "(sin columna)" in codigos_de(est):    # archivos sin columna de estado (Ilo 2021)
        partes = [d.assign(**{e: "(sin columna)" for e in ("PM10_ESTADO", "PM25_ESTADO") if e not in d})
                  for d in partes]
    prioridad = {".xlsx": 0, ".csv": 0, ".pdf": 0, ".dat": 1}
    crudo = pd.concat(partes, ignore_index=True).dropna(subset=["FECHA_HORA"])
    crudo["_prio"] = crudo["ARCHIVO"].map(lambda n: prioridad.get(os.path.splitext(n)[1].lower(), 2))
    n0 = len(crudo)
    # Presión en hPa -> mmHg (por archivo)
    for arch, g in crudo.groupby("ARCHIVO"):
        if g["PBAR"].median() > UMBRAL_HPA:
            crudo.loc[g.index, "PBAR"] = g["PBAR"] * 0.750062
    # -9999 -> NaN
    num = [v for v in VARIABLES if v in crudo]
    crudo[num] = crudo[num].where(crudo[num] != -9999)
    for v in ("PM10_ESTADO", "PM25_ESTADO"):
        if v in crudo:
            e = crudo[v].astype("string").str.strip()
            bad = e.isin(["-9999", "-9999.00", "-9999.0"])
            crudo.loc[bad, v.replace("_ESTADO", "")] = np.nan
    # Filas con todas las variables en cero
    base = [v for v in ("PM10", "PM25", "PBAR", "TEMP", "HR", "WS", "WD") if v in crudo]
    todo_cero = (crudo[base].fillna(0) == 0).all(axis=1) & crudo[base].notna().any(axis=1)
    crudo.loc[todo_cero, num] = np.nan
    bitacora = [{"regla": "Filas con todas las variables en cero", "registros": int(todo_cero.sum())}]
    # Códigos de estado: solo los claramente válidos
    if FILTRAR_ESTADOS:
        for v_est, v in (("PM10_ESTADO", "PM10"), ("PM25_ESTADO", "PM25")):
            if v_est in crudo and v in crudo:
                cod = normalizar_codigo(crudo[v_est])
                malo = ~cod.isin(codigos_validos) & crudo[v].notna()
                for c, n in cod[malo].value_counts().items():
                    bitacora.append({"regla": f"{v}: código de estado '{c}' tratado como faltante", "registros": int(n)})
                crudo.loc[malo, v] = np.nan
    crudo = crudo.sort_values(["FECHA_HORA", "_prio", "ARCHIVO"])

    # Reglas por variable
    for v in num:
        lo, hi = DOMINIO_REGISTRO[v]
        fuera = crudo[v].notna() & ~crudo[v].between(lo, hi)
        bitacora.append({"regla": f"{v} fuera de dominio [{lo}, {hi}]", "registros": int(fuera.sum())})
        crudo.loc[fuera, v] = np.nan
    t = crudo["FECHA_HORA"]
    for v in [x for x in ("PM10", "PM25") if x in crudo]:
        for arch, g in crudo.groupby("ARCHIVO"):
            g = g.sort_values("FECHA_HORA")
            cero = g[v] == 0
            grupo = ((g[v] != g[v].shift()) | (cero != cero.shift())).cumsum()
            dur = g["PASO_MIN"].groupby(grupo).transform("sum")
            m = cero & (dur >= RACHA_CEROS_MIN)
            crudo.loc[g.index[m], v] = np.nan
            plano = (g[v] != 0) & g[v].notna() & (dur >= PLANOS_MIN[v])
            crudo.loc[g.index[plano], v] = np.nan
            bitacora.append({"regla": f"{v}: rachas de ceros >= {RACHA_CEROS_MIN} min / planos ({arch[:30]})",
                             "registros": int(m.sum() + plano.sum())})
    # Duplicados por fecha-hora: primera fuente con valor válido por variable
    agg = crudo.groupby("FECHA_HORA", sort=True)
    unif = agg[num].first()
    for v in ("PM10_ESTADO", "PM25_ESTADO"):
        if v in crudo:
            unif[v] = agg[v].first()
    unif["PASO_MIN"] = agg["PASO_MIN"].min()
    unif["ARCHIVO"] = agg["ARCHIVO"].first()
    bitacora.insert(0, {"regla": "Registros leídos (archivos principales)", "registros": n0})
    bitacora.append({"regla": "Registros únicos por fecha-hora", "registros": len(unif)})
    return unif, pd.DataFrame(bitacora)


def agregar(unif: pd.DataFrame):
    base = unif.copy()
    base["HORA"] = base.index.floor("h")
    num = [v for v in VARIABLES if v in base]
    if "WD" in base:
        rad = np.deg2rad(base["WD"])
        base["WD_SIN"], base["WD_COS"] = np.sin(rad), np.cos(rad)
    g = base.groupby("HORA")
    esperados = 60 / g["PASO_MIN"].min().clip(lower=1)
    hor = pd.DataFrame(index=esperados.index)
    for v in num:
        ok = g[v].count() / esperados >= MIN_FRACCION_HORA
        if v == "PP":
            hor[v] = g[v].sum(min_count=1).where(ok)
        elif v == "WD":
            hor["WD_SIN"], hor["WD_COS"] = g["WD_SIN"].mean().where(ok), g["WD_COS"].mean().where(ok)
        else:
            hor[v] = g[v].mean().where(ok)
    for v, (lo, hi) in DOMINIO_HORARIO.items():
        if v in hor:
            hor[v] = hor[v].where(hor[v].between(lo, hi) | hor[v].isna())
    hor = hor.asfreq("h")
    gd = hor.groupby(hor.index.floor("D"))
    dia = pd.DataFrame({v: (gd[v].sum(min_count=1) if v == "PP" else gd[v].mean()).where(gd[v].count() >= MIN_HORAS_DIA)
                        for v in hor.columns})
    return hor, dia.asfreq("D")


unificados = {}
for est in ESTACIONES_NUEVAS:
    unif, bit = unificar(est)
    hor, dia = agregar(unif)
    unificados[est] = {"5min": unif, "hora": hor, "dia": dia, "bitacora": bit}
    largo = unif[[v for v in VARIABLES if v in unif]].stack().rename("VALOR").reset_index()
    largo.columns = ["FECHA_HORA", "VARIABLE", "VALOR"]
    largo["UNIDAD"] = largo["VARIABLE"].map(UNIDADES)
    largo.to_parquet(os.path.join(CARPETA_SALIDA, f"02_{est}_estandarizado_5min.parquet"), index=False)
    unif.to_parquet(os.path.join(CARPETA_SALIDA, f"02_{est}_5min_ancho.parquet"))   # incluye los códigos de estado
    hor.to_pickle(os.path.join(CARPETA_SALIDA, f"02_{est}_horario.pkl"))
    dia.to_pickle(os.path.join(CARPETA_SALIDA, f"02_{est}_diario.pkl"))
    bit.to_csv(os.path.join(CARPETA_SALIDA, f"02_{est}_bitacora_limpieza.csv"), sep=";", index=False)
    print(f"\n=== {est}: {len(unif):,} registros únicos ({unif.index.min()} -> {unif.index.max()}) | "
          f"horas con PM10 válido: {hor['PM10'].notna().sum():,} | días con PM10 válido: {dia['PM10'].notna().sum():,}")
    print(bit[bit["registros"] > 0].to_string(index=False))
    del largo
    gc.collect()

# %% [markdown]
# ### Códigos de PM10_ESTADO y PM25_ESTADO (solo descripción; significado por confirmar)

# %%
for est, u in unificados.items():
    for v in ("PM10_ESTADO", "PM25_ESTADO"):
        if v not in u["5min"]:
            continue
        x = u["5min"].assign(COD=u["5min"][v].fillna("(vacío)").astype(str),
                             ANIO=u["5min"].index.year)
        t = x.groupby("COD").agg(registros=("COD", "size"), desde=("ANIO", "min"), hasta=("ANIO", "max"),
                                 mediana_valor=(v.replace("_ESTADO", ""), "median"))
        t["%"] = (t["registros"] / t["registros"].sum() * 100).round(2)
        t = t.sort_values("registros", ascending=False)
        t.to_csv(os.path.join(CARPETA_SALIDA, f"03_{est}_codigos_{v}.csv"), sep=";")
        print(f"\n{est} - {v}:")
        print(t.head(25).to_string())

# %% [markdown]
# ### Hora local o UTC
#
# 1) Ciclo diario: hora del máximo de la temperatura media y del mínimo de la HR por año
#    (hora local de Perú: ~13-15 h). 2) Correlación horaria con el mismo mes de 1A.csv (dic 2021
#    para CA-COLQ-01 y CA-TAL-01), probando desfases de -8 a +8 h.

# %%
filas = []
for est, u in unificados.items():
    h = u["hora"]
    for anio, g in h.groupby(h.index.year):
        fila = {"estacion": est, "anio": anio}
        for v, fn in (("TEMP", "idxmax"), ("HR", "idxmin"), ("PM10", "idxmax")):
            if v in g and g[v].notna().sum() > 200:
                perfil = g.groupby(g.index.hour)[v].mean()
                fila[f"hora_{'max' if fn == 'idxmax' else 'min'}_{v}"] = int(getattr(perfil, fn)())
        filas.append(fila)
ciclo = pd.DataFrame(filas)
print(ciclo.to_string(index=False))

oefa = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, "01_mediciones_marcadas.pkl"))
oefa = oefa[oefa["NOMBRE_PUNTO"].isin(list(ESTACIONES_NUEVAS)) & ~oefa["FLAG_DOMINIO"] & ~oefa["FLAG_CERO_RACHA"]]
zona = []
for est, u in unificados.items():
    o = oefa[oefa["NOMBRE_PUNTO"] == est].pivot_table(index="FECHA_HORA", columns="VARIABLE", values="VALOR")
    for var_o, var_n in (("PM10", "PM10"), ("PM2.5", "PM25"), ("TEMPERATURA", "TEMP")):
        if var_o not in o or var_n not in u["hora"]:
            continue
        corr = {}
        for L in range(-8, 9):
            n = u["hora"][var_n].copy()
            n.index = n.index + pd.Timedelta(hours=L)
            c = pd.concat([o[var_o], n], axis=1, join="inner").dropna()
            if len(c) > 24:
                corr[L] = c.iloc[:, 0].corr(c.iloc[:, 1])
        if corr:
            L = max(corr, key=corr.get)
            n = u["hora"][var_n].copy()
            c = pd.concat([o[var_o], n], axis=1, join="inner").dropna()
            zona.append({"estacion": est, "variable": var_n, "horas_comunes": len(c), "desfase_optimo_h": L,
                         "corr_0h": round(corr.get(0, np.nan), 4), "corr_optima": round(corr[L], 4),
                         "dif_media_0h": round((c.iloc[:, 1] - c.iloc[:, 0]).mean(), 3)})
zona = pd.DataFrame(zona)
zona.to_csv(os.path.join(CARPETA_SALIDA, "03_zona_horaria.csv"), sep=";", index=False)
print(zona.to_string(index=False))

# %% [markdown]
# ## 4. Cobertura mensual (% de días con promedio diario válido) y huecos > 30 días

# %%
def serie_referencia(est: str) -> pd.DataFrame:
    """Series diarias de referencia del 1A.csv (dataset del script 01)."""
    ds = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, f"03_dataset_{est}_PM10.pkl")).asfreq("D")
    return pd.DataFrame({"PM10": ds["OBJETIVO"], "TEMP": ds.get("TEMPERATURA"), "HR": ds.get("HUMEDAD_RELATIVA")})


diarios = {est: u["dia"] for est, u in unificados.items()}
for dep, ref in REFERENCIA_1A.items():
    diarios[f"{ref} (1A.csv)"] = serie_referencia(ref)


def cobertura(serie: pd.Series) -> pd.DataFrame:
    c = (serie.notna().groupby(serie.index.to_period("M")).mean() * 100).round(1)
    t = c.to_frame("pct").assign(anio=c.index.year, mes=c.index.month).pivot(index="anio", columns="mes", values="pct")
    return t.reindex(columns=range(1, 13))


def huecos(serie: pd.Series, minimo: int = 31) -> pd.DataFrame:
    s = serie.loc[serie.first_valid_index():serie.last_valid_index()]
    h = s.isna()
    b = (h != h.shift()).cumsum()
    t = s[h].groupby(b[h]).apply(lambda x: pd.Series({"desde": x.index.min().date(), "hasta": x.index.max().date(),
                                                       "dias": len(x)}))
    t = t.unstack() if isinstance(t, pd.Series) else t
    return t[t["dias"] >= minimo].reset_index(drop=True) if len(t) else pd.DataFrame(columns=["desde", "hasta", "dias"])


for var in ("PM10", "PM25"):
    series = {k: d[var] for k, d in diarios.items() if var in d and d[var].notna().sum() > 0}
    fig, axes = plt.subplots(len(series), 1, figsize=(11, 2.3 * len(series) + 0.8), squeeze=False)
    for ax, (k, s) in zip(axes[:, 0], series.items()):
        t = cobertura(s)
        t.to_csv(os.path.join(CARPETA_SALIDA, f"04_cobertura_{var}_{k.split()[0]}.csv"), sep=";")
        print(f"\n{k} - {var}: % de días con promedio diario válido")
        print(t.set_axis(MESES_ES, axis=1).to_string())
        hs = huecos(s)
        print(f"Huecos > 30 días: {len(hs)}")
        if len(hs):
            print(hs.to_string(index=False))
        sns.heatmap(t.set_axis(MESES_ES, axis=1), ax=ax, cmap="Blues", vmin=0, vmax=100, annot=True, fmt=".0f",
                    cbar=False, annot_kws={"size": 7})
        ax.set_title(f"{k} - {'PM$_{10}$' if var == 'PM10' else 'PM$_{2.5}$'}: % de días con promedio diario válido",
                     fontsize=10)
        ax.set_xlabel("")
        ax.set_ylabel("Año")
    plt.tight_layout()
    guardar_fig(f"fig01_cobertura_{var}")

# %% [markdown]
# ## 5. Comparación por departamento

# %%
def resumen_estacion(nombre: str, d: pd.DataFrame, var: str = "PM10", eca: float = 100) -> dict:
    s = d[var] if var in d else pd.Series(dtype=float)
    v = s.dropna()
    if v.empty:
        return {"estacion": nombre, "dias_validos": 0}
    hs = huecos(s)
    todos = huecos(s, minimo=1)
    ult = v.index.max()
    reciente = s.loc[ult - pd.Timedelta(days=547):ult]
    return {
        "estacion": nombre, "desde": v.index.min().date(), "hasta": ult.date(),
        "anios_de_periodo": round((ult - v.index.min()).days / 365.25, 1), "dias_validos": len(v),
        "pct_dias_validos_en_periodo": round(len(v) / ((ult - v.index.min()).days + 1) * 100, 1),
        "hueco_mas_largo_dias": int(todos["dias"].max()) if len(todos) else 0,
        "huecos_mayores_30_dias": len(hs),
        "dias_validos_ultimos_18_meses": int(reciente.notna().sum()),
        "variables_meteo": ",".join(x for x in ("TEMP", "HR", "WS", "WD", "PBAR", "PP") if x in d and d[x].notna().sum() > 100),
        "PM25_disponible": "PM25" in d and d["PM25"].notna().sum() > 30,
        "media": round(v.mean(), 1), "mediana": round(v.median(), 1), "p95": round(v.quantile(0.95), 1),
        "pct_moderada_o_peor": round((v > 0.5 * eca).mean() * 100, 1),
        "dias_moderada_o_peor": int((v > 0.5 * eca).sum()), "dias_sobre_ECA": int((v > eca).sum()),
    }


comparacion = []
for dep, ref in REFERENCIA_1A.items():
    nuevas = [e for e, c in ESTACIONES_NUEVAS.items() if c["departamento"] == dep]
    for nombre in nuevas + [f"{ref} (1A.csv)"]:
        comparacion.append({"departamento": dep, **resumen_estacion(nombre, diarios[nombre])})
comparacion = pd.DataFrame(comparacion)
comparacion.to_csv(os.path.join(CARPETA_SALIDA, "05_comparacion_estaciones_PM10.csv"), sep=";", index=False)
print(comparacion.T.to_string())

# CA-TAL-01 por tramo de código (TAL-01 hasta el 10/07/2025; TAL-02 desde el 11/07/2025)
corte, codigo = ESTACIONES_NUEVAS["CA-TAL-01"]["cambio_codigo"]
d = diarios["CA-TAL-01"]
print("\nCA-TAL-01 por tramo:")
print(pd.DataFrame([resumen_estacion("CA-TAL-01 (hasta 10/07/2025)", d.loc[:pd.Timestamp(corte) - pd.Timedelta(days=1)]),
                    resumen_estacion(f"{codigo} (desde {corte})", d.loc[corte:])]).T.to_string())
print("Presión mediana (mmHg) por año (un salto indica reubicación en altura):")
print(d["PBAR"].groupby(d.index.year).median().round(1).to_string())

# Serie combinable: coincidencia con 1A.csv en el periodo común (solo misma estación)
print("\nCoincidencia con 1A.csv (misma estación, días comunes):")
for est, u in unificados.items():
    o = oefa[(oefa["NOMBRE_PUNTO"] == est) & (oefa["VARIABLE"] == "PM10")]
    od = o.groupby(o["FECHA_HORA"].dt.floor("D"))["VALOR"].agg(["mean", "size"])
    od = od.loc[od["size"] >= 18, "mean"]
    c = pd.concat([od.rename("1A"), u["dia"]["PM10"].rename("nuevo")], axis=1, join="inner").dropna()
    print(f"{est}: {len(c)} días comunes" + (f" | r = {c['1A'].corr(c['nuevo']):.4f}, dif. media = "
                                               f"{(c['nuevo'] - c['1A']).mean():.3f} µg/m³" if len(c) > 2 else ""))

# CA-SB-01: fuente nueva (ene 2021, TEOM horario) vs 1A.csv
# Dos líneas de cabecera del equipo (número de serie, versión) y una vacía; luego filas de 16 campos
teom = pd.read_csv("Datos_crudos_CA-SB-01/2021/Enero/PM10_TEOM_CA-SB-01_1H_ENE_2021.csv", header=None, skiprows=3)
teom["FECHA_HORA"] = pd.to_datetime(teom[0].astype(str) + " " + teom[1].astype(str), errors="coerce").dt.floor("h")
for col in teom.columns[2:16]:
    teom[col] = pd.to_numeric(teom[col], errors="coerce")
o = oefa if "CA-SB-01" in oefa["NOMBRE_PUNTO"].unique() else None
oe_sb = pd.read_pickle(os.path.join(wc.CARPETA_DATOS, "01_mediciones_marcadas.pkl"))
oe_sb = oe_sb[(oe_sb["NOMBRE_PUNTO"] == "CA-SB-01") & (oe_sb["VARIABLE"] == "PM10")].set_index("FECHA_HORA")["VALOR"]
filas_sb = []
for col in teom.columns[2:8]:
    c = pd.concat([oe_sb.rename("1A"), teom.set_index("FECHA_HORA")[col].rename("nuevo")], axis=1, join="inner").dropna()
    if len(c) > 24:
        filas_sb.append({"columna_TEOM": col, "horas_comunes": len(c), "corr": round(c.corr().iloc[0, 1], 4),
                         "cociente_mediano": round((c["nuevo"] / c["1A"]).median(), 3)})
print("\nCA-SB-01 fuente nueva (TEOM, ene 2021) vs 1A.csv, horario:")
print(pd.DataFrame(filas_sb).to_string(index=False))
del oe_sb
gc.collect()

# %% [markdown]
# ### Evaluación de PM2.5 (donde exista)

# %%
filas = []
for est, u in unificados.items():
    d = u["dia"]
    if "PM25" not in d or d["PM25"].notna().sum() < 30:
        continue
    r = resumen_estacion(est, d, "PM25", ECA_PM25)
    c = d[["PM10", "PM25"]].dropna()
    c = c[c["PM10"] > 0]
    r.update({"corr_diaria_PM25_PM10": round(c["PM10"].corr(c["PM25"]), 3),
              "cociente_medio_PM25_PM10": round((c["PM25"] / c["PM10"]).mean(), 3),
              "cociente_mediano_PM25_PM10": round((c["PM25"] / c["PM10"]).median(), 3), "dias_con_ambos": len(c)})
    filas.append(r)
pm25 = pd.DataFrame(filas)
pm25.to_csv(os.path.join(CARPETA_SALIDA, "05_evaluacion_PM25.csv"), sep=";", index=False)
print(pm25.T.to_string())

# %%
# Serie diaria de PM10 de las cuatro estaciones (para ver periodos y huecos)
fig, axes = plt.subplots(len(diarios), 1, figsize=(13, 2.2 * len(diarios)), sharex=True)
for ax, (k, d) in zip(axes, diarios.items()):
    ax.plot(d.index, d["PM10"], lw=0.6, color="#4472C4")
    ax.axhline(100, color="#D7263D", ls="--", lw=0.8, label="ECA 24 h (100 µg/m³)")
    ax.axhline(50, color="#F2C12E", ls="-.", lw=0.8, label="INCA 50")
    ax.set_title(k, fontsize=10)
    ax.set_ylabel("µg/m³")
axes[0].legend(fontsize=8, loc="upper left")
axes[-1].set_xlabel("Fecha")
plt.tight_layout()
guardar_fig("fig02_series_diarias_PM10")
print(f"\nSalidas en {CARPETA_SALIDA}/ y figuras en {CARPETA_FIG}/")

# %% [markdown]
# ## 6. Impacto de tratar "sin código" de estado como faltante (criterio conservador)

# %%
impacto = []
for est in ESTACIONES_NUEVAS:
    u_alt, _ = unificar(est, codigos_de(est) | {"(vacío)"})
    _, dia_alt = agregar(u_alt)
    base = unificados[est]["dia"]["PM10"]
    alt = dia_alt["PM10"]
    for anio in sorted(set(base.index.year)):
        b, a = base[base.index.year == anio], alt[alt.index.year == anio]
        impacto.append({"estacion": est, "anio": anio, "dias_validos_criterio": int(b.notna().sum()),
                        "dias_validos_si_se_acepta_sin_codigo": int(a.notna().sum()),
                        "dias_perdidos": int(a.notna().sum() - b.notna().sum())})
    del u_alt, dia_alt
    gc.collect()
impacto = pd.DataFrame(impacto)
impacto.to_csv(os.path.join(CARPETA_SALIDA, "06_impacto_sin_codigo.csv"), sep=";", index=False)
print(impacto.to_string(index=False))

# %% [markdown]
# ## 7. Datasets diarios para modelar (mismo formato que 03_dataset_<estación>_<contaminante>)
#
# Solo PM10 (decisión del usuario). CA-TAL-01: TAL-01 y TAL-02 son una sola estación (el equipo se
# reubicó en julio de 2025): serie continua con la columna REUBICACION (0 antes, 1 desde
# REUBICACION_TAL). Sufijo "_ar" (alta resolución): no reemplaza los datasets de 1A.csv.

# %%
NOMBRES = {"PBAR": "PRESION_BAROMETRICA", "TEMP": "TEMPERATURA", "HR": "HUMEDAD_RELATIVA",
           "WS": "VELOCIDAD_VIENTO", "PP": "PRECIPITACION"}
for est, cfg in ESTACIONES_NUEVAS.items():
    d = unificados[est]["dia"]
    h = unificados[est]["hora"]
    gh = h["PM10"].groupby(h.index.floor("D"))
    ds = pd.DataFrame(index=d.index)
    ds["OBJETIVO"] = d["PM10"]
    ds["INCA"] = wc.valor_inca(ds["OBJETIVO"], "PM10")
    ds["CATEGORIA_INCA"] = wc.categoria_inca(ds["OBJETIVO"], "PM10").values
    ds["SUPERA_ECA"] = (ds["OBJETIVO"] > wc.ECA_24H["PM10"]).where(ds["OBJETIVO"].notna())
    ds["SUPERA_OMS"] = (ds["OBJETIVO"] > wc.OMS_24H["PM10"]).where(ds["OBJETIVO"].notna())
    for v, nombre in NOMBRES.items():
        if v in d:
            ds[nombre] = d[v]
    ds["VIENTO_SIN"], ds["VIENTO_COS"] = d.get("WD_SIN"), d.get("WD_COS")
    ds["MAXIMO_HORARIO"] = gh.max().where(gh.count() >= MIN_HORAS_DIA).reindex(ds.index)
    if est == "CA-TAL-01":
        ds["REUBICACION"] = (ds.index >= pd.Timestamp(REUBICACION_TAL)).astype(float)
    ds = ds.loc[ds["OBJETIVO"].first_valid_index():].asfreq("D")
    ds["DIA_SEMANA"], ds["MES"] = ds.index.dayofweek, ds.index.month
    ds.insert(0, "CONTAMINANTE", "PM10")
    ds.insert(0, "NOMBRE_PUNTO", est)
    ds.insert(0, "DEPARTAMENTO", cfg["departamento"])
    ds.index.name = "FECHA"
    # CA-HUAR-01: solo datos propios; la serie combinada (con relleno de CA-COLQ-01) la arma 00f
    # (Ilo: candidatas; la serie combinada se arma aparte)
    nombre = f"03_dataset_{est}_PM10_ar" + ("_propia" if est == "CA-HUAR-01" or "patron" in cfg else "")
    ds.to_pickle(os.path.join(wc.CARPETA_DATOS, f"{nombre}.pkl"))
    ds.to_csv(os.path.join(wc.CARPETA_DATOS, f"{nombre}.csv"), sep=";")
    print(f"\n{nombre}: {len(ds):,} días ({ds.index.min().date()} -> {ds.index.max().date()}), "
          f"PM10 válido: {ds['OBJETIVO'].notna().sum():,}")
    print(ds.drop(columns=["DEPARTAMENTO", "NOMBRE_PUNTO", "CONTAMINANTE"]).notna().mean().mul(100).round(1).to_string())
