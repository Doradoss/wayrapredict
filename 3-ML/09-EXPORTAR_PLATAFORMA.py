# %% [markdown]
# # 09 - Exportación de datos para la plataforma web (esquema v1.2)
#
# Genera un CSV por tabla en `plataforma/` (separador `;`, UTF-8) con los nombres de columna del esquema
# `esquema_wayrapredict.sql`. **No cambia ningún modelo, selección ni resultado.**
#
# Convención de claves en los CSV (las traduce `10-CARGAR_BD.py` a los id reales):
# - columnas de clave foránea: `id_estacion` = código de la estación (p. ej. CA-CC-01), `id_variable` = código de
#   la variable (SO2, PM10, TEMPERATURA...), `id_categoria` = nombre de la categoría INCA;
# - `id_modelo` = clave local "estación|variable|versión"; `id_ejecucion` = número de ejecución de la carga manual
#   (1, 2, 3; se insertan con ese id);
# - los id autoincrementales propios (`id_medicion`, `id_prediccion`) no se exportan.
#
# Modelos (instrucciones_8): CA-CC-01 y CA-HUAR-01 -> v1 = principal (respaldo), v2 = EF2 del experimento 2
# (vigente); CA-ILO-02 -> v1 = principal (vigente). No se carga ninguna predicción de PM2.5.
# Requiere `09a-PRONOSTICO_ULTIMO_DATO.py` (pronóstico desde el último dato); si su salida falta, se ejecuta aquí.

# %%
import json
import os
import subprocess
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
import wayra_comun as wc

PLAT = os.path.join(wc.RAIZ, "plataforma")
DIR_INT = os.path.join(PLAT, "intermedio")
DIR_BLOB_MET = os.path.join(PLAT, "blob", "pronosticos_meteo")
EXP1 = os.path.join(wc.RAIZ, "experimento_mejoras")
EXP2 = os.path.join(wc.RAIZ, "experimento_2")
for c in (PLAT, DIR_INT, DIR_BLOB_MET):
    os.makedirs(c, exist_ok=True)
H = wc.HORIZONTES
AHORA = datetime.now().replace(microsecond=0)

# Catálogo de variables del esquema (código BD -> columna del dataset diario) y umbrales para el INCA
VAR_METEO = {"TEMPERATURA": "TEMPERATURA", "HUMEDAD_RELATIVA": "HUMEDAD_RELATIVA", "VELOCIDAD_VIENTO": "VELOCIDAD_VIENTO",
             "PRESION_BAROMETRICA": "PRESION_BAROMETRICA", "PRECIPITACION": "PRECIPITACION"}
ECA_BD = {"SO2": 250, "PM10": 100, "PM2.5": 50}
VUEC_BD = {"SO2": None, "PM10": None, "PM2.5": None}    # NULL en el esquema: todo lo > INCA 100 es "Mala"

# Estaciones: coordenadas UTM WGS84 corregidas (experimento 1: CA-HUAR-01 zona 18, no 19 como en 1A.csv);
# altitud de 1A.csv (CA-CC-01, CA-HUAR-01) y del informe REAS-012-2024 (CA-ILO-02)
ESTACIONES = {
    "CA-CC-01": {"clave": "CA-CC-01_DIOXIDO_AZUFRE", "fuente": "combinada", "variable": "SO2", "vigente": "v2",
                 "nombre": "La Oroya", "departamento": "Junín", "provincia": "Yauli", "distrito": "La Oroya",
                 "este": 401757, "norte": 8726374, "zona_utm": 18, "altitud": 3728, "col_alerta": "limite_alerta"},
    "CA-HUAR-01": {"clave": "CA-HUAR-01_PM10", "fuente": "pasco_moquegua", "variable": "PM10", "vigente": "v2",
                   "nombre": "Huaraucaca", "departamento": "Pasco", "provincia": "Pasco", "distrito": "Tinyahuarco",
                   "este": 358735, "norte": 8806535, "zona_utm": 18, "altitud": 4166, "col_alerta": "limite_alerta_movil"},
    "CA-ILO-02": {"clave": "CA-ILO-02_PM10", "fuente": "pasco_moquegua", "variable": "PM10", "vigente": "v2",
                  "nombre": "Ilo-Pacocha", "departamento": "Moquegua", "provincia": "Ilo", "distrito": "Pacocha",
                  "este": 251618, "norte": 8051342, "zona_utm": 19, "altitud": 30, "col_alerta": "limite_alerta_movil"},
}
EJECUCIONES = {1: "Carga manual: mediciones diarias históricas",
               2: "Carga manual: predicciones pasadas (h = 1, periodo de prueba)",
               3: "Carga manual: pronóstico a 1-3 días desde el último dato de cada estación",
               4: "Carga manual: PM10 de Huaraucaca estimado con Colquijirca ajustada (estacion_vecina)",
               5: "Carga manual: meteorología completada con reanálisis (servicio_meteo)",
               6: "Carga manual: meteorología pronosticada de los días objetivo (pronostico_meteo)"}


