-- =====================================================================
-- WayraPredict — usuario propio del backend (wayra_api) con permisos limitados
-- Ejecutar en pgAdmin conectado a la base "wayrapredict" como postgres.
-- La carga del ML (10-CARGAR_BD.py) sigue usando postgres.
--
-- ANTES DE EJECUTAR: reemplazar  CAMBIAR_ESTA_CONTRASENA  por una contraseña segura
-- (la misma que luego se pone en la variable de entorno WAYRA_API_DB_PASSWORD).
-- =====================================================================

-- 1. Crear el rol de inicio de sesión (si ya existe, solo se actualiza la contraseña)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wayra_api') THEN
        CREATE ROLE wayra_api LOGIN PASSWORD 'CAMBIAR_ESTA_CONTRASENA';
    ELSE
        ALTER ROLE wayra_api LOGIN PASSWORD 'CAMBIAR_ESTA_CONTRASENA';
    END IF;
END
$$;

-- 2. Conexión a la base y uso del esquema
GRANT CONNECT ON DATABASE wayrapredict TO wayra_api;
GRANT USAGE ON SCHEMA public TO wayra_api;

-- 3. Lectura de todas las tablas y de la vista v_alerta
GRANT SELECT ON estacion, variable, categoria_inca, usuario, ejecucion_proceso,
                medicion_diaria, modelo, prediccion TO wayra_api;
GRANT SELECT ON v_alerta TO wayra_api;

-- 4. Usuarios: registrar (solicitud de cuenta y primer administrador) y actualizar (aprobación, rol, estado)
GRANT INSERT, UPDATE ON usuario TO wayra_api;
GRANT USAGE, SELECT ON SEQUENCE usuario_id_usuario_seq TO wayra_api;

-- 5. Predicciones: SOLO las columnas de verificación
GRANT UPDATE (verificado, verificado_por, fecha_verificacion) ON prediccion TO wayra_api;

-- 6. Comprobación (debe listar SELECT en las 8 tablas y en v_alerta; INSERT/UPDATE en usuario;
--    UPDATE de columnas en prediccion)
SELECT table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'wayra_api'
ORDER BY table_name, privilege_type;

SELECT column_name, privilege_type
FROM information_schema.column_privileges
WHERE grantee = 'wayra_api' AND table_name = 'prediccion' AND privilege_type = 'UPDATE'
ORDER BY column_name;
