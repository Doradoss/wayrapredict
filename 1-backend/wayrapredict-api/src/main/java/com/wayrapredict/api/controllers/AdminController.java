package com.wayrapredict.api.controllers;

import com.wayrapredict.api.dtos.EjecucionDTO.EjecucionDto;
import com.wayrapredict.api.dtos.UsuarioDTO.CambioRolDto;
import com.wayrapredict.api.dtos.UsuarioDTO.UsuarioDto;
import com.wayrapredict.api.serviceinterfaces.EjecucionService;
import com.wayrapredict.api.serviceinterfaces.UsuarioService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@CrossOrigin
@RestController
@RequestMapping("/api/admin")
@SecurityRequirement(name = "bearerAuth")
@Tag(name = "Administración", description = "Cuentas, roles y ejecuciones del proceso (rol administrador)")
public class AdminController {
    final UsuarioService usuarioService;
    final EjecucionService ejecucionService;

    public AdminController(UsuarioService usuarioService, EjecucionService ejecucionService) {
        this.usuarioService = usuarioService;
        this.ejecucionService = ejecucionService;
    }

    //Listar usuarios (opcionalmente por estado)
    @Operation(summary = "Lista los usuarios; filtro opcional por estado")
    @GetMapping("/usuarios")
    public ResponseEntity<List<UsuarioDto>> usuarios(
            @Parameter(description = "pendiente | aprobado | rechazado") @RequestParam(required = false) String estado) {
        return ResponseEntity.ok(usuarioService.findAll(estado));
    }

    //Aprobar una cuenta
    @Operation(summary = "Aprueba una cuenta (registra el administrador y la fecha)")
    @PutMapping("/aprobar-usuario/{id}")
    public ResponseEntity<UsuarioDto> aprobar(@PathVariable Integer id, Authentication autenticacion) {
        return ResponseEntity.ok(usuarioService.aprobar(id, autenticacion.getName()));
    }

    //Rechazar una cuenta
    @Operation(summary = "Rechaza una solicitud o revoca una cuenta aprobada")
    @PutMapping("/rechazar-usuario/{id}")
    public ResponseEntity<UsuarioDto> rechazar(@PathVariable Integer id, Authentication autenticacion) {
        return ResponseEntity.ok(usuarioService.rechazar(id, autenticacion.getName()));
    }

    //Cambiar el rol de un usuario
    @Operation(summary = "Cambia el rol de un usuario (administrador | usuario_institucional)")
    @PutMapping("/cambiar-rol/{id}")
    public ResponseEntity<UsuarioDto> cambiarRol(@PathVariable Integer id, @Valid @RequestBody CambioRolDto dto,
                                                 Authentication autenticacion) {
        return ResponseEntity.ok(usuarioService.cambiarRol(id, dto.getRol(), autenticacion.getName()));
    }

    //Estado de las ejecuciones del proceso
    @Operation(summary = "Estado de las ejecuciones del proceso de carga y predicción")
    @GetMapping("/ejecuciones")
    public ResponseEntity<List<EjecucionDto>> ejecuciones() {
        return ResponseEntity.ok(ejecucionService.findAll());
    }
}
