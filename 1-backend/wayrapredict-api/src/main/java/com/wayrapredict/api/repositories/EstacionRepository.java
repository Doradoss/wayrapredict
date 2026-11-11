package com.wayrapredict.api.repositories;

import com.wayrapredict.api.entities.Estacion;
import jakarta.persistence.Tuple;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface EstacionRepository extends JpaRepository<Estacion, Integer> {

    Optional<Estacion> findByCodigo(String codigo);

    //Lista las estaciones con su contaminante (el del modelo vigente), su fecha de referencia (último día medido
    //por la estación: origen = 'estacion'), el valor de ese día con su categoría INCA y la fecha de la última
    //actualización de predicciones (fin de la última ejecución que generó predicciones para la estación).
    //Categoría del valor medido: INCA = valor * 100 / ECA; <= 50 Buena, <= 100 Moderada, sobre el VUEC (si existe)
    //Umbral de cuidado y si no Mala (la misma regla con que se clasifican las predicciones).
    @Query(value = "SELECT e.id_estacion AS id_estacion, e.codigo AS codigo, e.nombre AS nombre, " +
            "       e.departamento AS departamento, e.provincia AS provincia, e.distrito AS distrito, " +
            "       e.este AS este, e.norte AS norte, e.zona_utm AS zona_utm, e.altitud AS altitud, e.activa AS activa, " +
            "       v.codigo AS contaminante, v.nombre AS contaminante_nombre, v.unidad AS unidad, " +
            "       v.eca_24h AS eca_24h, v.oms_24h AS oms_24h, ref.fecha_referencia AS fecha_referencia, " +
            "       ult.valor AS ultimo_valor, ROUND(ult.valor * 100 / v.eca_24h, 1) AS ultimo_valor_inca, " +
            "       cu.nombre AS categoria_ultimo_valor, cu.color_hex AS color_ultimo_valor, " +
            "       (SELECT MAX(ep.fecha_fin) FROM prediccion p " +
            "          JOIN modelo m2 ON m2.id_modelo = p.id_modelo " +
            "          JOIN ejecucion_proceso ep ON ep.id_ejecucion = p.id_ejecucion " +
            "         WHERE m2.id_estacion = e.id_estacion) AS ultima_actualizacion " +
            "FROM estacion e " +
            "LEFT JOIN modelo m ON m.id_estacion = e.id_estacion AND m.vigente " +
            "LEFT JOIN variable v ON v.id_variable = m.id_variable " +
            "LEFT JOIN LATERAL (SELECT MAX(md.fecha) AS fecha_referencia FROM medicion_diaria md " +
            "                   WHERE md.id_estacion = e.id_estacion AND md.id_variable = v.id_variable " +
            "                     AND md.origen = 'estacion') ref ON TRUE " +
            "LEFT JOIN medicion_diaria ult ON ult.id_estacion = e.id_estacion AND ult.id_variable = v.id_variable " +
            "      AND ult.fecha = ref.fecha_referencia AND ult.origen = 'estacion' " +
            "LEFT JOIN categoria_inca cu ON cu.nombre = CASE " +
            "      WHEN ult.valor IS NULL OR v.eca_24h IS NULL THEN NULL " +
            "      WHEN v.vuec IS NOT NULL AND ult.valor > v.vuec THEN 'Umbral de cuidado' " +
            "      WHEN ult.valor * 100 / v.eca_24h <= 50 THEN 'Buena' " +
            "      WHEN ult.valor * 100 / v.eca_24h <= 100 THEN 'Moderada' ELSE 'Mala' END " +
            "WHERE (CAST(:codigo AS VARCHAR) IS NULL OR e.codigo = :codigo) " +
            "ORDER BY e.id_estacion", nativeQuery = true)
    List<Tuple> estacionesConReferencia(@Param("codigo") String codigo);
}
