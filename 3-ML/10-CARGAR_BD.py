# %% [markdown]
# # 10 - Carga de los CSV de `plataforma/` en PostgreSQL (esquema WayraPredict v1.2)
#
# - Conexión SOLO desde variables de entorno: WAYRA_DB_HOST, WAYRA_DB_PORT, WAYRA_DB_NAME, WAYRA_DB_USER,
#   WAYRA_DB_PASSWORD (nunca escritas en el código).
# - Repetible: usa las restricciones UNIQUE (ON CONFLICT ... DO UPDATE); correrlo otra vez actualiza sin duplicar.
# - No inserta catálogos que ya llena el esquema (variable, categoria_inca): solo busca sus id por código/nombre.
#   En estacion solo completa coordenadas, zona y altitud (y la inserta si faltara).
# - Ejecuciones de la carga manual: id_ejecucion 1, 2 y 3 (fijos, para que la carga sea repetible). Las
#   predicciones de esas ejecuciones que ya no estén en el CSV se borran (p. ej., si un pronóstico pasó de v2 a v1).
# - Todo en una sola transacción: si algo falla, no queda nada a medias.
# Al final se ejecutan las consultas de verificación (sección 3).

# %%
import os
import sys

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

PLAT = os.path.join(os.environ.get("WAYRA_RAIZ", "."), "plataforma")
VARIABLES_ENTORNO = ["WAYRA_DB_HOST", "WAYRA_DB_PORT", "WAYRA_DB_NAME", "WAYRA_DB_USER", "WAYRA_DB_PASSWORD"]


def conectar():
    falta = [v for v in VARIABLES_ENTORNO if not os.environ.get(v)]
    if falta:
        sys.exit(f"Faltan variables de entorno: {', '.join(falta)} (ver CLAUDE.md, sección de la base de datos)")
    return psycopg2.connect(host=os.environ["WAYRA_DB_HOST"], port=os.environ["WAYRA_DB_PORT"],
                            dbname=os.environ["WAYRA_DB_NAME"], user=os.environ["WAYRA_DB_USER"],
                            password=os.environ["WAYRA_DB_PASSWORD"])


def leer(nombre):
    df = pd.read_csv(os.path.join(PLAT, f"{nombre}.csv"), sep=";", encoding="utf-8", keep_default_na=False, na_values=[""])
    return df.astype(object).where(df.notna(), None)


def mapa(cur, sql):
    cur.execute(sql)
    return {k: v for k, v in cur.fetchall()}


# %% [markdown]
# ## 1. Lectura de los CSV

# %%
estacion, ejecucion = leer("estacion"), leer("ejecucion_proceso")
medicion, modelo, prediccion = leer("medicion_diaria"), leer("modelo"), leer("prediccion")
print({n: len(d) for n, d in [("estacion", estacion), ("ejecucion_proceso", ejecucion), ("medicion_diaria", medicion),
                              ("modelo", modelo), ("prediccion", prediccion)]})

# %% [markdown]
# ## 2. Carga (una transacción)

