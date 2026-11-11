package com.wayrapredict.api.repositories;

import com.wayrapredict.api.entities.Modelo;
import jakarta.persistence.Tuple;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface ModeloRepository extends JpaRepository<Modelo, Integer> {

    //Métricas de los modelos de cada estación (prueba a h = 1). Con soloVigente = true, solo el vigente
    //("Desempeño del modelo"); si no, todas las versiones (vigente y respaldos).
    @Query(value = "SELECT e.codigo AS estacion, e.nombre AS estacion_nombre, v.codigo AS contaminante, " +
            "       m.id_modelo AS id_modelo, m.version AS version, m.vigente AS vigente, " +
            "       m.fecha_entrenamiento AS fecha_entrenamiento, m.rmse AS rmse, m.mae AS mae, m.r2 AS r2, " +
            "       v.unidad AS unidad " +
            "FROM modelo m " +
            "JOIN estacion e ON e.id_estacion = m.id_estacion " +
            "JOIN variable v ON v.id_variable = m.id_variable " +
            "WHERE (CAST(:codigo AS VARCHAR) IS NULL OR e.codigo = :codigo) AND (m.vigente OR NOT :soloVigente) " +
            "ORDER BY e.id_estacion, m.vigente DESC, m.version", nativeQuery = true)
    List<Tuple> metricas(@Param("codigo") String codigo, @Param("soloVigente") boolean soloVigente);
}
