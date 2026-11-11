package com.wayrapredict.api.dtos.AsistenteDTO;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

//Pregunta al asistente. estacion (opcional): código de la estación que el usuario está viendo, para responder
//preguntas como "¿cómo estará mañana?". historial (opcional): intervenciones anteriores (se usan las últimas 6).
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PreguntaAsistenteDto {
    @NotBlank
    @Size(max = 500)
    private String pregunta;

    @Size(max = 20)
    private String estacion;

    @Valid
    @Size(max = 20)
    private List<MensajeAsistenteDto> historial = new ArrayList<>();
}
