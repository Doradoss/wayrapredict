package com.wayrapredict.api.securities;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.LocalDateTime;

//Clase 7 (como en la plantilla): sin token válido en una ruta protegida -> 401.
//Cambio: responde JSON en español con el mismo formato que el manejador de errores.
@Component
public class JwtAuthenticationEntryPoint implements AuthenticationEntryPoint {

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
                         AuthenticationException authException) throws IOException {
        escribir(response, HttpServletResponse.SC_UNAUTHORIZED, "Unauthorized",
                "Debe iniciar sesión (token JWT ausente, inválido o expirado)");
    }

    static void escribir(HttpServletResponse response, int estado, String error, String mensaje) throws IOException {
        response.setStatus(estado);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"fecha\":\"" + LocalDateTime.now() + "\",\"estado\":" + estado +
                ",\"error\":\"" + error + "\",\"mensaje\":\"" + mensaje + "\"}");
    }
}
