package com.wayrapredict.api.securities;

import lombok.AllArgsConstructor;
import lombok.Getter;

//Clase 5 (como en la plantilla): respuesta del login con el token.
//Cambio: además del token devuelve el correo, el rol, el nombre y la validez (ms), para que el frontend
//no tenga que decodificar el token.
@Getter
@AllArgsConstructor
public class JwtResponse {
    private final String jwttoken;
    private final String correo;
    private final String rol;
    private final String nombre;
    private final long validezMs;
}
