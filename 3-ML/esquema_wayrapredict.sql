-- =====================================================================
-- WayraPredict — Esquema de base de datos (PostgreSQL) — versión 1.4
-- 8 tablas + 1 vista. No se almacenan datos que puedan calcularse.
--
-- Cambios respecto a la versión anterior:
--   * Estaciones finales: CA-CC-01 (Junín), CA-HUAR-01 (Pasco) y CA-ILO-02 (Moquegua).
--   * La vista v_alerta usa una FECHA DE REFERENCIA por estación y contaminante:
--     el último día con medición disponible (MAX(fecha) en medicion_diaria).
--     Una alerta es "vigente" si su fecha objetivo es posterior a ese día.
--     Con datos al día funciona igual que antes; con datos históricos,
--     la plataforma muestra los pronósticos relativos al último dato disponible.
--   * Se incluye el PM2.5 en el catálogo de variables para una ampliación futura
--     (actualmente no se modela en las estaciones piloto).
--   * medicion_diaria incluye la columna "origen" de cada valor: medido por la estación,
--     estimado con una estación vecina, completado con un servicio meteorológico
--     (reanálisis) o pronosticado (meteorología de los días objetivo, para el dashboard).
--     La fecha de referencia usa solo valores medidos por la estación.
--   * Cada estación puede tener varias versiones de modelo (por ejemplo, v1 y v2);
--     solo una es vigente, y cada predicción queda asociada al modelo que la generó.
-- =====================================================================

-- ---------------------------------------------------------------------
-- (Opcional) Reinicio completo en desarrollo: descomentar para borrar todo
-- ---------------------------------------------------------------------
-- DROP VIEW  IF EXISTS v_alerta;
-- DROP TABLE IF EXISTS prediccion, modelo, medicion_diaria, ejecucion_proceso,
--                      usuario, categoria_inca, variable, estacion CASCADE;

