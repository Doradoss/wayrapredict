package com.wayrapredict.api.dtos.EstacionDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

//Estación con su contaminante (del modelo vigente), su fecha de referencia (último día medido por la estación),
//el valor medido ese día con su categoría INCA (tarjetas del dashboard) y la fecha de la última actualización
//de predicciones
@Data
@NoArgsConstructor
@AllArgsConstructor
public class EstacionDto {
    private Integer idEstacion;
    private String codigo;
    private String nombre;
    private String departamento;
    private String provincia;
    private String distrito;
    private BigDecimal este;
    private BigDecimal norte;
    private Integer zonaUtm;
    private Integer altitud;
    private Boolean activa;
    private String contaminante;
    private String contaminanteNombre;
    private String unidad;
    private BigDecimal eca24h;
    private BigDecimal oms24h;
    private LocalDate fechaReferencia;
    private BigDecimal ultimoValor;
    private BigDecimal ultimoValorInca;
    private String categoriaUltimoValor;
    private String colorUltimoValor;
    private LocalDateTime ultimaActualizacionPredicciones;
}
