package com.wayrapredict.api.controllers;

import com.wayrapredict.api.dtos.ModeloDTO.MetricaModeloDto;
import com.wayrapredict.api.dtos.PrediccionDTO.PrediccionDto;
import com.wayrapredict.api.serviceinterfaces.ModeloService;
import com.wayrapredict.api.serviceinterfaces.PrediccionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@CrossOrigin
@RestController
@RequestMapping("/api/libre")
@Tag(name = "Predicciones y modelos (público)", description = "Pronóstico de los próximos días, historial y métricas")
public class PrediccionController {
    final PrediccionService prediccionService;
    final ModeloService modeloService;

    public PrediccionController(PrediccionService prediccionService, ModeloService modeloService) {
        this.prediccionService = prediccionService;
        this.modeloService = modeloService;
    }

    //Próximos días desde el último dato medido de la estación
    @Operation(summary = "Pronóstico de los próximos días desde la fecha de referencia de la estación",
            description = "Predicciones de la última ejecución (modelo vigente o su respaldo), con la versión del modelo")
    @GetMapping("/predicciones-proximos-dias/{codigo}")
    public ResponseEntity<List<PrediccionDto>> proximosDias(@PathVariable String codigo) {
        return ResponseEntity.ok(prediccionService.proximosDias(codigo));
    }

    //Historial de predicciones con el valor observado
    @Operation(summary = "Historial de predicciones (hasta la fecha de referencia) con el valor observado")
    @GetMapping("/predicciones-historial/{codigo}")
    public ResponseEntity<List<PrediccionDto>> historial(
            @PathVariable String codigo,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate desde,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate hasta) {
        return ResponseEntity.ok(prediccionService.historial(codigo, desde, hasta));
    }

    //Métricas del modelo vigente ("Desempeño del modelo")
    @Operation(summary = "Métricas del modelo vigente de cada estación (RMSE, MAE y R² de la prueba a 1 día)")
    @GetMapping("/metricas-modelo-vigente")
    public ResponseEntity<List<MetricaModeloDto>> metricasVigente(@RequestParam(required = false) String estacion) {
        return ResponseEntity.ok(modeloService.metricas(estacion, true));
    }

    //Métricas de todas las versiones (vigente y respaldo)
    @Operation(summary = "Métricas de todas las versiones de modelo (vigente y respaldo)")
    @GetMapping("/metricas-modelos")
    public ResponseEntity<List<MetricaModeloDto>> metricasTodas(@RequestParam(required = false) String estacion) {
        return ResponseEntity.ok(modeloService.metricas(estacion, false));
    }
}