# %%
con = conectar()
try:
    with con:
        with con.cursor() as cur:
            # --- estacion: completa coordenadas (UNIQUE codigo)
            execute_values(cur, """
                INSERT INTO estacion (codigo, nombre, departamento, provincia, distrito, este, norte, zona_utm, altitud, activa)
                VALUES %s
                ON CONFLICT (codigo) DO UPDATE SET este = EXCLUDED.este, norte = EXCLUDED.norte,
                    zona_utm = EXCLUDED.zona_utm, altitud = EXCLUDED.altitud""",
                [tuple(r) for r in estacion[["codigo", "nombre", "departamento", "provincia", "distrito", "este", "norte",
                                             "zona_utm", "altitud", "activa"]].itertuples(index=False)])
            id_est = mapa(cur, "SELECT codigo, id_estacion FROM estacion")
            id_var = mapa(cur, "SELECT codigo, id_variable FROM variable")
            id_cat = mapa(cur, "SELECT nombre, id_categoria FROM categoria_inca")
            for col, m, df in (("id_estacion", id_est, pd.concat([medicion, modelo])), ("id_variable", id_var, pd.concat([medicion, modelo])),
                               ("id_categoria", id_cat, prediccion)):
                faltan = set(df[col]) - set(m)
                if faltan:
                    raise ValueError(f"Códigos sin registro en la base ({col}): {faltan}. ¿Se ejecutó el esquema completo?")

            # --- ejecucion_proceso: id fijos de la carga manual; luego se ajusta la secuencia
            execute_values(cur, """
                INSERT INTO ejecucion_proceso (id_ejecucion, fecha_inicio, fecha_fin, estado, mensaje_error) VALUES %s
                ON CONFLICT (id_ejecucion) DO UPDATE SET fecha_inicio = EXCLUDED.fecha_inicio, fecha_fin = EXCLUDED.fecha_fin,
                    estado = EXCLUDED.estado, mensaje_error = EXCLUDED.mensaje_error""",
                [tuple(r) for r in ejecucion[["id_ejecucion", "fecha_inicio", "fecha_fin", "estado", "mensaje_error"]].itertuples(index=False)])
            cur.execute("SELECT setval(pg_get_serial_sequence('ejecucion_proceso', 'id_ejecucion'), "
                        "(SELECT MAX(id_ejecucion) FROM ejecucion_proceso))")

            # --- medicion_diaria (UNIQUE id_estacion, id_variable, fecha)
            filas_med = [(id_est[r.id_estacion], id_var[r.id_variable], r.id_ejecucion, r.fecha, r.valor, r.origen)
                         for r in medicion.itertuples()]
            execute_values(cur, """
                INSERT INTO medicion_diaria (id_estacion, id_variable, id_ejecucion, fecha, valor, origen) VALUES %s
                ON CONFLICT (id_estacion, id_variable, fecha) DO UPDATE SET valor = EXCLUDED.valor,
                    id_ejecucion = EXCLUDED.id_ejecucion, origen = EXCLUDED.origen""", filas_med, page_size=5000)
            # mediciones de la carga manual que ya no están en el CSV (p. ej., un día completado que ahora tiene dato)
            cur.execute("CREATE TEMP TABLE _med_csv (id_estacion INT, id_variable INT, fecha DATE) ON COMMIT DROP")
            execute_values(cur, "INSERT INTO _med_csv VALUES %s", [(f[0], f[1], f[3]) for f in filas_med], page_size=5000)
            cur.execute("""
                DELETE FROM medicion_diaria m
                WHERE m.id_ejecucion = ANY(%s)
                  AND NOT EXISTS (SELECT 1 FROM _med_csv c WHERE c.id_estacion = m.id_estacion
                                  AND c.id_variable = m.id_variable AND c.fecha = m.fecha)""",
                        (list(map(int, ejecucion["id_ejecucion"])),))
            print("Mediciones antiguas de la carga manual eliminadas:", cur.rowcount)

            # --- modelo (UNIQUE id_estacion, id_variable, version; un solo vigente por estación y contaminante):
            #     primero se quitan los vigentes de esas series y luego se insertan/actualizan las versiones
            pares = {(id_est[r.id_estacion], id_var[r.id_variable]) for r in modelo.itertuples()}
            cur.executemany("UPDATE modelo SET vigente = FALSE WHERE id_estacion = %s AND id_variable = %s", list(pares))
            id_mod = {}
            for r in modelo.itertuples():
                cur.execute("""
                    INSERT INTO modelo (id_estacion, id_variable, version, ruta_blob, fecha_entrenamiento, rmse, mae, r2, vigente)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id_estacion, id_variable, version) DO UPDATE SET ruta_blob = EXCLUDED.ruta_blob,
                        fecha_entrenamiento = EXCLUDED.fecha_entrenamiento, rmse = EXCLUDED.rmse, mae = EXCLUDED.mae,
                        r2 = EXCLUDED.r2, vigente = EXCLUDED.vigente
                    RETURNING id_modelo""",
                    (id_est[r.id_estacion], id_var[r.id_variable], r.version, r.ruta_blob, r.fecha_entrenamiento,
                     r.rmse, r.mae, r.r2, str(r.vigente) == "True"))
                id_mod[r.id_modelo] = cur.fetchone()[0]

            # --- prediccion (UNIQUE id_ejecucion, id_modelo, fecha_objetivo)
            filas = [(id_mod[r.id_modelo], r.id_ejecucion, r.fecha_objetivo, r.valor, r.limite_inferior, r.limite_superior,
                      id_cat[r.id_categoria], str(r.verificado) == "True", r.verificado_por, r.fecha_verificacion)
                     for r in prediccion.itertuples()]
            execute_values(cur, """
                INSERT INTO prediccion (id_modelo, id_ejecucion, fecha_objetivo, valor, limite_inferior, limite_superior,
                                        id_categoria, verificado, verificado_por, fecha_verificacion) VALUES %s
                ON CONFLICT (id_ejecucion, id_modelo, fecha_objetivo) DO UPDATE SET valor = EXCLUDED.valor,
                    limite_inferior = EXCLUDED.limite_inferior, limite_superior = EXCLUDED.limite_superior,
                    id_categoria = EXCLUDED.id_categoria""", filas, page_size=5000)
            # predicciones de la carga manual que ya no están en el CSV (repetibilidad); las verificadas se conservan
            cur.execute("CREATE TEMP TABLE _pred_csv (id_ejecucion BIGINT, id_modelo INT, fecha_objetivo DATE) ON COMMIT DROP")
            execute_values(cur, "INSERT INTO _pred_csv VALUES %s", [(f[1], f[0], f[2]) for f in filas], page_size=5000)
            cur.execute("""
                DELETE FROM prediccion p
                WHERE p.id_ejecucion = ANY(%s) AND NOT p.verificado
                  AND NOT EXISTS (SELECT 1 FROM _pred_csv c WHERE c.id_ejecucion = p.id_ejecucion
                                  AND c.id_modelo = p.id_modelo AND c.fecha_objetivo = p.fecha_objetivo)""",
                        (list(map(int, ejecucion["id_ejecucion"])),))
            print("Predicciones antiguas de la carga manual eliminadas:", cur.rowcount)
    print("Carga completada (transacción confirmada).")