def clave_modelo(est, version):
    return f"{est}|{ESTACIONES[est]['variable']}|{version}"


def categoria(valor, variable):
    inca = round(valor, 3) / ECA_BD[variable] * 100
    if inca <= 50:
        return "Buena"
    if inca <= 100:
        return "Moderada"
    vuec = VUEC_BD[variable]
    return "Umbral de cuidado" if vuec is not None and valor > vuec else "Mala"


def guardar_csv(df, nombre):
    df.to_csv(os.path.join(PLAT, f"{nombre}.csv"), sep=";", index=False, encoding="utf-8")
    print(f"   {nombre}.csv: {len(df)} filas")


# %% [markdown]
# ## 0. Pronóstico desde el último dato (09a, una vez por fuente)

# %%
for fuente in ("combinada", "pasco_moquegua"):
    if not os.path.exists(os.path.join(DIR_INT, f"09a_futuro_{fuente}.pkl")):
        print(f"Ejecutando 09a con WAYRA_FUENTE={fuente} ...")
        subprocess.run([sys.executable, "-u", "-X", "utf8", "09a-PRONOSTICO_ULTIMO_DATO.py"], check=True,
                       env={**os.environ, "WAYRA_FUENTE": fuente, "MPLBACKEND": "Agg"})
futuro = {**pd.read_pickle(os.path.join(DIR_INT, "09a_futuro_combinada.pkl")),
          **pd.read_pickle(os.path.join(DIR_INT, "09a_futuro_pasco_moquegua.pkl"))}

# %% [markdown]
# ## 1. estacion y medicion_diaria
#
# Esquema v1.3: cada valor lleva `origen` = 'estacion' (medido), 'estacion_vecina' (PM10 de Huaraucaca estimado
# con Colquijirca ajustada, de la serie combinada oficial, solo en días sin dato propio), 'servicio_meteo'
# (meteorología completada con reanálisis, 1b) o 'pronostico_meteo' (meteorología pronosticada de los días
# objetivo, 3b). La fecha de referencia de v_alerta solo usa origen = 'estacion'.
# Mediciones de la estación: todo el histórico de cada serie tal como entra a los modelos (La Oroya: OEFA
# 2018-2019 + alta resolución; Ilo-02: desde junio de 2022, como se decidió en instrucciones_4), más la dirección
# del viento (promedio vectorial diario: atan2 de las componentes medias del vector unitario de dirección, las
# mismas VIENTO_SIN / VIENTO_COS de los datasets). Se omiten valores meteorológicos imposibles (no se cambian los
# datasets de los modelos):
#   - día con temperatura = 0 y viento = 0 exactos a la vez (registro vacío del logger): temperatura, viento,
#     dirección y precipitación de ese día;
#   - viento medio diario = 0 exacto (sensor detenido): viento y dirección;
#   - dirección = 0° exacto todo el día (seno 0, coseno 1);
#   - presión a más de 20 mmHg de la mediana de la estación (p. ej. ~752 mmHg en La Oroya, mar 2021).

# %%
estacion = pd.DataFrame([{"codigo": e, "nombre": c["nombre"], "departamento": c["departamento"], "provincia": c["provincia"],
                          "distrito": c["distrito"], "este": c["este"], "norte": c["norte"], "zona_utm": c["zona_utm"],
                          "altitud": c["altitud"], "activa": True} for e, c in ESTACIONES.items()])
def direccion(sin, cos):
    """Dirección media (°, 0-360) a partir de las componentes medias del vector de dirección."""
    return np.mod(np.degrees(np.arctan2(sin, cos)), 360)


def a_largo(tabla, est, origen, ejecucion):
    largo = tabla.stack().dropna().rename("valor").reset_index()
    largo.columns = ["fecha", "id_variable", "valor"]
    largo.insert(0, "id_estacion", est)
    return largo.assign(origen=origen, id_ejecucion=ejecucion)


