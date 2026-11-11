package com.wayrapredict.api.dtos.AsistenteDTO;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

//Una intervención anterior de la conversación (memoria): la guarda el navegador mientras el panel está abierto
@Data
@NoArgsConstructor
@AllArgsConstructor
public class MensajeAsistenteDto {
    @NotBlank
    @Pattern(regexp = "usuario|asistente", message = "debe ser 'usuario' o 'asistente'")
    private String rol;

    @NotBlank
    @Size(max = 2000)
    private String texto;
}
