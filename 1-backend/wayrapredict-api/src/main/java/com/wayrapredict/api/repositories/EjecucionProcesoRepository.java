package com.wayrapredict.api.repositories;

import com.wayrapredict.api.entities.EjecucionProceso;
import jakarta.persistence.Tuple;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface EjecucionProcesoRepository extends JpaRepository<EjecucionProceso, Long> {

    //Ejecuciones del proceso (más recientes primero) con cuántas predicciones y mediciones registró cada una
    @Query(value = "SELECT ep.id_ejecucion AS id_ejecucion, ep.fecha_inicio AS fecha_inicio, ep.fecha_fin AS fecha_fin, " +
            "       ep.estado AS estado, ep.mensaje_error AS mensaje_error, " +
            "       (SELECT COUNT(*) FROM prediccion p WHERE p.id_ejecucion = ep.id_ejecucion) AS predicciones, " +
            "       (SELECT COUNT(*) FROM medicion_diaria md WHERE md.id_ejecucion = ep.id_ejecucion) AS mediciones " +
            "FROM ejecucion_proceso ep " +
            "ORDER BY ep.id_ejecucion DESC", nativeQuery = true)
    List<Tuple> ejecucionesConConteo();
}
