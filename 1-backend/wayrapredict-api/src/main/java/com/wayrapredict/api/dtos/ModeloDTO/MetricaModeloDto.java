package com.wayrapredict.api.dtos.ModeloDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

//Métricas de un modelo (prueba a 1 día): RMSE y MAE en la unidad del contaminante, R² sin unidad
@Data
@NoArgsConstructor
@AllArgsConstructor
public class MetricaModeloDto {
    private String estacion;
    private String estacionNombre;
    private String contaminante;
    private Integer idModelo;
    private String version;
    private Boolean vigente;
    private LocalDateTime fechaEntrenamiento;
    private BigDecimal rmse;
    private BigDecimal mae;
    private BigDecimal r2;
    private String unidad;
}