finally:
    con.close()

# %% [markdown]
# ## 3. Verificación

# %%
CONSULTAS = {
    "Filas por tabla": """
        SELECT 'estacion' AS tabla, COUNT(*) FROM estacion UNION ALL SELECT 'variable', COUNT(*) FROM variable
        UNION ALL SELECT 'categoria_inca', COUNT(*) FROM categoria_inca UNION ALL SELECT 'usuario', COUNT(*) FROM usuario
        UNION ALL SELECT 'ejecucion_proceso', COUNT(*) FROM ejecucion_proceso
        UNION ALL SELECT 'medicion_diaria', COUNT(*) FROM medicion_diaria UNION ALL SELECT 'modelo', COUNT(*) FROM modelo
        UNION ALL SELECT 'prediccion', COUNT(*) FROM prediccion""",
    "Modelos por estación": """
        SELECT e.codigo AS estacion, v.codigo AS contaminante, m.version, m.vigente, m.rmse, m.mae, m.r2,
               m.fecha_entrenamiento, m.ruta_blob, COUNT(p.id_prediccion) AS predicciones
        FROM modelo m JOIN estacion e USING (id_estacion) JOIN variable v USING (id_variable)
        LEFT JOIN prediccion p USING (id_modelo)
        GROUP BY e.codigo, v.codigo, m.version, m.vigente, m.rmse, m.mae, m.r2, m.fecha_entrenamiento, m.ruta_blob
        ORDER BY 1, 3""",
    "Fecha de referencia por estación y contaminante (último día con medición propia: origen = 'estacion')": """
        SELECT e.codigo AS estacion, v.codigo AS contaminante, MIN(md.fecha) AS primer_dia, MAX(md.fecha) AS fecha_referencia,
               COUNT(*) AS dias,
               (SELECT MAX(x.fecha) FROM medicion_diaria x WHERE x.id_estacion = e.id_estacion
                  AND x.id_variable = v.id_variable) AS max_fecha_todos_los_origenes,
               (SELECT DISTINCT fecha_referencia FROM v_alerta a WHERE a.estacion = e.codigo) AS fecha_referencia_v_alerta
        FROM medicion_diaria md JOIN estacion e USING (id_estacion) JOIN variable v USING (id_variable)
        WHERE v.tipo = 'contaminante' AND md.origen = 'estacion' GROUP BY e.id_estacion, v.id_variable, 1, 2 ORDER BY 1""",
    "Mediciones por estación y origen": """
        SELECT e.codigo AS estacion, md.origen, COUNT(*) AS filas, MIN(md.fecha) AS desde, MAX(md.fecha) AS hasta
        FROM medicion_diaria md JOIN estacion e USING (id_estacion) GROUP BY 1, 2 ORDER BY 1, 2""",
    "Mediciones por origen": """SELECT origen, COUNT(*) AS filas FROM medicion_diaria GROUP BY 1 ORDER BY 1""",
    "Mediciones por estación y variable": """
        SELECT e.codigo AS estacion, v.codigo AS variable, md.origen, COUNT(*) AS dias, MIN(md.fecha) AS desde,
               MAX(md.fecha) AS hasta
        FROM medicion_diaria md JOIN estacion e USING (id_estacion) JOIN variable v USING (id_variable)
        GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""",
    "v_alerta con estado 'vigente'": """
        SELECT estacion, departamento, contaminante, fecha_objetivo, fecha_referencia, dias_desde_referencia,
               valor, valor_inca, categoria_inca, supera_eca, estado
        FROM v_alerta WHERE estado = 'vigente' ORDER BY estacion, fecha_objetivo""",
    "Pronóstico desde la fecha de referencia (todas las categorías)": """
        SELECT e.codigo AS estacion, m.version, p.fecha_objetivo, p.valor, p.limite_inferior, p.limite_superior, c.nombre AS categoria
        FROM prediccion p JOIN modelo m USING (id_modelo) JOIN estacion e USING (id_estacion)
        JOIN categoria_inca c USING (id_categoria)
        WHERE p.fecha_objetivo > (SELECT MAX(fecha) FROM medicion_diaria md WHERE md.id_estacion = m.id_estacion
                                  AND md.id_variable = m.id_variable)
        ORDER BY 1, 3""",
    "Alertas por estación y estado (v_alerta)": """
        SELECT estacion, estado, categoria_inca, COUNT(*) FROM v_alerta GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""",
}
pd.set_option("display.width", 250)
con = conectar()
try:
    for titulo, sql in CONSULTAS.items():
        print(f"\n=== {titulo}")
        with con.cursor() as cur:
            cur.execute(sql)
            filas = cur.fetchall()
            cols = [d[0] for d in cur.description]
        print(pd.DataFrame(filas, columns=cols).to_string(index=False) if filas else "(sin filas)")
finally:
    con.close()
