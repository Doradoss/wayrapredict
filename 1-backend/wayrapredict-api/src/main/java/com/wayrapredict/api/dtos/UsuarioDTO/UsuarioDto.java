package com.wayrapredict.api.dtos.UsuarioDTO;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

//Datos de un usuario para mostrar (nunca incluye la contraseña ni su hash)
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UsuarioDto {
    private Integer idUsuario;
    private String nombres;
    private String apellidos;
    private String correo;
    private String institucion;
    private String cargo;
    private String rol;
    private String estado;
    private LocalDateTime fechaRegistro;
    private String aprobadoPor;
    private LocalDateTime fechaAprobacion;
}
