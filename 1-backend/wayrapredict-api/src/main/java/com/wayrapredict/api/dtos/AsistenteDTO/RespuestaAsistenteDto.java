package com.wayrapredict.api.dtos.AsistenteDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

//Respuesta del asistente: texto, fecha de los datos usados (día actual más reciente de las estaciones) y el modelo
//de Gemini que respondió (el principal o el de respaldo)
@Data
@NoArgsConstructor
@AllArgsConstructor
public class RespuestaAsistenteDto {
    private String respuesta;
    private LocalDate fechaDatos;
    private String modelo;
}
