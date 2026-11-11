package com.wayrapredict.api.repositories;

import com.wayrapredict.api.entities.MedicionDiaria;
import jakarta.persistence.Tuple;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;

public interface MedicionDiariaRepository extends JpaRepository<MedicionDiaria, Long> {

    //Serie diaria de una estación entre dos fechas: contaminante y meteorología, cada valor con su origen
    //(estacion | estacion_vecina | servicio_meteo | pronostico_meteo), para el gráfico y el tooltip
    @Query(value = "SELECT md.fecha AS fecha, " +
            "  MAX(CASE WHEN v.tipo = 'contaminante' THEN md.valor END) AS contaminante, " +
            "  MAX(CASE WHEN v.tipo = 'contaminante' THEN md.origen END) AS origen_contaminante, " +
            "  MAX(CASE WHEN v.codigo = 'TEMPERATURA' THEN md.valor END) AS temperatura, " +
            "  MAX(CASE WHEN v.codigo = 'TEMPERATURA' THEN md.origen END) AS origen_temperatura, " +
            "  MAX(CASE WHEN v.codigo = 'HUMEDAD_RELATIVA' THEN md.valor END) AS humedad_relativa, " +
            "  MAX(CASE WHEN v.codigo = 'HUMEDAD_RELATIVA' THEN md.origen END) AS origen_humedad_relativa, " +
            "  MAX(CASE WHEN v.codigo = 'VELOCIDAD_VIENTO' THEN md.valor END) AS velocidad_viento, " +
            "  MAX(CASE WHEN v.codigo = 'VELOCIDAD_VIENTO' THEN md.origen END) AS origen_velocidad_viento, " +
            "  MAX(CASE WHEN v.codigo = 'DIRECCION_VIENTO' THEN md.valor END) AS direccion_viento, " +
            "  MAX(CASE WHEN v.codigo = 'DIRECCION_VIENTO' THEN md.origen END) AS origen_direccion_viento, " +
            "  MAX(CASE WHEN v.codigo = 'PRESION_BAROMETRICA' THEN md.valor END) AS presion_barometrica, " +
            "  MAX(CASE WHEN v.codigo = 'PRESION_BAROMETRICA' THEN md.origen END) AS origen_presion_barometrica, " +
            "  MAX(CASE WHEN v.codigo = 'PRECIPITACION' THEN md.valor END) AS precipitacion, " +
            "  MAX(CASE WHEN v.codigo = 'PRECIPITACION' THEN md.origen END) AS origen_precipitacion " +
            "FROM medicion_diaria md " +
            "JOIN estacion e ON e.id_estacion = md.id_estacion " +
            "JOIN variable v ON v.id_variable = md.id_variable " +
            "WHERE e.codigo = :codigo AND md.fecha BETWEEN :desde AND :hasta " +
            "GROUP BY md.fecha " +
            "ORDER BY md.fecha", nativeQuery = true)
    List<Tuple> serieDiaria(@Param("codigo") String codigo, @Param("desde") LocalDate desde,
                            @Param("hasta") LocalDate hasta);

    //Mediciones de una estación en formato largo (una fila por variable y día), con su unidad y origen
    @Query(value = "SELECT md.fecha AS fecha, v.codigo AS variable, v.nombre AS variable_nombre, v.tipo AS tipo, " +
            "       v.unidad AS unidad, md.valor AS valor, md.origen AS origen " +
            "FROM medicion_diaria md " +
            "JOIN estacion e ON e.id_estacion = md.id_estacion " +
            "JOIN variable v ON v.id_variable = md.id_variable " +
            "WHERE e.codigo = :codigo AND md.fecha BETWEEN :desde AND :hasta " +
            "  AND (CAST(:variable AS VARCHAR) IS NULL OR v.codigo = :variable) " +
            "ORDER BY md.fecha, v.id_variable", nativeQuery = true)
    List<Tuple> medicionesPorEstacion(@Param("codigo") String codigo, @Param("desde") LocalDate desde,
                                      @Param("hasta") LocalDate hasta, @Param("variable") String variable);

    //Último día con dato de una estación en cualquier origen (incluye la meteorología pronosticada)
    @Query(value = "SELECT MAX(md.fecha) FROM medicion_diaria md JOIN estacion e ON e.id_estacion = md.id_estacion " +
            "WHERE e.codigo = :codigo", nativeQuery = true)
    LocalDate ultimaFechaConDatos(@Param("codigo") String codigo);
}
