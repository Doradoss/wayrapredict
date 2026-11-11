package com.wayrapredict.api.dtos.UsuarioDTO;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

//Solicitud de cuenta (usuario institucional): queda en estado 'pendiente' hasta que un administrador la apruebe.
//El correo debe ser institucional (.gob.pe) y se debe aceptar el tratamiento de datos (Ley N.° 29733); la
//aceptación no se guarda en la base: sin ella la solicitud no se registra.
@Data
@NoArgsConstructor
@AllArgsConstructor
public class SolicitudCuentaDto {
    @NotBlank
    @Size(max = 80)
    private String nombres;
    @NotBlank
    @Size(max = 80)
    private String apellidos;
    @NotBlank
    @Email
    @Pattern(regexp = "(?i)^[^@\\s]+@([a-z0-9-]+\\.)*gob\\.pe$", message = "debe ser un correo institucional que termine en .gob.pe")
    @Size(max = 150)
    private String correo;
    @NotBlank
    @Size(min = 8, max = 72, message = "debe tener entre 8 y 72 caracteres")
    private String password;
    @NotBlank
    @Size(max = 150)
    private String institucion;
    @Size(max = 100)
    private String cargo;
    @NotNull(message = "debe aceptar el tratamiento de datos personales (Ley N.° 29733)")
    @AssertTrue(message = "debe aceptar el tratamiento de datos personales (Ley N.° 29733)")
    private Boolean aceptaTratamientoDatos;
}
