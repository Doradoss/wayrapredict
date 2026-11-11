package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

//Estación de monitoreo de calidad del aire (catálogo)
@Entity
@Table(name = "estacion")
@Data
@NoArgsConstructor
public class Estacion {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id_estacion")
    private Integer idEstacion;
    @Column(name = "codigo", nullable = false, length = 20, unique = true)
    private String codigo;
    @Column(name = "nombre", nullable = false, length = 120)
    private String nombre;
    @Column(name = "departamento", nullable = false, length = 60)
    private String departamento;
    @Column(name = "provincia", length = 60)
    private String provincia;
    @Column(name = "distrito", length = 60)
    private String distrito;
    @Column(name = "este", precision = 12, scale = 2)
    private BigDecimal este;
    @Column(name = "norte", precision = 12, scale = 2)
    private BigDecimal norte;
    @Column(name = "zona_utm")
    private Short zonaUtm;
    @Column(name = "altitud")
    private Integer altitud;
    @Column(name = "activa", nullable = false)
    private Boolean activa;
}
