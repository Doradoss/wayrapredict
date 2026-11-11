# -*- coding: utf-8 -*-
"""
WayraPredict - lectura de los datos crudos de alta resolución (datalogger Campbell CR1000,
exportaciones de base de datos y Excel), parametrizada por estación.

Solo LEE los archivos originales; nunca los modifica.
Formatos soportados (detectados automáticamente):
- TOA5 (Campbell): línea 1 = encabezado, líneas 2-3 = unidades y tipo de agregación.
- Texto delimitado (coma, punto y coma o tabulación), con coma o punto decimal.
- Texto con cada línea entre comillas y comillas internas duplicadas (p. ej. abril de 2020).
- Descargas del analizador Thermo 43i (líneas ';;' de cabecera, columnas por espacios).
- Excel (.xlsx), primera hoja, encabezado en la primera fila con fecha.
"""
import csv
import io
import os
import re

import pandas as pd

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
PALABRAS_ENCABEZADO = ("timestamp", "fecha", "date", "time", "hora")


def listar_archivos(carpeta_entrada: str) -> pd.DataFrame:
    """Tabla de archivos con año y mes tomados de <año>/<n-Mes>/."""
    filas = []
    for raiz, _, archivos in os.walk(carpeta_entrada):
        partes = os.path.relpath(raiz, carpeta_entrada).split(os.sep)
        if len(partes) < 2:
            continue
        m = re.match(r"(\d+)-(.+)", partes[1])
        mes = int(m.group(1)) if m else MESES.get(partes[1].lower())
        for nombre in sorted(archivos):
            filas.append({"anio": int(partes[0]), "mes": mes, "archivo": nombre,
                          "extension": os.path.splitext(nombre)[1].lower(),
                          "ruta": os.path.join(raiz, nombre)})
    return pd.DataFrame(filas).sort_values(["anio", "mes", "archivo"]).reset_index(drop=True)