filas, omitidos, datasets, met_valida = [], [], {}, {}
for est, c in ESTACIONES.items():
    ds = wc.cargar_dataset(c["clave"], c["fuente"])
    datasets[est] = ds
    obj = ds["OBJETIVO"].where(ds["RELLENO"] != 1) if "RELLENO" in ds else ds["OBJETIVO"]
    met = ds[list(VAR_METEO.values()) + ["VIENTO_SIN", "VIENTO_COS"]].copy()
    vacio = (ds["TEMPERATURA"] == 0) & (ds["VELOCIDAD_VIENTO"] == 0)
    dir_cero = (ds["VIENTO_SIN"] == 0) & (ds["VIENTO_COS"] == 1)       # 0° exacto todo el día: registro vacío
    reglas = {"temperatura y viento = 0 (registro vacío)": (vacio, ["TEMPERATURA", "VELOCIDAD_VIENTO", "PRECIPITACION",
                                                                     "VIENTO_SIN", "VIENTO_COS"]),
              "viento medio = 0": (ds["VELOCIDAD_VIENTO"] == 0, ["VELOCIDAD_VIENTO", "VIENTO_SIN", "VIENTO_COS"]),
              "dirección = 0° exacto todo el día": (dir_cero, ["VIENTO_SIN", "VIENTO_COS"]),
              "presión fuera de ±20 mmHg de la mediana": ((ds["PRESION_BAROMETRICA"] - ds["PRESION_BAROMETRICA"].median()).abs() > 20,
                                                          ["PRESION_BAROMETRICA"])}
    for regla, (m, cols) in reglas.items():
        for col in cols:
            n = int((m & met[col].notna()).sum())
            if n:
                omitidos.append({"estacion": est, "variable": col, "regla": regla, "dias_omitidos": n})
            met.loc[m, col] = np.nan
    met["DIRECCION_VIENTO"] = direccion(met["VIENTO_SIN"], met["VIENTO_COS"])
    met_valida[est] = met
    tabla = pd.concat([obj.rename(c["variable"]),
                       met[list(VAR_METEO.values()) + ["DIRECCION_VIENTO"]].rename(columns={v: k for k, v in VAR_METEO.items()})], axis=1)
    filas.append(a_largo(tabla, est, "estacion", 1))
    # Huaraucaca: días rellenados con Colquijirca ajustada (serie combinada oficial), solo sin dato propio
    if "RELLENO" in ds:
        vec = ds["OBJETIVO"].where((ds["RELLENO"] == 1) & obj.isna())
        filas.append(a_largo(vec.rename(c["variable"]).to_frame(), est, "estacion_vecina", 4))
medicion = pd.concat(filas, ignore_index=True)
fecha_ref = {est: pd.Timestamp(medicion.loc[(medicion["id_estacion"] == est) & (medicion["id_variable"] == c["variable"])
                                            & (medicion["origen"] == "estacion"), "fecha"].max())
             for est, c in ESTACIONES.items()}
print("Valores meteorológicos omitidos (inválidos):")
print(pd.DataFrame(omitidos).to_string(index=False))
print("Fecha de referencia (último día con medición propia del contaminante):", {e: str(f.date()) for e, f in fecha_ref.items()})

# %% [markdown]
# ## 1b. Meteorología faltante o inválida completada con reanálisis (solo para la plataforma)
#
# Open-Meteo Historical Weather API (reanálisis ERA5/ERA5-Land, `archive-api`), por coordenadas de la estación,
# agregada por día en hora local igual que la estación (medias; precipitación sumada; dirección como promedio de
# las componentes del vector unitario; presión en hPa -> mmHg). Para cada estación y variable:
# r y diferencia media (estación - reanálisis) en los días válidos comunes; si r >= 0,6 se completan los días sin
# dato válido de la estación (entre el primer día de medición del contaminante y la fecha de referencia) con el
# ajuste lineal estación = a + b · reanálisis estimado en esos días comunes. La dirección del viento se completa
# si las dos componentes (seno y coseno) cumplen r >= 0,6. Origen = 'servicio_meteo'. No cambia ningún modelo.

# %%
import requests

DIR_REAN = os.path.join(DIR_INT, "reanalisis")
os.makedirs(DIR_REAN, exist_ok=True)
COORD = {"CA-CC-01": (-11.51995, -75.90088), "CA-HUAR-01": (-10.79368, -76.29212), "CA-ILO-02": (-17.61076, -71.34065)}
VARS_REAN = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m", "precipitation", "surface_pressure"]
R_MIN = 0.6


def reanalisis(est, inicio, fin):
    lat, lon = COORD[est]
    ruta = os.path.join(DIR_REAN, f"era5_{est}_{inicio.date()}_{fin.date()}.json")
    if not os.path.exists(ruta):
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=300, params={
            "latitude": lat, "longitude": lon, "start_date": str(inicio.date()), "end_date": str(fin.date()),
            "hourly": ",".join(VARS_REAN), "wind_speed_unit": "ms", "timezone": "America/Lima"})
        r.raise_for_status()
        with open(ruta, "w", encoding="utf-8") as fj:
            json.dump(r.json(), fj)
    d = json.load(open(ruta, encoding="utf-8"))
    h = pd.DataFrame(d["hourly"])
    h["time"] = pd.to_datetime(h["time"])
    h = h.set_index("time").apply(pd.to_numeric, errors="coerce")
    g = h.groupby(h.index.floor("D"))
    rad = np.deg2rad(h["wind_direction_10m"])
    out = pd.DataFrame({"TEMPERATURA": g["temperature_2m"].mean(), "HUMEDAD_RELATIVA": g["relative_humidity_2m"].mean(),
                        "VELOCIDAD_VIENTO": g["wind_speed_10m"].mean(), "PRECIPITACION": g["precipitation"].sum(min_count=20),
                        "PRESION_BAROMETRICA": g["surface_pressure"].mean() * 0.750062,
                        "VIENTO_SIN": np.sin(rad).groupby(h.index.floor("D")).mean(),
                        "VIENTO_COS": np.cos(rad).groupby(h.index.floor("D")).mean()})
    return out.where(g["temperature_2m"].count() >= 20), d.get("elevation")


