package com.wayrapredict.api.controllers;

import com.wayrapredict.api.dtos.UsuarioDTO.SolicitudCuentaDto;
import com.wayrapredict.api.dtos.UsuarioDTO.UsuarioDto;
import com.wayrapredict.api.serviceinterfaces.UsuarioService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@CrossOrigin
@RestController
@Tag(name = "Cuenta", description = "Solicitud de cuenta (pública) y perfil del usuario que inició sesión")
public class UsuarioController {
    final UsuarioService usuarioService;

    public UsuarioController(UsuarioService usuarioService) {
        this.usuarioService = usuarioService;
    }

    //Solicitar cuenta (sin login): queda pendiente de aprobación
    @Operation(summary = "Solicita una cuenta de usuario institucional (queda en estado 'pendiente')")
    @PostMapping("/api/libre/solicitar-cuenta")
    public ResponseEntity<UsuarioDto> solicitarCuenta(@Valid @RequestBody SolicitudCuentaDto dto) {
        return new ResponseEntity<>(usuarioService.solicitarCuenta(dto), HttpStatus.CREATED);
    }

    //Perfil del usuario autenticado (cualquier rol)
    @Operation(summary = "Perfil del usuario que inició sesión", security = @SecurityRequirement(name = "bearerAuth"))
    @GetMapping("/api/cuenta/mi-perfil")
    public ResponseEntity<UsuarioDto> miPerfil(Authentication autenticacion) {
        return ResponseEntity.ok(usuarioService.perfil(autenticacion.getName()));
    }
}
