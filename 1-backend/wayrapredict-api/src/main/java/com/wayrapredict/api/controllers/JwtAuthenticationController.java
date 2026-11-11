package com.wayrapredict.api.controllers;

import com.wayrapredict.api.entities.Usuario;
import com.wayrapredict.api.repositories.UsuarioRepository;
import com.wayrapredict.api.securities.JwtRequest;
import com.wayrapredict.api.securities.JwtResponse;
import com.wayrapredict.api.securities.JwtTokenUtil;
import com.wayrapredict.api.serviceimplements.JwtUserDetailsService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.DisabledException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

//Clase 3 (como en la plantilla): POST /authenticate -> token JWT.
//Cambios: credenciales con @Valid; errores 401/403 en JSON en español en lugar de una excepción genérica
//(credenciales incorrectas, cuenta pendiente o rechazada).
@CrossOrigin
@RestController
@Tag(name = "Autenticación", description = "Inicio de sesión con correo y contraseña")
public class JwtAuthenticationController {
    final AuthenticationManager authenticationManager;
    final JwtTokenUtil jwtTokenUtil;
    final JwtUserDetailsService userDetailsService;
    final UsuarioRepository usuarioRepository;

    public JwtAuthenticationController(AuthenticationManager authenticationManager, JwtTokenUtil jwtTokenUtil,
                                       JwtUserDetailsService userDetailsService, UsuarioRepository usuarioRepository) {
        this.authenticationManager = authenticationManager;
        this.jwtTokenUtil = jwtTokenUtil;
        this.userDetailsService = userDetailsService;
        this.usuarioRepository = usuarioRepository;
    }

    @Operation(summary = "Inicia sesión con correo y contraseña; solo las cuentas aprobadas reciben un token")
    @PostMapping("/authenticate")
    public ResponseEntity<?> createAuthenticationToken(@Valid @RequestBody JwtRequest request) {
        try {
            authenticationManager.authenticate(new UsernamePasswordAuthenticationToken(request.getCorreo(), request.getPassword()));
        } catch (DisabledException e) {
            String estado = usuarioRepository.findByCorreoIgnoreCase(request.getCorreo()).map(Usuario::getEstado).orElse("");
            String mensaje = Usuario.ESTADO_RECHAZADO.equals(estado) ? "La solicitud de cuenta fue rechazada"
                    : "La cuenta está pendiente de aprobación por un administrador";
            return error(HttpStatus.FORBIDDEN, mensaje);
        } catch (BadCredentialsException e) {
            return error(HttpStatus.UNAUTHORIZED, "Correo o contraseña incorrectos");
        }
        final UserDetails userDetails = userDetailsService.loadUserByUsername(request.getCorreo());
        Usuario usuario = usuarioRepository.findByCorreoIgnoreCase(request.getCorreo()).orElseThrow();
        final String token = jwtTokenUtil.generateToken(userDetails, usuario.getNombres() + " " + usuario.getApellidos());
        return ResponseEntity.ok(new JwtResponse(token, usuario.getCorreo(), usuario.getRol(),
                usuario.getNombres() + " " + usuario.getApellidos(), jwtTokenUtil.getValidezMs()));
    }

    private ResponseEntity<Map<String, Object>> error(HttpStatus estado, String mensaje) {
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("fecha", LocalDateTime.now());
        cuerpo.put("estado", estado.value());
        cuerpo.put("error", estado.getReasonPhrase());
        cuerpo.put("mensaje", mensaje);
        return ResponseEntity.status(estado).body(cuerpo);
    }
}