coincidencia, filas_rean = [], []
for est, c in ESTACIONES.items():
    met = met_valida[est]
    inicio = medicion.loc[(medicion["id_estacion"] == est) & (medicion["id_variable"] == c["variable"]), "fecha"].min()
    rango = pd.date_range(inicio, fecha_ref[est])
    rean, elev = reanalisis(est, rango[0], rango[-1])
    rean = rean.reindex(rango)
    completado = pd.DataFrame(index=rango)
    ajustes = {}
    for var in list(VAR_METEO) + ["VIENTO_SIN", "VIENTO_COS"]:
        y, x = met[var].reindex(rango), rean[var]
        ok = y.notna() & x.notna()
        r = float(np.corrcoef(y[ok], x[ok])[0, 1]) if ok.sum() > 30 and y[ok].std() > 0 else np.nan
        b, a = np.polyfit(x[ok], y[ok], 1) if ok.sum() > 30 else (np.nan, np.nan)
        falta = y.isna() & x.notna()
        ajustes[var] = (r, a, b, falta)
        coincidencia.append({"estacion": est, "variable": var, "dias_comunes": int(ok.sum()), "r": round(r, 3),
                             "dif_media_estacion_menos_reanalisis": round(float((y[ok] - x[ok]).mean()), 3),
                             "ajuste_a": round(a, 4), "ajuste_b": round(b, 4), "cumple_r>=0,6": bool(r >= R_MIN),
                             "dias_sin_dato_valido": int(y.isna().sum()),
                             "dias_completados": int(falta.sum()) if r >= R_MIN else 0,
                             "elevacion_celda_reanalisis_m": elev})
    for var in VAR_METEO:
        r, a, b, falta = ajustes[var]
        if r >= R_MIN:
            v = a + b * rean.loc[falta, var]
            if var in ("PRECIPITACION", "VELOCIDAD_VIENTO"):
                v = v.clip(lower=0)
            if var == "HUMEDAD_RELATIVA":
                v = v.clip(0, 100)
            completado.loc[falta, var] = v
    (rs, as_, bs, fs), (rc, ac, bc, fc) = ajustes["VIENTO_SIN"], ajustes["VIENTO_COS"]
    if rs >= R_MIN and rc >= R_MIN:
        falta = met["DIRECCION_VIENTO"].reindex(rango).isna() & rean["VIENTO_SIN"].notna()
        completado.loc[falta, "DIRECCION_VIENTO"] = direccion(as_ + bs * rean.loc[falta, "VIENTO_SIN"],
                                                              ac + bc * rean.loc[falta, "VIENTO_COS"])
    coincidencia.append({"estacion": est, "variable": "DIRECCION_VIENTO (seno y coseno)",
                         "cumple_r>=0,6": bool(rs >= R_MIN and rc >= R_MIN),
                         "dias_completados": int(completado.get("DIRECCION_VIENTO", pd.Series(dtype=float)).notna().sum())})
    filas_rean.append(a_largo(completado, est, "servicio_meteo", 5))
coincidencia = pd.DataFrame(coincidencia)
medicion = pd.concat([medicion] + filas_rean, ignore_index=True)
print("Coincidencia estación vs reanálisis (días válidos comunes):")
print(coincidencia.to_string(index=False))

# %% [markdown]
# ## 2. Predicciones de v1 y v2 (EF2) y métricas de la prueba a h = 1
#
# v2 = EF2 del experimento 2 con los pesos guardados en `experimento_2/resultados/F4_versiones.json` (elegidos en
# validación). Intervalo del 80 %: el del modelo principal desplazado en escala log, igual que en el experimento.

# %%
def componente(est, nombre):
    if nombre.startswith("x1_"):
        ruta = os.path.join(EXP1, "modelos", est, nombre[3:] + ".pkl")
    else:
        ruta = os.path.join(EXP2, "modelos", est, nombre[3:] + ".pkl")
    return pd.read_pickle(ruta), ruta


