package com.wayrapredict.api.controllers;

import com.wayrapredict.api.dtos.PrediccionDTO.PrediccionDto;
import com.wayrapredict.api.serviceinterfaces.PrediccionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@CrossOrigin
@RestController
@RequestMapping("/api/institucional")
@SecurityRequirement(name = "bearerAuth")
@Tag(name = "Usuario institucional", description = "Verificación de predicciones (rol usuario_institucional)")
public class InstitucionalController {
    final PrediccionService prediccionService;

    public InstitucionalController(PrediccionService prediccionService) {
        this.prediccionService = prediccionService;
    }

    //Predicciones de una estación que aún no se verificaron (con el valor observado)
    @Operation(summary = "Predicciones pasadas de una estación pendientes de verificar, con el valor observado")
    @GetMapping("/predicciones-por-verificar/{codigo}")
    public ResponseEntity<List<PrediccionDto>> porVerificar(
            @PathVariable String codigo,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate desde,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate hasta) {
        return ResponseEntity.ok(prediccionService.porVerificar(codigo, desde, hasta));
    }

    //Verificar una predicción (registra el usuario y la fecha)
    @Operation(summary = "Marca una predicción como verificada por el usuario que inició sesión")
    @PutMapping("/verificar-prediccion/{id}")
    public ResponseEntity<PrediccionDto> verificar(@PathVariable Long id, Authentication autenticacion) {
        return ResponseEntity.ok(prediccionService.verificar(id, autenticacion.getName()));
    }
}
