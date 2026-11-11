package com.wayrapredict.api.dtos.AlertaDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

//Alerta (fila de la vista v_alerta): predicción de categoría Moderada o superior; estado vigente | finalizada.
//estacionNombre (p. ej. "La Oroya") no está en la vista: lo agrega el servicio desde la tabla estacion.
@Data
@NoArgsConstructor
@AllArgsConstructor
public class AlertaDto {
    private Long idPrediccion;
    private String estacion;
    private String estacionNombre;
    private String departamento;
    private String contaminante;
    private LocalDate fechaObjetivo;
    private LocalDate fechaReferencia;
    private Integer diasDesdeReferencia;
    private BigDecimal valor;
    private BigDecimal valorInca;
    private String categoriaInca;
    private String colorHex;
    private Boolean superaEca;
    private String estado;
}