versiones = json.load(open(os.path.join(EXP2, "resultados", "F4_versiones.json"), encoding="utf-8"))
pred_v, info_modelo, meteo_usada = {}, {}, {}
for est, c in ESTACIONES.items():
    ruta_sel = os.path.join(wc.CARPETA_DATOS, f"fuente_{c['fuente']}", f"08_hibrido_seleccionado_walkforward_{c['clave']}.pkl")
    sel = pd.read_pickle(ruta_sel)
    sel = sel[sel["particion"].isin(["val", "test", "extra"])]
    v1 = sel[["origen", "horizonte", "fecha_objetivo", "particion", "observado", "valor", "limite_inferior", "limite_superior"]].copy()
    pred_v[(est, "v1")] = v1
    info_modelo[(est, "v1")] = {"fecha_entrenamiento": datetime.fromtimestamp(os.path.getmtime(ruta_sel)).replace(microsecond=0),
                                "descripcion": "modelo principal (evaluación principal)"}
    if c["vigente"] != "v2":
        continue
    pesos = {int(h): w for h, w in versiones[c["clave"]]["pesos_EF2"].items()}
    tab = v1.set_index(["origen", "horizonte"])
    partes, mtimes, met = [], [], {h: set() for h in H}
    for h in H:
        g = tab.xs(h, level="horizonte", drop_level=False).copy()
        valor = pd.Series(0.0, index=g.index)
        for n, w in pesos[h].items():
            if w == 0:
                continue
            if n == "Principal":
                x = g["valor"]
            else:
                d, ruta = componente(est, n)
                mtimes.append(os.path.getmtime(ruta))
                x = d["pred"].set_index(["origen", "horizonte"])["valor"].reindex(g.index)
                fm = d["info"].get("fuente_meteo") or (n.replace("x2_E9m_", "") if n.startswith("x2_E9m_") else None)
                if n == "x1_E9_meteo_pronosticada":
                    fm = "best_match"
                if fm:
                    met[h] |= set(["best_match", "gfs_seamless", "jma_seamless", "icon_seamless", "ecmwf_ifs025"]) if fm == "promedio" else {fm}
            valor = valor + w * x
        d_log = np.log1p(valor.clip(lower=0)) - np.log1p(g["valor"].clip(lower=0))
        g["limite_inferior"] = np.expm1(np.log1p(g["limite_inferior"]) + d_log)
        g["limite_superior"] = np.expm1(np.log1p(g["limite_superior"]) + d_log)
        g["valor"] = valor
        partes.append(g)
    pred_v[(est, "v2")] = pd.concat(partes).reset_index()
    meteo_usada[est] = met
    info_modelo[(est, "v2")] = {"fecha_entrenamiento": datetime.fromtimestamp(max(mtimes)).replace(microsecond=0),
                                "descripcion": f"EF2 del experimento 2; pesos por horizonte: {pesos}"}

# Métricas de la prueba a h = 1 (días observados; Huaraucaca: solo días propios -> la prueba es 100 % propia)
filas_modelo = []
for (est, ver), p in pred_v.items():
    c = ESTACIONES[est]
    ds = datasets[est]
    g = p[(p["particion"] == "test") & (p["horizonte"] == 1)].copy()
    if "RELLENO" in ds:
        g = g[~g["fecha_objetivo"].map(ds["RELLENO"]).eq(1)]
    g = g.dropna(subset=["observado", "valor"])
    mt_ = wc.metricas_regresion(g["observado"], g["valor"])
    info_modelo[(est, ver)]["n_test_h1"] = mt_["n"]
    filas_modelo.append({"id_modelo": clave_modelo(est, ver), "id_estacion": est, "id_variable": c["variable"], "version": ver,
                         "ruta_blob": f"modelos/{est}/{ver}/", "fecha_entrenamiento": info_modelo[(est, ver)]["fecha_entrenamiento"],
                         "rmse": round(mt_["RMSE"], 4), "mae": round(mt_["MAE"], 4), "r2": round(mt_["R2"], 4),
                         "vigente": ver == c["vigente"]})
modelo = pd.DataFrame(filas_modelo)
print(modelo.assign(n_test_h1=[info_modelo[(r.id_estacion, r.version)]["n_test_h1"] for r in modelo.itertuples()]).to_string(index=False))

# %% [markdown]
# ## 3. Tabla prediccion
# a) Predicciones pasadas: h = 1 del modelo vigente con fecha objetivo en la prueba y hasta la fecha de referencia
#    (ejecución 2). b) Pronóstico a 1-3 días desde el último dato (ejecución 3): modelo vigente; si la v2 no está
#    disponible en un horizonte, se usa v1 y la predicción se asigna a v1.

