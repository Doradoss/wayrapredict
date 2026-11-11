package com.wayrapredict.api.util;

//Recurso inexistente (estación, predicción, usuario...): el manejador global responde 404
public class NoEncontradoException extends RuntimeException {
    public NoEncontradoException(String mensaje) {
        super(mensaje);
    }
}
