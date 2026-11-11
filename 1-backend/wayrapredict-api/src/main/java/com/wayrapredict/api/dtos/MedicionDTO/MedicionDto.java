package com.wayrapredict.api.dtos.MedicionDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

//Una medición diaria (formato largo: una fila por variable y día) con su unidad y origen
@Data
@NoArgsConstructor
@AllArgsConstructor
public class MedicionDto {
    private LocalDate fecha;
    private String variable;
    private String variableNombre;
    private String tipo;
    private String unidad;
    private BigDecimal valor;
    private String origen;
}