def leer_texto(ruta: str):
    with open(ruta, "rb") as f:
        crudo = f.read()
    if crudo[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return crudo.decode("utf-16", errors="replace"), "utf-16"
    for cod in ("utf-8-sig", "utf-8"):
        try:
            return crudo.decode(cod), cod
        except UnicodeDecodeError:
            continue
    return crudo.decode("latin-1"), "latin-1"


def _separador(lineas) -> str:
    muestra = "\n".join(lineas[:30])
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;\t").delimiter
    except csv.Error:
        cuentas = {s: muestra.count(s) for s in (",", ";", "\t")}
        return max(cuentas, key=cuentas.get)


def _fila_encabezado(filas) -> int:
    for i, fila in enumerate(filas[:40]):
        celdas = [str(c).strip().strip('"').lower() for c in fila]
        if any(any(p in c for p in PALABRAS_ENCABEZADO) for c in celdas if c):
            return i
    return 0


def leer_archivo(ruta: str):
    """Devuelve (DataFrame con todas las columnas como texto, metadatos del formato)."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext in (".xlsx", ".xls"):
        crudo = pd.read_excel(ruta, sheet_name=0, header=None, dtype=str)
        enc = _fila_encabezado(crudo.head(40).fillna("").values.tolist())
        df = crudo.iloc[enc + 1:].reset_index(drop=True)
        df.columns = [str(c).strip() for c in crudo.iloc[enc]]
        return df, {"formato": "Excel", "codificacion": None, "separador": None,
                    "fila_encabezado": enc, "filas_omitidas": 0}

    texto, cod = leer_texto(ruta)
    lineas = texto.splitlines()
    meta = {"codificacion": cod, "filas_omitidas": 0}

    # Analizador Thermo 43i: cabecera con ';;' y columnas separadas por espacios/tabulaciones
    if any(l.strip().strip('"').startswith(";;") for l in lineas[:3]):
        datos = [l for l in lineas if not l.strip().strip('"').startswith(";;") and l.strip()]
        filas = [re.split(r"[\t ]+", l.strip()) for l in datos]
        filas = [[c for c in f if c != ""] for f in filas]
        enc = _fila_encabezado(filas)
        cols = filas[enc]
        cuerpo = [f[:len(cols)] for f in filas[enc + 1:] if len(f) >= len(cols)]
        df = pd.DataFrame(cuerpo, columns=cols)
        meta.update({"formato": "Analizador 43i", "separador": "espacios/tabulación",
                     "fila_encabezado": enc})
        return df, meta

    sep = _separador(lineas)
    filas = list(csv.reader(lineas[:40], delimiter=sep))
    # Líneas completas entre comillas (abril de 2020): la coma es a la vez separador y decimal,
    # así que las columnas son ambiguas. Se reconstruye desde DESCRIPCION_TRAMA_ORIGINAL (trama
    # del datalogger con punto decimal), cuyas posiciones se validan contra enero de 2020.
    if filas and len(filas[0]) == 1 and filas[0][0].count(",") > 2:
        df = leer_tramas(lineas)
        meta.update({"formato": "Texto con comillas envolventes (se lee la trama original)",
                     "separador": "coma (ambigua con la coma decimal)", "fila_encabezado": 0})
        return df, meta
    enc = _fila_encabezado(filas)
    toa5 = lineas[0].strip('"').startswith("TOA5")
    df = pd.read_csv(io.StringIO("\n".join(lineas)), sep=sep, header=enc, dtype=str,
                     engine="python", on_bad_lines="skip", keep_default_na=False,
                     na_values=["", "NAN", "NaN", "nan", "-", "NA"])
    if toa5:
        df = df.iloc[2:].reset_index(drop=True)  # unidades y tipo de agregación
        meta["filas_omitidas"] = 2
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [not c.startswith("Unnamed") or df[c].notna().any() for c in df.columns]]
    meta.update({"formato": "TOA5 (Campbell)" if toa5 else "Texto delimitado",
                 "separador": {",": "coma", ";": "punto y coma", "\t": "tabulación"}.get(sep, sep),
                 "fila_encabezado": enc})
    return df, meta


# Posiciones de la trama original del datalogger (2020), verificadas contra las columnas de
# enero de 2020, donde vienen ambas: id, modelo, fecha (MM_DD_AAAA), hora, PBAR, PP, TEMP, HR,
# WS, WD, 14 campos vacíos, SO2, estado, flujo, lámpara, temp. interna, voltaje PMT, temp. conv.
POSICIONES_TRAMA = {"FECHA_TRAMA": 2, "HORA_TRAMA": 3, "PBAR": 4, "PP": 5, "TEMP": 6, "HR": 7,
                    "WS": 8, "WD": 9, "SO2_CONC": 24, "SO2_ESTADO": 25, "SO2_FLOW": 26,
                    "SO2_LAMP_INT": 27, "SO2_INTERNAL_TEMP": 28, "SO2_PMT_VOLTAGE": 29,
                    "SO2_CONV_TEMP": 30}


def partir_trama(trama: str) -> dict:
    campos = [c.strip() for c in str(trama).split(",")]
    salida = {}
    for nombre, pos in POSICIONES_TRAMA.items():
        v = campos[pos] if pos < len(campos) else None
        salida[nombre] = None if v in (None, "", "NULL") else v
    return salida


def leer_tramas(lineas) -> pd.DataFrame:
    filas = []
    for l in lineas[1:]:
        m = re.search(r'""(\d+,[^",]+,\d{2}_\d{2}_\d{4},[^"]*)""', l)
        if m:
            filas.append(partir_trama(m.group(1)))
    df = pd.DataFrame(filas)
    df["FECHA_DATA_LOGGER_TIMESTAMP"] = (df["FECHA_TRAMA"].str.replace("_", "/") + " "
                                          + df["HORA_TRAMA"])
    return df.drop(columns=["FECHA_TRAMA", "HORA_TRAMA"])


# ------------------------------------------------------------------
# MAPEO DE VARIANTES DE COLUMNAS -> ESQUEMA ESTÁNDAR
# ------------------------------------------------------------------
# Columna de fecha-hora principal, en orden de preferencia (la primera que exista)
COLUMNAS_FECHA = ["date", "TIMESTAMP", "FECHA_DATA_LOGGER_TIMESTAMP"]
# Fecha y hora "locales" separadas (se comparan con la principal para la zona horaria)
PARES_FECHA_LOCAL = [("FECHA_DATA", "HORA_DATA"), ("FECHA_DATA_LOGER", "HORA_DATA_LOGER"),
                     ("Date", "Time")]
MAPEO = {
    # Contaminante (ppb según la documentación; se verifica contra el OEFA)
    "SO2_PPB": ["SO2_PPB", "SO2_CONC", "Conc_SO2_Avg", "Conc_SO2", "so2"],
    "SO2_ESTADO": ["SO2_ESTADO", "Status", "Flags"],
    # Meteorología
    "PBAR": ["PBAR", "PBAR_mmHH", "PBAR_mmHg", "BP_mmHg_Avg", "BP_hPA_Avg"],
    "PP": ["PP", "PP_mm", "Rain_mm_Tot"],
    "TEMP": ["TEMP", "TEMP_°C", "AirTC_Avg"],
    "HR": ["HR", "HR_%", "RH_Avg"],
    "WS": ["WS", "ws", "ws_m/s", "WS_ms_S_WVT"],
    "WD": ["WD", "wd", "wd_°", "WindDir_D1_WVT"],
    "WD_DESV": ["WindDir_SD1_WVT"],
    "RS": ["RS", "RS_w/m2"],
    # Estado del analizador de SO2
    "SO2_FLOW": ["SO2_FLOW", "Flow", "smplfl"],
    "SO2_LAMP_INT": ["SO2_LAMP_INT", "Lamp_int", "lmpi"],
    "SO2_LAMP_VOLTAGE": ["SO2_LAMP_VOLTAGE", "lmpv"],
    "SO2_INTERNAL_TEMP": ["SO2_INTERNAL_TEMP", "Internal_temp", "intt"],
    "SO2_CAMARA_TEMP": ["SO2_CHAMBER_TEMP", "React_temp", "VALOR_43I_IREACT_TEMP", "rctt"],
    "SO2_BENCH_TEMP": ["SO2_BENCH_TEMP"],
    "SO2_BENCH_PRESS": ["SO2_BENCH_PRESS"],
    "SO2_PRES_MUESTRA": ["pres"],
    "SO2_PMT_VOLTAGE": ["SO2_PMT_VOLTAGE", "Pmt_voltage", "pmtv"],
    "SO2_CONV_TEMP": ["SO2_CONV_TEMP"],
    "SO2_BACKGROUND": ["SO2_BACKGROUND"],
    "SO2_COEFFICIENT": ["SO2_COEFFICIENT"],
    # Cabina y equipo
    "CABINA_TEMP": ["CABINET_INT_TEMP", "Temperatura_Avg"],
    "CABINA_HR": ["CABINET_INT_HR", "Humedad_Avg"],
    "BATERIA_V": ["Batt_volt_Avg"],
    "EQUIPO_MET": ["EQUIPO_MET"],
    "EQUIPO_SO2": ["EQUIPO_SO2"],
    # Segundo canal (columnas con asterisco) y banderas de validación
    "SO2_PPB_2": ["SO2_PPB*"],
    "SO2_ESTADO_2": ["SO2_ESTADO*"],
    "BANDERA_SO2": ["B_SO2_PPB"],
    "BANDERA_MET": ["B_TEMP"],
}
COLUMNAS_TEXTO = {"SO2_ESTADO", "SO2_ESTADO_2", "BANDERA_SO2", "BANDERA_MET", "EQUIPO_MET",
                  "EQUIPO_SO2"}


def decimal_con_coma(df: pd.DataFrame) -> bool:
    muestra = df.head(500).astype(str)
    return bool(muestra.apply(lambda s: s.str.fullmatch(r"-?\d+,\d+").mean()).max() > 0.3)


def parsear_fecha(texto: pd.Series, anio: int, mes: int):
    """Convierte texto a fecha-hora. Como el orden día/mes varía entre archivos, se prueban
    ambas lecturas y se elige la que deja más registros dentro del mes de la carpeta.
    Devuelve (fechas sin zona, 'dia/mes' o 'mes/dia', tenia_sufijo_UTC)."""
    s = texto.astype(str).str.strip()
    con_utc = bool(s.str.endswith("UTC").mean() > 0.5)
    s = s.str.replace(r"\s*UTC$", "", regex=True)
    mejor = None
    for dayfirst in (False, True):
        f = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst, format="mixed")
        dentro = ((f.dt.year == anio) & (f.dt.month == mes)).mean()
        if mejor is None or dentro > mejor[0]:
            mejor = (dentro, f, "dia/mes" if dayfirst else "mes/dia")
    return mejor[1], mejor[2], con_utc


def estandarizar(df: pd.DataFrame, anio: int, mes: int):
    """Lleva un archivo leído al esquema estándar. Devuelve (DataFrame, detalle)."""
    coma = decimal_con_coma(df)
    salida = pd.DataFrame(index=df.index)
    detalle = {"decimal": "coma" if coma else "punto", "columnas_mapeadas": {}}

    # Fecha-hora principal
    col_fecha = next((c for c in COLUMNAS_FECHA if c in df.columns), None)
    if col_fecha is not None:
        texto = df[col_fecha]
    else:  # solo fecha y hora separadas (analizador 43i)
        cf, ch = next(p for p in PARES_FECHA_LOCAL if p[0] in df.columns and p[1] in df.columns)
        texto, col_fecha = df[cf].astype(str) + " " + df[ch].astype(str), f"{cf}+{ch}"
    salida["FECHA_HORA"], orden, con_utc = parsear_fecha(texto, anio, mes)
    detalle.update({"columna_fecha": col_fecha, "orden_fecha": orden, "sufijo_UTC": con_utc})

    # Fecha y hora "locales" separadas: diferencia con la principal (horas)
    for cf, ch in PARES_FECHA_LOCAL:
        if cf in df.columns and ch in df.columns and f"{cf}+{ch}" != col_fecha:
            loc, orden_loc, _ = parsear_fecha(df[cf].astype(str) + " " + df[ch].astype(str), anio, mes)
            dif = (salida["FECHA_HORA"] - loc).dt.total_seconds().div(3600)
            detalle.update({"columna_fecha_local": f"{cf}+{ch}", "orden_fecha_local": orden_loc,
                            "dif_principal_menos_local_h": float(dif.median())})
            break

    for estandar, variantes in MAPEO.items():
        col = next((v for v in variantes if v in df.columns), None)
        if col is None:
            continue
        detalle["columnas_mapeadas"][estandar] = col
        s = df[col]
        if estandar in COLUMNAS_TEXTO:
            salida[estandar] = s.astype("string").str.strip()
        else:
            s = s.astype("string").str.strip()
            if coma:
                s = s.str.replace(",", ".", regex=False)
            salida[estandar] = pd.to_numeric(s, errors="coerce").astype("float64")
    detalle["columnas_sin_mapear"] = [c for c in df.columns if c not in
                                      set(detalle["columnas_mapeadas"].values()) | {col_fecha}]
    return salida, detalle
