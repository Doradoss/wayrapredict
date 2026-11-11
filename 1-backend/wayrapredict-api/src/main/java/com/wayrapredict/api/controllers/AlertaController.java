package com.wayrapredict.api.controllers;

import com.wayrapredict.api.dtos.AlertaDTO.AlertaDto;
import com.wayrapredict.api.serviceinterfaces.AlertaService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@CrossOrigin
@RestController
@RequestMapping("/api/libre")
@Tag(name = "Alertas (público)", description = "Predicciones de categoría Moderada o superior (vista v_alerta)")
public class AlertaController {
    final AlertaService alertaService;

    public AlertaController(AlertaService alertaService) {
        this.alertaService = alertaService;
    }

    //Listar alertas (opcionalmente por estación y estado)
    @Operation(summary = "Alertas por estación y estado (vigente = posterior a la fecha de referencia)")
    @GetMapping("/alertas")
    public ResponseEntity<List<AlertaDto>> alertas(
            @Parameter(description = "Código de la estación") @RequestParam(required = false) String estacion,
            @Parameter(description = "vigente | finalizada") @RequestParam(required = false) String estado) {
        return ResponseEntity.ok(alertaService.buscar(estacion, estado));
    }
}
