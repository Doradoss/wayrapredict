package com.wayrapredict.api.securities;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;

//Nuevo (no estaba en la plantilla): sesión válida pero rol sin permiso para la ruta -> 403 en JSON
@Component
public class JwtAccessDeniedHandler implements AccessDeniedHandler {

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                       AccessDeniedException accessDeniedException) throws IOException {
        JwtAuthenticationEntryPoint.escribir(response, HttpServletResponse.SC_FORBIDDEN, "Forbidden",
                "Su rol no tiene permiso para esta operación");
    }
}