-- ---------------------------------------------------------------------
-- 1. Catálogos
-- ---------------------------------------------------------------------
CREATE TABLE estacion (
    id_estacion   SERIAL PRIMARY KEY,
    codigo        VARCHAR(20)  NOT NULL UNIQUE,          -- código OEFA, p. ej. CA-CC-01
    nombre        VARCHAR(120) NOT NULL,
    departamento  VARCHAR(60)  NOT NULL,
    provincia     VARCHAR(60),
    distrito      VARCHAR(60),
    este          NUMERIC(12,2),                         -- coordenada UTM
    norte         NUMERIC(12,2),                         -- coordenada UTM
    zona_utm      SMALLINT,
    altitud       INTEGER,
    activa        BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE variable (
    id_variable   SERIAL PRIMARY KEY,
    codigo        VARCHAR(30)  NOT NULL UNIQUE,          -- p. ej. SO2, PM10, TEMPERATURA
    nombre        VARCHAR(80)  NOT NULL,
    tipo          VARCHAR(20)  NOT NULL CHECK (tipo IN ('contaminante', 'meteorologica')),
    unidad        VARCHAR(20)  NOT NULL,
    eca_24h       NUMERIC(8,2),                          -- ECA-Aire de 24 h (nulo en meteorológicas)
    oms_24h       NUMERIC(8,2),                          -- guía OMS 2021 de 24 h
    vuec          NUMERIC(8,2)                           -- valor umbral del estado de cuidado
);

CREATE TABLE categoria_inca (
    id_categoria  SMALLSERIAL PRIMARY KEY,
    nombre        VARCHAR(30)  NOT NULL UNIQUE,
    color_hex     CHAR(7)      NOT NULL,
    inca_min      NUMERIC(6,1),                          -- nulo: desde el VUEC del contaminante
    inca_max      NUMERIC(6,1),                          -- nulo: hasta el VUEC o sin límite
    recomendacion TEXT         NOT NULL
);

-- ---------------------------------------------------------------------
-- 2. Usuarios
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
    id_usuario       SERIAL PRIMARY KEY,
    nombres          VARCHAR(80)  NOT NULL,
    apellidos        VARCHAR(80)  NOT NULL,
    correo           VARCHAR(150) NOT NULL UNIQUE,       -- funciona como nombre de usuario
    hash_contrasena  VARCHAR(255) NOT NULL,
    institucion      VARCHAR(150),                       -- nulo para administradores
    cargo            VARCHAR(100),
    rol              VARCHAR(25)  NOT NULL DEFAULT 'usuario_institucional'
                     CHECK (rol IN ('administrador', 'usuario_institucional')),
    estado           VARCHAR(12)  NOT NULL DEFAULT 'pendiente'
                     CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    fecha_registro   TIMESTAMP    NOT NULL DEFAULT NOW(),
    aprobado_por     INTEGER      REFERENCES usuario(id_usuario),
    fecha_aprobacion TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 3. Operación
-- ---------------------------------------------------------------------
CREATE TABLE ejecucion_proceso (
    id_ejecucion  BIGSERIAL PRIMARY KEY,
    fecha_inicio  TIMESTAMP   NOT NULL DEFAULT NOW(),
    fecha_fin     TIMESTAMP,
    estado        VARCHAR(12) NOT NULL DEFAULT 'en_curso'
                  CHECK (estado IN ('en_curso', 'completada', 'fallida')),
    mensaje_error TEXT
);

-- ---------------------------------------------------------------------
-- 4. Datos y predicciones
-- ---------------------------------------------------------------------
CREATE TABLE medicion_diaria (
    id_medicion   BIGSERIAL PRIMARY KEY,
    id_estacion   INTEGER       NOT NULL REFERENCES estacion(id_estacion),
    id_variable   INTEGER       NOT NULL REFERENCES variable(id_variable),
    id_ejecucion  BIGINT        REFERENCES ejecucion_proceso(id_ejecucion),
    fecha         DATE          NOT NULL,
    valor         NUMERIC(10,3) NOT NULL,
    origen        VARCHAR(20)   NOT NULL DEFAULT 'estacion'
                  CHECK (origen IN ('estacion', 'estacion_vecina', 'servicio_meteo', 'pronostico_meteo')),
    UNIQUE (id_estacion, id_variable, fecha)
);

CREATE TABLE modelo (
    id_modelo           SERIAL PRIMARY KEY,
    id_estacion         INTEGER      NOT NULL REFERENCES estacion(id_estacion),
    id_variable         INTEGER      NOT NULL REFERENCES variable(id_variable),
    version             VARCHAR(20)  NOT NULL,
    ruta_blob           VARCHAR(255) NOT NULL,           -- archivo del modelo en Azure Blob Storage
    fecha_entrenamiento TIMESTAMP    NOT NULL,
    rmse                NUMERIC(10,4),
    mae                 NUMERIC(10,4),
    r2                  NUMERIC(6,4),
    vigente             BOOLEAN      NOT NULL DEFAULT FALSE,
    UNIQUE (id_estacion, id_variable, version)
);
-- Solo una versión vigente por estación y contaminante
CREATE UNIQUE INDEX ux_modelo_vigente ON modelo (id_estacion, id_variable) WHERE vigente;

CREATE TABLE prediccion (
    id_prediccion      BIGSERIAL PRIMARY KEY,
    id_modelo          INTEGER       NOT NULL REFERENCES modelo(id_modelo),   -- define estación y contaminante
    id_ejecucion       BIGINT        NOT NULL REFERENCES ejecucion_proceso(id_ejecucion),
    fecha_objetivo     DATE          NOT NULL,
    valor              NUMERIC(10,3) NOT NULL,
    limite_inferior    NUMERIC(10,3),
    limite_superior    NUMERIC(10,3),
    id_categoria       SMALLINT      NOT NULL REFERENCES categoria_inca(id_categoria),
    verificado         BOOLEAN       NOT NULL DEFAULT FALSE,
    verificado_por     INTEGER       REFERENCES usuario(id_usuario),
    fecha_verificacion TIMESTAMP,
    UNIQUE (id_ejecucion, id_modelo, fecha_objetivo),
    CHECK ((verificado AND verificado_por IS NOT NULL AND fecha_verificacion IS NOT NULL)
           OR (NOT verificado AND verificado_por IS NULL AND fecha_verificacion IS NULL))
);
CREATE INDEX ix_prediccion_consulta ON prediccion (id_modelo, fecha_objetivo);

-- ---------------------------------------------------------------------
-- 5. Vista de alertas (no es una tabla: se calcula a partir de las predicciones)
--    Alerta = predicción de categoría moderada o superior.
--    El valor INCA y la superación del ECA se calculan, no se guardan.
--    Fecha de referencia = último día con medición de esa estación y contaminante.
-- ---------------------------------------------------------------------
CREATE VIEW v_alerta AS
SELECT p.id_prediccion,
       e.codigo                               AS estacion,
       e.departamento,
       v.codigo                               AS contaminante,
       p.fecha_objetivo,
       ref.fecha_referencia,
       (p.fecha_objetivo - ref.fecha_referencia) AS dias_desde_referencia,
       p.valor,
       ROUND(p.valor * 100 / v.eca_24h, 1)    AS valor_inca,
       c.nombre                               AS categoria_inca,
       c.color_hex,
       (p.valor > v.eca_24h)                  AS supera_eca,
       CASE WHEN p.fecha_objetivo > ref.fecha_referencia
            THEN 'vigente' ELSE 'finalizada' END AS estado
FROM prediccion p
JOIN modelo m         ON m.id_modelo = p.id_modelo
JOIN estacion e       ON e.id_estacion = m.id_estacion
JOIN variable v       ON v.id_variable = m.id_variable
JOIN categoria_inca c ON c.id_categoria = p.id_categoria
JOIN LATERAL (
       SELECT MAX(md.fecha) AS fecha_referencia
       FROM medicion_diaria md
       WHERE md.id_estacion = m.id_estacion
         AND md.id_variable = m.id_variable
         AND md.origen = 'estacion'
     ) ref ON TRUE
WHERE c.nombre <> 'Buena';

-- =====================================================================
-- Datos iniciales (catálogos)
-- =====================================================================
INSERT INTO categoria_inca (nombre, color_hex, inca_min, inca_max, recomendacion) VALUES
 ('Buena',             '#2E8B3E',   0,   50, 'La calidad del aire es aceptable; se pueden realizar actividades al aire libre.'),
 ('Moderada',          '#E0B21A',  51,  100, 'Las personas de grupos sensibles deben reducir la actividad física intensa al aire libre.'),
 ('Mala',              '#D9731F', 101, NULL, 'Se recomienda reducir las actividades al aire libre, en especial a niños, adultos mayores y personas con asma.'),
 ('Umbral de cuidado', '#C0392B', NULL, NULL, 'Seguir las indicaciones de la autoridad de salud según los niveles de estado de alerta.');

-- PENDIENTE: completar el VUEC del SO2 y del PM10 con los valores verificados en la
-- R.M. N.° 181-2016-MINAM. Mientras sea NULL, los valores sobre INCA 100 se clasifican como "Mala".
INSERT INTO variable (codigo, nombre, tipo, unidad, eca_24h, oms_24h, vuec) VALUES
 ('SO2',   'Dióxido de azufre',          'contaminante',  'ug/m3', 250, 40, NULL),
 ('PM10',  'Material particulado PM10',  'contaminante',  'ug/m3', 100, 45, NULL),
 ('PM2.5', 'Material particulado PM2.5', 'contaminante',  'ug/m3',  50, 15, NULL),
 ('TEMPERATURA',         'Temperatura',          'meteorologica', '°C',   NULL, NULL, NULL),
 ('HUMEDAD_RELATIVA',    'Humedad relativa',     'meteorologica', '%',    NULL, NULL, NULL),
 ('VELOCIDAD_VIENTO',    'Velocidad del viento', 'meteorologica', 'm/s',  NULL, NULL, NULL),
 ('DIRECCION_VIENTO',    'Dirección del viento', 'meteorologica', '°',    NULL, NULL, NULL),
 ('PRESION_BAROMETRICA', 'Presión barométrica',  'meteorologica', 'mmHg', NULL, NULL, NULL),
 ('PRECIPITACION',       'Precipitación',        'meteorologica', 'mm',   NULL, NULL, NULL);

-- Coordenadas y altitud: las completa el script de carga si están en los datos crudos.
-- Verificar provincia y distrito en el portal del OEFA.
INSERT INTO estacion (codigo, nombre, departamento, provincia, distrito) VALUES
 ('CA-CC-01',   'La Oroya',     'Junín',    'Yauli', 'La Oroya'),
 ('CA-HUAR-01', 'Huaraucaca',   'Pasco',    'Pasco', 'Tinyahuarco'),
 ('CA-ILO-02',  'Ilo-Pacocha',  'Moquegua', 'Ilo',   'Pacocha');
