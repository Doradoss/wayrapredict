package com.wayrapredict.api.dtos.CategoriaIncaDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

//Categoría del INCA (leyenda del semáforo)
@Data
@NoArgsConstructor
@AllArgsConstructor
public class CategoriaIncaDto {
    private Short idCategoria;
    private String nombre;
    private String colorHex;
    private BigDecimal incaMin;
    private BigDecimal incaMax;
    private String recomendacion;
}
