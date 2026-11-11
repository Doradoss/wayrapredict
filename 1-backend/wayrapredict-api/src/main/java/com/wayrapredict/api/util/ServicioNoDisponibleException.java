package com.wayrapredict.api.util;

//Un servicio externo (p. ej. la API de Gemini) no respondió o no está configurado: el manejador global responde 503
public class ServicioNoDisponibleException extends RuntimeException {
    public ServicioNoDisponibleException(String mensaje) {
        super(mensaje);
    }
}
