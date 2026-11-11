package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.ToString;

import java.math.BigDecimal;
import java.time.LocalDate;

//Valor diario de una variable en una estación.
//Origen: estacion | estacion_vecina | servicio_meteo | pronostico_meteo
@Entity
@Table(name = "medicion_diaria",
        uniqueConstraints = @UniqueConstraint(columnNames = {"id_estacion", "id_variable", "fecha"}))
@Data
@NoArgsConstructor
public class MedicionDiaria {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id_medicion")
    private Long idMedicion;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "id_estacion", nullable = false)
    private Estacion estacion;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "id_variable", nullable = false)
    private Variable variable;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "id_ejecucion")
    private EjecucionProceso ejecucion;

    @Column(name = "fecha", nullable = false)
    private LocalDate fecha;
    @Column(name = "valor", nullable = false, precision = 10, scale = 3)
    private BigDecimal valor;
    @Column(name = "origen", nullable = false, length = 20)
    private String origen;
}
