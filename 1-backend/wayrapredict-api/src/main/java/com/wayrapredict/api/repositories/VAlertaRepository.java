package com.wayrapredict.api.repositories;

import com.wayrapredict.api.entities.VAlerta;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

//Vista v_alerta: solo lectura (la entidad es @Immutable; no se usan save ni delete)
public interface VAlertaRepository extends JpaRepository<VAlerta, Long> {

    //Alertas filtradas por estación y estado (vigente | finalizada); null = sin filtro
    @Query("SELECT a FROM VAlerta a WHERE (:estacion IS NULL OR a.estacion = :estacion) " +
            "AND (:estado IS NULL OR a.estado = :estado) ORDER BY a.estacion, a.fechaObjetivo DESC")
    List<VAlerta> buscar(@Param("estacion") String estacion, @Param("estado") String estado);
}
