package com.wayrapredict.api.util;

//Petición válida en forma pero no permitida por las reglas del negocio (p. ej. correo ya registrado,
//predicción ya verificada): el manejador global responde 409
public class ReglaNegocioException extends RuntimeException {
    public ReglaNegocioException(String mensaje) {
        super(mensaje);
    }
}
