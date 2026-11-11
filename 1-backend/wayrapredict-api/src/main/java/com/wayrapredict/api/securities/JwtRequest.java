package com.wayrapredict.api.securities;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

//Clase 4 (como en la plantilla): datos del login. El correo funciona como nombre de usuario.
@Data
@NoArgsConstructor
@AllArgsConstructor
public class JwtRequest {
    @NotBlank
    @Email
    private String correo;
    @NotBlank
    private String password;
}
