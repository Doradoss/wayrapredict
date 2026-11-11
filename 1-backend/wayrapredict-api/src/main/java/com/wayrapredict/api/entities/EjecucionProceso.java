package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

//Ejecución del proceso de carga o de predicción (en_curso | completada | fallida)
@Entity
@Table(name = "ejecucion_proceso")
@Data
@NoArgsConstructor
public class EjecucionProceso {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id_ejecucion")
    private Long idEjecucion;
    @Column(name = "fecha_inicio", nullable = false)
    private LocalDateTime fechaInicio;
    @Column(name = "fecha_fin")
    private LocalDateTime fechaFin;
    @Column(name = "estado", nullable = false, length = 12)
    private String estado;
    @Column(name = "mensaje_error", columnDefinition = "text")
    private String mensajeError;
}
