package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.ToString;

import java.math.BigDecimal;
import java.time.LocalDateTime;

//Versión de modelo por estación y contaminante (solo una vigente) con sus métricas de la prueba a h = 1
@Entity
@Table(name = "modelo",
        uniqueConstraints = @UniqueConstraint(columnNames = {"id_estacion", "id_variable", "version"}))
@Data
@NoArgsConstructor
public class Modelo {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id_modelo")
    private Integer idModelo;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "id_estacion", nullable = false)
    private Estacion estacion;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "id_variable", nullable = false)
    private Variable variable;

    @Column(name = "version", nullable = false, length = 20)
    private String version;
    @Column(name = "ruta_blob", nullable = false, length = 255)
    private String rutaBlob;
    @Column(name = "fecha_entrenamiento", nullable = false)
    private LocalDateTime fechaEntrenamiento;
    @Column(name = "rmse", precision = 10, scale = 4)
    private BigDecimal rmse;
    @Column(name = "mae", precision = 10, scale = 4)
    private BigDecimal mae;
    @Column(name = "r2", precision = 6, scale = 4)
    private BigDecimal r2;
    @Column(name = "vigente", nullable = false)
    private Boolean vigente;
}
