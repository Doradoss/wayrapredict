package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;

//Categoría del Índice de Calidad del Aire (INCA) con su color y recomendación (catálogo)
@Entity
@Table(name = "categoria_inca")
@Data
@NoArgsConstructor
public class CategoriaInca {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id_categoria")
    private Short idCategoria;
    @Column(name = "nombre", nullable = false, length = 30, unique = true)
    private String nombre;
    //CHAR(7) en la base (p. ej. #2E8B3E)
    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(name = "color_hex", nullable = false, length = 7)
    private String colorHex;
    @Column(name = "inca_min", precision = 6, scale = 1)
    private BigDecimal incaMin;
    @Column(name = "inca_max", precision = 6, scale = 1)
    private BigDecimal incaMax;
    @Column(name = "recomendacion", nullable = false, columnDefinition = "text")
    private String recomendacion;
}
