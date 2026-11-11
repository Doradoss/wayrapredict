package com.wayrapredict.api.dtos.MedicionDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

//Un día de la serie de una estación (gráfico y tooltip): contaminante y meteorología, cada valor con su origen
//(estacion | estacion_vecina | servicio_meteo | pronostico_meteo). posteriorAReferencia = día después del
//último dato medido (solo trae meteorología pronosticada).
@Data
@NoArgsConstructor
@AllArgsConstructor
public class SerieDiariaDto {
    private LocalDate fecha;
    private Boolean posteriorAReferencia;
    private BigDecimal contaminante;
    private String origenContaminante;
    private BigDecimal temperatura;
    private String origenTemperatura;
    private BigDecimal humedadRelativa;
    private String origenHumedadRelativa;
    private BigDecimal velocidadViento;
    private String origenVelocidadViento;
    private BigDecimal direccionViento;
    private String origenDireccionViento;
    private BigDecimal presionBarometrica;
    private String origenPresionBarometrica;
    private BigDecimal precipitacion;
    private String origenPrecipitacion;
}
