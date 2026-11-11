package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.ToString;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

//Predicción diaria generada por un modelo en una ejecución, con intervalo del 80 % y categoría INCA.
//La verificación (verificado, verificado_por, fecha_verificacion) se llena junta o no se llena.
@Entity
@Table(name = "prediccion",
        uniqueConstraints = @UniqueConstraint(columnNames = {"id_ejecucion", "id_modelo", "fecha_objetivo"}))
@Data
@NoArgsConstructor
public class Prediccion {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id_prediccion")
    private Long idPrediccion;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "id_modelo", nullable = false)
    private Modelo modelo;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "id_ejecucion", nullable = false)
    private EjecucionProceso ejecucion;

    @Column(name = "fecha_objetivo", nullable = false)
    private LocalDate fechaObjetivo;
    @Column(name = "valor", nullable = false, precision = 10, scale = 3)
    private BigDecimal valor;
    @Column(name = "limite_inferior", precision = 10, scale = 3)
    private BigDecimal limiteInferior;
    @Column(name = "limite_superior", precision = 10, scale = 3)
    private BigDecimal limiteSuperior;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "id_categoria", nullable = false)
    private CategoriaInca categoria;

    @Column(name = "verificado", nullable = false)
    private Boolean verificado;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "verificado_por")
    private Usuario verificadoPor;

    @Column(name = "fecha_verificacion")
    private LocalDateTime fechaVerificacion;
}
