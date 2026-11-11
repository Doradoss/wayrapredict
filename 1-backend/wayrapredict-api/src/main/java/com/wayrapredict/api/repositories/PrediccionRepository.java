package com.wayrapredict.api.repositories;

import com.wayrapredict.api.entities.Prediccion;
import jakarta.persistence.Tuple;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

public interface PrediccionRepository extends JpaRepository<Prediccion, Long> {

    //Columnas comunes de una predicción: valor, intervalo del 80 %, INCA (calculado), superación del ECA,
    //categoría y el modelo (versión) que la generó
    String COLUMNAS = "p.id_prediccion AS id_prediccion, e.codigo AS estacion, v.codigo AS contaminante, " +
            "p.fecha_objetivo AS fecha_objetivo, ref.fecha_referencia AS fecha_referencia, " +
            "(p.fecha_objetivo - ref.fecha_referencia) AS dias_desde_referencia, " +
            "p.valor AS valor, p.limite_inferior AS limite_inferior, p.limite_superior AS limite_superior, " +
            "ROUND(p.valor * 100 / v.eca_24h, 1) AS valor_inca, (p.valor > v.eca_24h) AS supera_eca, " +
            "c.nombre AS categoria_inca, c.color_hex AS color_hex, c.recomendacion AS recomendacion, " +
            "m.version AS version_modelo, m.vigente AS modelo_vigente, p.id_ejecucion AS id_ejecucion, " +
            "p.verificado AS verificado, p.fecha_verificacion AS fecha_verificacion, " +
            "(SELECT u.correo FROM usuario u WHERE u.id_usuario = p.verificado_por) AS verificado_por ";

    String UNIONES = "FROM prediccion p " +
            "JOIN modelo m ON m.id_modelo = p.id_modelo " +
            "JOIN estacion e ON e.id_estacion = m.id_estacion " +
            "JOIN variable v ON v.id_variable = m.id_variable " +
            "JOIN categoria_inca c ON c.id_categoria = p.id_categoria " +
            "JOIN LATERAL (SELECT MAX(md.fecha) AS fecha_referencia FROM medicion_diaria md " +
            "              WHERE md.id_estacion = m.id_estacion AND md.id_variable = m.id_variable " +
            "                AND md.origen = 'estacion') ref ON TRUE ";

    //Próximos días de una estación: predicciones de la ÚLTIMA ejecución que generó predicciones para la estación
    //(sea del modelo vigente o de su respaldo) con fecha objetivo posterior a la fecha de referencia
    @Query(value = "SELECT " + COLUMNAS + UNIONES +
            "WHERE e.codigo = :codigo " +
            "  AND p.fecha_objetivo > ref.fecha_referencia " +
            "  AND p.id_ejecucion = (SELECT MAX(p2.id_ejecucion) FROM prediccion p2 " +
            "                        JOIN modelo m2 ON m2.id_modelo = p2.id_modelo " +
            "                        WHERE m2.id_estacion = e.id_estacion) " +
            "ORDER BY p.fecha_objetivo", nativeQuery = true)
    List<Tuple> proximosDias(@Param("codigo") String codigo);

    //Historial de una estación (fechas objetivo hasta la fecha de referencia) con el valor observado de ese día y
    //su categoría INCA (misma regla que las predicciones: INCA <= 50 Buena, <= 100 Moderada, sobre el VUEC
    //Umbral de cuidado y si no Mala). Si varias ejecuciones pronosticaron el mismo día, se toma la más reciente
    //(la de menor anticipación).
    @Query(value = "SELECT * FROM ( " +
            "  SELECT DISTINCT ON (p.fecha_objetivo) " + COLUMNAS + ", " +
            "         obs.valor AS observado, obs.origen AS origen_observado, " +
            "         cobs.nombre AS categoria_observada, cobs.color_hex AS color_observado " + UNIONES +
            "  LEFT JOIN medicion_diaria obs ON obs.id_estacion = m.id_estacion AND obs.id_variable = m.id_variable " +
            "        AND obs.fecha = p.fecha_objetivo " +
            "  LEFT JOIN categoria_inca cobs ON cobs.nombre = CASE " +
            "        WHEN obs.valor IS NULL OR v.eca_24h IS NULL THEN NULL " +
            "        WHEN v.vuec IS NOT NULL AND obs.valor > v.vuec THEN 'Umbral de cuidado' " +
            "        WHEN obs.valor * 100 / v.eca_24h <= 50 THEN 'Buena' " +
            "        WHEN obs.valor * 100 / v.eca_24h <= 100 THEN 'Moderada' ELSE 'Mala' END " +
            "  WHERE e.codigo = :codigo AND p.fecha_objetivo <= ref.fecha_referencia " +
            "    AND p.fecha_objetivo BETWEEN :desde AND :hasta " +
            "  ORDER BY p.fecha_objetivo, p.id_ejecucion DESC " +
            ") h ORDER BY h.fecha_objetivo", nativeQuery = true)
    List<Tuple> historial(@Param("codigo") String codigo, @Param("desde") LocalDate desde,
                          @Param("hasta") LocalDate hasta);

    //Una predicción por id con sus datos completos (para la verificación)
    @Query(value = "SELECT " + COLUMNAS + UNIONES + "WHERE p.id_prediccion = :id", nativeQuery = true)
    List<Tuple> detalle(@Param("id") Long id);

    //Marca una predicción como verificada. Actualiza SOLO las 3 columnas de verificación (el usuario wayra_api
    //no tiene permiso sobre las demás) y solo si aún no estaba verificada. Devuelve las filas afectadas.
    @Modifying
    @Query(value = "UPDATE prediccion SET verificado = TRUE, verificado_por = :idUsuario, fecha_verificacion = :fecha " +
            "WHERE id_prediccion = :id AND NOT verificado", nativeQuery = true)
    int verificar(@Param("id") Long id, @Param("idUsuario") Integer idUsuario, @Param("fecha") LocalDateTime fecha);
}
