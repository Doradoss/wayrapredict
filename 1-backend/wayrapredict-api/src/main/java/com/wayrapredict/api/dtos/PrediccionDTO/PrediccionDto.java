package com.wayrapredict.api.dtos.PrediccionDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

//Predicción con intervalo del 80 %, INCA (calculado), superación del ECA, categoría y la versión del modelo
//que la generó. observado, origenObservado, categoriaObservada y colorObservado solo se llenan en el historial.
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PrediccionDto {
    private Long idPrediccion;
    private String estacion;
    private String contaminante;
    private LocalDate fechaObjetivo;
    private LocalDate fechaReferencia;
    private Integer diasDesdeReferencia;
    private BigDecimal valor;
    private BigDecimal limiteInferior;
    private BigDecimal limiteSuperior;
    private BigDecimal valorInca;
    private Boolean superaEca;
    private String categoriaInca;
    private String colorHex;
    private String recomendacion;
    private String versionModelo;
    private Boolean modeloVigente;
    private Long idEjecucion;
    private Boolean verificado;
    private String verificadoPor;
    private LocalDateTime fechaVerificacion;
    private BigDecimal observado;
    private String origenObservado;
    private String categoriaObservada;
    private String colorObservado;
}
