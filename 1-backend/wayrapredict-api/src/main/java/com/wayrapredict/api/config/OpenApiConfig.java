package com.wayrapredict.api.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

//Documentación OpenAPI (Swagger UI en /doc/swagger-ui/index.html) con el botón "Authorize" para el token JWT
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI wayraOpenApi() {
        return new OpenAPI()
                .info(new Info().title("WayraPredict API").version("v1")
                        .description("API de la plataforma WayraPredict: estaciones, mediciones diarias, predicciones de " +
                                "calidad del aire (INCA), alertas, métricas de los modelos y administración de cuentas. " +
                                "Las rutas /api/libre/** son públicas; para las demás, inicie sesión en /authenticate y " +
                                "use el token en 'Authorize'."))
                .components(new Components().addSecuritySchemes("bearerAuth",
                        new SecurityScheme().type(SecurityScheme.Type.HTTP).scheme("bearer").bearerFormat("JWT")));
    }
}
