package com.wayrapredict.api.dtos.UsuarioDTO;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

//Nuevo rol de un usuario
@Data
@NoArgsConstructor
@AllArgsConstructor
public class CambioRolDto {
    @NotBlank
    @Pattern(regexp = "administrador|usuario_institucional", message = "debe ser 'administrador' o 'usuario_institucional'")
    private String rol;
}
