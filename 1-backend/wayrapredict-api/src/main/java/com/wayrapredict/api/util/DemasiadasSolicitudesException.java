package com.wayrapredict.api.util;

//Se superó el límite de solicitudes por minuto (p. ej. preguntas al asistente): el manejador global responde 429
public class DemasiadasSolicitudesException extends RuntimeException {
    public DemasiadasSolicitudesException(String mensaje) {
        super(mensaje);
    }
}