# %%
filas_pred, origen_futuro = [], []
for est, c in ESTACIONES.items():
    ver = c["vigente"]
    p = pred_v[(est, ver)]
    ini_test = pd.Timestamp(wc.SERIES_POR_FUENTE[c["fuente"]][c["clave"]]["inicio_test"])
    a = p[(p["horizonte"] == 1) & (p["fecha_objetivo"] >= ini_test) & (p["fecha_objetivo"] <= fecha_ref[est])].dropna(subset=["valor"])
    filas_pred.append(a.assign(id_modelo=clave_modelo(est, ver), id_ejecucion=2))
    # b) desde el último dato
    f = futuro[c["clave"]]
    t0 = f["ultimo_dato"]
    assert t0 == fecha_ref[est], f"{est}: el último dato de 09a ({t0}) no coincide con la fecha de referencia"
    for h in H:
        usado, fila = None, None
        if ver == "v2":
            r2 = f["v2"][f["v2"]["horizonte"] == h] if f.get("v2") is not None else None
            if r2 is not None and r2["valor"].notna().any():     # regenerado en 09a (Pasco)
                fila, usado = r2.iloc[0], "v2 (09a)"
            else:                                              # guardado en los componentes (Junín, Moquegua)
                g = p[(p["origen"] == t0) & (p["horizonte"] == h)].dropna(subset=["valor"])
                if len(g):
                    fila, usado = g.iloc[0], "v2 (componentes guardados)"
        if fila is None:
            fila = f["v1"][f["v1"]["horizonte"] == h].iloc[0]
            usado = "v1" + (" (v2 no disponible)" if ver == "v2" else "") + f" ({fila['fuente']})"
        version = "v2" if usado.startswith("v2") else "v1"
        filas_pred.append(pd.DataFrame([{"fecha_objetivo": fila["fecha_objetivo"], "valor": fila["valor"],
                                         "limite_inferior": fila["limite_inferior"], "limite_superior": fila["limite_superior"],
                                         "id_modelo": clave_modelo(est, version), "id_ejecucion": 3}]))
        origen_futuro.append({"estacion": est, "origen": t0.date(), "horizonte": h, "fecha_objetivo": fila["fecha_objetivo"].date(),
                              "modelo": version, "detalle": usado, "valor": round(float(fila["valor"]), 3)})
prediccion = pd.concat(filas_pred, ignore_index=True)
for col in ("valor", "limite_inferior", "limite_superior"):
    prediccion[col] = prediccion[col].astype(float).round(3)
prediccion["id_categoria"] = [categoria(v, m.split("|")[1]) for v, m in zip(prediccion["valor"], prediccion["id_modelo"])]
prediccion["fecha_objetivo"] = pd.to_datetime(prediccion["fecha_objetivo"]).dt.date
prediccion["verificado"] = False
prediccion["verificado_por"] = None
prediccion["fecha_verificacion"] = None
prediccion = prediccion[["id_modelo", "id_ejecucion", "fecha_objetivo", "valor", "limite_inferior", "limite_superior",
                         "id_categoria", "verificado", "verificado_por", "fecha_verificacion"]]
assert not prediccion.duplicated(["id_ejecucion", "id_modelo", "fecha_objetivo"]).any(), "violaría UNIQUE de prediccion"
print(pd.DataFrame(origen_futuro).to_string(index=False))
print(prediccion.groupby(["id_modelo", "id_ejecucion", "id_categoria"]).size().unstack(fill_value=0))

# %% [markdown]
# ## 3b. Meteorología PRONOSTICADA de los días objetivo del pronóstico a 1-3 días (origen 'pronostico_meteo')
#
# Para el tooltip del dashboard. Previous Runs emitido el día de origen (desfase = horizonte). Por horizonte se
# promedian los modelos meteorológicos con los pesos que tienen en la v2 (EF2; "promedio" = media de los cinco
# modelos). Si el pronóstico de ese horizonte no usa meteorología (Junín h = 3, generado con v1) o la estación usa
# v1 (Moquegua), se usa la fuente elegida en validación en el experimento 2 (E9opt: Junín ICON, Pasco y Moquegua
# GFS). Variables: temperatura, humedad, velocidad y dirección del viento y precipitación (Previous Runs no se
# descargó con presión).

# %%
TODOS_MET = ["best_match", "gfs_seamless", "jma_seamless", "icon_seamless", "ecmwf_ifs025"]
DIR_MET_FUT = os.path.join(DIR_INT, "meteo_futuro")


