package com.wayrapredict.api.dtos.EjecucionDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

//Estado de una ejecución del proceso, con cuántas predicciones y mediciones registró
@Data
@NoArgsConstructor
@AllArgsConstructor
public class EjecucionDto {
    private Long idEjecucion;
    private LocalDateTime fechaInicio;
    private LocalDateTime fechaFin;
    private String estado;
    private String mensajeError;
    private Long predicciones;
    private Long mediciones;
}
