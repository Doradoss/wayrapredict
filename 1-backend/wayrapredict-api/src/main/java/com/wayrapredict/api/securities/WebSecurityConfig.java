package com.wayrapredict.api.securities;

import com.wayrapredict.api.entities.Usuario;
import jakarta.servlet.DispatcherType;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;

//Clase S7 (como en la plantilla): reglas de acceso, sesión sin estado, BCrypt y filtro JWT.
//Cambios para Spring Security 7 (Spring Boot 4):
// - DSL con lambdas: csrf(c -> c.disable()), authorizeHttpRequests(...), requestMatchers(...). Los métodos
//   csrf().disable(), authorizeRequests(), antMatchers() y .and() de la plantilla fueron eliminados.
// - @EnableMethodSecurity reemplaza a @EnableGlobalMethodSecurity.
// - Ya no hace falta configureGlobal(AuthenticationManagerBuilder): Spring arma el AuthenticationManager con
//   el único UserDetailsService (JwtUserDetailsService) y el PasswordEncoder declarados como beans.
// - CORS con la configuración nativa de Spring Security (CorsConfigurationSource) en lugar del filtro propio
//   CORS de la plantilla; los orígenes permitidos se leen de WAYRA_CORS_ORIGENES.
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class WebSecurityConfig {

    final JwtAuthenticationEntryPoint jwtAuthenticationEntryPoint;
    final JwtAccessDeniedHandler jwtAccessDeniedHandler;
    final JwtRequestFilter jwtRequestFilter;

    @Value("${wayra.cors.origenes}")
    private String origenesCors;

    public WebSecurityConfig(JwtAuthenticationEntryPoint jwtAuthenticationEntryPoint,
                             JwtAccessDeniedHandler jwtAccessDeniedHandler, JwtRequestFilter jwtRequestFilter) {
        this.jwtAuthenticationEntryPoint = jwtAuthenticationEntryPoint;
        this.jwtAccessDeniedHandler = jwtAccessDeniedHandler;
        this.jwtRequestFilter = jwtRequestFilter;
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration configuration) throws Exception {
        return configuration.getAuthenticationManager();
    }

    @Bean
    public static PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http.csrf(csrf -> csrf.disable())
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        //la página de error de Spring (404, 400...) no debe convertirse en 401
                        .dispatcherTypeMatchers(DispatcherType.ERROR).permitAll()
                        //respuestas por partes del asistente (SseEmitter): el despacho asíncrono no vuelve a autorizarse
                        .dispatcherTypeMatchers(DispatcherType.ASYNC).permitAll()
                        .requestMatchers("/error").permitAll()
                        .requestMatchers("/authenticate").permitAll()
                        .requestMatchers("/api/libre/**").permitAll()
                        .requestMatchers("/doc/**", "/v3/api-docs/**", "/swagger-ui/**").permitAll()
                        .requestMatchers("/api/institucional/**").hasAuthority(Usuario.ROL_INSTITUCIONAL)
                        .requestMatchers("/api/admin/**").hasAuthority(Usuario.ROL_ADMINISTRADOR)
                        .anyRequest().authenticated())
                .exceptionHandling(ex -> ex
                        .authenticationEntryPoint(jwtAuthenticationEntryPoint)
                        .accessDeniedHandler(jwtAccessDeniedHandler))
                .formLogin(form -> form.disable())
                .httpBasic(basic -> basic.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS));

        http.addFilterBefore(jwtRequestFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    //Orígenes del frontend permitidos (separados por coma), métodos y cabeceras
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(Arrays.stream(origenesCors.split(",")).map(String::trim).filter(s -> !s.isEmpty()).toList());
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-Requested-With"));
        config.setMaxAge(3600L);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