def pr_dia(est, modelo, f, lag, datos):
    """Fila diaria de Previous Runs (previous_day{lag}) para el día f; descarga lo que falte (caché)."""
    fila = datos[modelo]["pr"][lag].reindex([f]).iloc[0] if datos[modelo]["pr"][lag] is not None else None
    if fila is not None and fila.notna().any():
        return fila
    a = str(f.date())
    ruta = os.path.join(DIR_MET_FUT, f"pr{lag}_{modelo}_{est}_{a}_{a}.json")
    if not os.path.exists(ruta):
        lat, lon = COORD[est]
        params = {"latitude": lat, "longitude": lon, "timezone": "America/Lima", "start_date": a, "end_date": a,
                  "hourly": ",".join(f"{v}_previous_day{lag}" for v in ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                                                                         "wind_direction_10m", "precipitation", "cloud_cover"])}
        if modelo != "best_match":
            params["models"] = modelo
        r = requests.get("https://previous-runs-api.open-meteo.com/v1/forecast", params=params, timeout=120)
        r.raise_for_status()
        with open(ruta, "w", encoding="utf-8") as fj:
            json.dump(r.json(), fj)
    h = pd.DataFrame(json.load(open(ruta, encoding="utf-8"))["hourly"])
    h = h.set_index(pd.to_datetime(h.pop("time"))).apply(pd.to_numeric, errors="coerce")
    s = lambda n: h[f"{n}_previous_day{lag}"]
    rad = np.deg2rad(s("wind_direction_10m"))
    ok = s("temperature_2m").count() >= 20
    return pd.Series({"temp": s("temperature_2m").mean(), "hr": s("relative_humidity_2m").mean(),
                      "viento": s("wind_speed_10m").mean() / 3.6, "viento_sin": np.sin(rad).mean(),
                      "viento_cos": np.cos(rad).mean(), "precip": s("precipitation").sum(min_count=20)}) * (1.0 if ok else np.nan)


def pesos_meteo(est, h, version):
    """Peso de cada modelo meteorológico en el pronóstico de ese horizonte (normalizados)."""
    w = {}
    clave = ESTACIONES[est]["clave"]
    if version == "v2":
        for n, x in versiones[clave]["pesos_EF2"][str(h)].items():
            if x == 0 or n == "Principal":
                continue
            d, _ = componente(est, n)
            fm = d["info"].get("fuente_meteo") or (n.replace("x2_E9m_", "") if n.startswith("x2_E9m_") else None)
            fm = "best_match" if n == "x1_E9_meteo_pronosticada" else fm
            for m in (TODOS_MET if fm == "promedio" else [fm] if fm else []):
                w[m] = w.get(m, 0) + x / (len(TODOS_MET) if fm == "promedio" else 1)
    if not w:      # sin meteorología en ese horizonte: fuente elegida en validación (E9opt del experimento 2)
        w = {pd.read_pickle(os.path.join(EXP2, "modelos", est, "E9opt.pkl"))["info"]["fuente_meteo"]: 1.0}
    tot = sum(w.values())
    return {m: x / tot for m, x in w.items()}


filas_pm, control_pm = [], []
for o in origen_futuro:
    est, h, f = o["estacion"], o["horizonte"], pd.Timestamp(o["fecha_objetivo"])
    ruta_ext = os.path.join(DIR_INT, f"{est}_meteo_multimodelo_extendido.pkl")
    datos = pd.read_pickle(ruta_ext if os.path.exists(ruta_ext) else os.path.join(EXP2, "datos_externos", f"{est}_meteo_multimodelo.pkl"))
    w = pesos_meteo(est, h, o["modelo"])
    vals = pd.DataFrame({m: pr_dia(est, m, f, h, datos) for m in w}).T
    peso = pd.Series(w).reindex(vals.index)
    prom = {c: float((vals[c] * peso).sum() / peso[vals[c].notna()].sum()) if vals[c].notna().any() else np.nan for c in vals}
    fila = {"TEMPERATURA": prom["temp"], "HUMEDAD_RELATIVA": prom["hr"], "VELOCIDAD_VIENTO": prom["viento"],
            "PRECIPITACION": prom["precip"], "DIRECCION_VIENTO": direccion(prom["viento_sin"], prom["viento_cos"])}
    for var, v in fila.items():
        if pd.notna(v):
            filas_pm.append({"id_estacion": est, "fecha": f, "id_variable": var, "valor": v, "origen": "pronostico_meteo",
                             "id_ejecucion": 6})
    control_pm.append({"estacion": est, "fecha_objetivo": f.date(), "horizonte": h, "fecha_emision": o["origen"],
                       "modelos_y_pesos": json.dumps({m: round(x, 3) for m, x in w.items()}),
                       **{k: round(v, 3) for k, v in fila.items()}})
medicion = pd.concat([medicion, pd.DataFrame(filas_pm)], ignore_index=True)
print(pd.DataFrame(control_pm).to_string(index=False))

