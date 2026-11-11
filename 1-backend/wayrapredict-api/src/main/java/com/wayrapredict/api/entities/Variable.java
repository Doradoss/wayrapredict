package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

//Variable medida o pronosticada: contaminante (SO2, PM10, PM2.5) o meteorológica (catálogo)
@Entity
@Table(name = "variable")
@Data
@NoArgsConstructor
public class Variable {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id_variable")
    private Integer idVariable;
    @Column(name = "codigo", nullable = false, length = 30, unique = true)
    private String codigo;
    @Column(name = "nombre", nullable = false, length = 80)
    private String nombre;
    @Column(name = "tipo", nullable = false, length = 20)
    private String tipo;
    @Column(name = "unidad", nullable = false, length = 20)
    private String unidad;
    @Column(name = "eca_24h", precision = 8, scale = 2)
    private BigDecimal eca24h;
    @Column(name = "oms_24h", precision = 8, scale = 2)
    private BigDecimal oms24h;
    @Column(name = "vuec", precision = 8, scale = 2)
    private BigDecimal vuec;
}
