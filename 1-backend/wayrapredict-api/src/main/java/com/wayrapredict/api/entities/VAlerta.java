package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.LocalDate;

//Vista v_alerta (SOLO LECTURA): predicciones de categoría Moderada o superior, con la fecha de referencia
//(último día medido por la estación, origen = 'estacion') y el estado vigente | finalizada.
@Entity
@Immutable
@Table(name = "v_alerta")
@Data
@NoArgsConstructor
public class VAlerta {
    @Id
    @Column(name = "id_prediccion")
    private Long idPrediccion;
    @Column(name = "estacion")
    private String estacion;
    @Column(name = "departamento")
    private String departamento;
    @Column(name = "contaminante")
    private String contaminante;
    @Column(name = "fecha_objetivo")
    private LocalDate fechaObjetivo;
    @Column(name = "fecha_referencia")
    private LocalDate fechaReferencia;
    @Column(name = "dias_desde_referencia")
    private Integer diasDesdeReferencia;
    @Column(name = "valor")
    private BigDecimal valor;
    @Column(name = "valor_inca")
    private BigDecimal valorInca;
    @Column(name = "categoria_inca")
    private String categoriaInca;
    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(name = "color_hex")
    private String colorHex;
    @Column(name = "supera_eca")
    private Boolean superaEca;
    @Column(name = "estado", columnDefinition = "text")
    private String estado;
}