# formato final de medicion_diaria
medicion["fecha"] = pd.to_datetime(medicion["fecha"]).dt.date
medicion["valor"] = medicion["valor"].astype(float).round(3)
medicion["id_ejecucion"] = medicion["id_ejecucion"].astype(int)
medicion = medicion[["id_estacion", "id_variable", "id_ejecucion", "fecha", "valor", "origen"]]
assert not medicion.duplicated(["id_estacion", "id_variable", "fecha"]).any(), "violaría UNIQUE de medicion_diaria"
ref_final = {e: medicion[(medicion["id_estacion"] == e) & (medicion["id_variable"] == c["variable"])
                         & (medicion["origen"] == "estacion")]["fecha"].max() for e, c in ESTACIONES.items()}
assert all(pd.Timestamp(ref_final[e]) == fecha_ref[e] for e in ESTACIONES), "la fecha de referencia cambió"
print(medicion.groupby(["id_estacion", "origen"]).size().unstack(fill_value=0))

# %% [markdown]
# ## 4. ejecucion_proceso y pronósticos meteorológicos de la v2 (JSON para Blob Storage)
#
# El esquema no tiene columna de tipo o descripción en ejecucion_proceso: las ejecuciones 1-3 son la carga manual
# (descripción en `plataforma/LEEME.md`), estado "completada", sin mensaje de error.
# Pronósticos meteorológicos: un JSON por estación y fecha de emisión (= fecha de origen) con los valores diarios
# de Previous Runs (desfase 1-3 días) de cada modelo que usa la v2, tal como entraron al modelo.

# %%
ejecucion = pd.DataFrame([{"id_ejecucion": i, "fecha_inicio": AHORA, "fecha_fin": AHORA, "estado": "completada",
                           "mensaje_error": None} for i in EJECUCIONES])
n_json = {}
for est, met in meteo_usada.items():
    c = ESTACIONES[est]
    ruta_ext = os.path.join(DIR_INT, f"{est}_meteo_multimodelo_extendido.pkl")
    datos = pd.read_pickle(ruta_ext if os.path.exists(ruta_ext) else os.path.join(EXP2, "datos_externos", f"{est}_meteo_multimodelo.pkl"))
    modelos_met = sorted(set().union(*met.values()))
    p2 = prediccion[prediccion["id_modelo"] == clave_modelo(est, "v2")]
    origenes = sorted({pd.Timestamp(f) - pd.Timedelta(days=1) for f in p2[p2["id_ejecucion"] == 2]["fecha_objetivo"]})
    origenes += [futuro[c["clave"]]["ultimo_dato"]] if (p2["id_ejecucion"] == 3).any() else []
    carpeta = os.path.join(DIR_BLOB_MET, est)
    os.makedirs(carpeta, exist_ok=True)
    for t in origenes:
        pron = []
        for mdl in modelos_met:
            for h in H:
                f = t + pd.Timedelta(days=h)
                fila = datos[mdl]["pr"][h].reindex([f]).iloc[0]
                pron.append({"modelo": mdl, "horizonte": h, "fecha_objetivo": str(f.date()),
                             **{k: (None if pd.isna(v) else round(float(v), 4)) for k, v in fila.items()}})
        doc = {"estacion": est, "fecha_emision": str(t.date()),
               "fuente": "Open-Meteo Previous Runs API (valor previous_dayN = pronóstico emitido N días antes del día objetivo)",
               "agregacion": "diaria, hora local America/Lima: temp °C, hr %, viento m/s, viento_sin/viento_cos medios, precip mm (suma), nubes %",
               "modelos_por_horizonte_v2": {str(h): sorted(m) for h, m in met.items()}, "pronosticos": pron}
        with open(os.path.join(carpeta, f"{t.date()}.json"), "w", encoding="utf-8") as fj:
            json.dump(doc, fj, ensure_ascii=False, indent=1)
    n_json[est] = len(origenes)
print("JSON de pronósticos meteorológicos por estación:", n_json)

# %% [markdown]
# ## 5. Guardar CSV y resumen

# %%
print("CSV en", PLAT)
guardar_csv(estacion, "estacion")
guardar_csv(ejecucion, "ejecucion_proceso")
guardar_csv(medicion, "medicion_diaria")
guardar_csv(modelo, "modelo")
guardar_csv(prediccion, "prediccion")
pd.DataFrame(omitidos).to_csv(os.path.join(PLAT, "control_meteo_omitida.csv"), sep=";", index=False, encoding="utf-8")
pd.DataFrame(origen_futuro).to_csv(os.path.join(PLAT, "control_pronostico_futuro.csv"), sep=";", index=False, encoding="utf-8")
coincidencia.to_csv(os.path.join(PLAT, "control_coincidencia_reanalisis.csv"), sep=";", index=False, encoding="utf-8")
pd.DataFrame(control_pm).to_csv(os.path.join(PLAT, "control_meteo_pronosticada.csv"), sep=";", index=False, encoding="utf-8")
print(medicion.groupby(["id_estacion", "id_variable", "origen"])["fecha"].agg(["count", "min", "max"]).to_string())
