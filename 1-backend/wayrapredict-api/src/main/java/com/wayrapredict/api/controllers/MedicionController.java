package com.wayrapredict.api.controllers;

import com.wayrapredict.api.dtos.MedicionDTO.MedicionDto;
import com.wayrapredict.api.dtos.MedicionDTO.SerieDiariaDto;
import com.wayrapredict.api.serviceinterfaces.MedicionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

@CrossOrigin
@RestController
@RequestMapping("/api/libre")
@Tag(name = "Mediciones (público)", description = "Mediciones diarias con su origen: gráfico y tooltip con meteorología")
public class MedicionController {
    final MedicionService medicionService;

    public MedicionController(MedicionService medicionService) {
        this.medicionService = medicionService;
    }

    //Serie diaria de una estación (contaminante + meteorología, con origen de cada valor)
    @Operation(summary = "Serie diaria para el gráfico: contaminante y meteorología con el origen de cada valor",
            description = "Por defecto: 90 días hasta la fecha de referencia y los días siguientes con meteorología pronosticada")
    @GetMapping("/serie-diaria/{codigo}")
    public ResponseEntity<List<SerieDiariaDto>> serieDiaria(
            @PathVariable String codigo,
            @Parameter(description = "Fecha inicial (AAAA-MM-DD)") @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate desde,
            @Parameter(description = "Fecha final (AAAA-MM-DD)") @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate hasta) {
        return ResponseEntity.ok(medicionService.serieDiaria(codigo, desde, hasta));
    }

    //Mediciones en formato largo (una fila por variable y día)
    @Operation(summary = "Mediciones en formato largo (una fila por variable y día), opcionalmente de una variable")
    @GetMapping("/mediciones/{codigo}")
    public ResponseEntity<List<MedicionDto>> mediciones(
            @PathVariable String codigo,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate desde,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate hasta,
            @Parameter(description = "Código de variable: SO2, PM10, TEMPERATURA, HUMEDAD_RELATIVA, VELOCIDAD_VIENTO, " +
                    "DIRECCION_VIENTO, PRESION_BAROMETRICA, PRECIPITACION") @RequestParam(required = false) String variable) {
        return ResponseEntity.ok(medicionService.mediciones(codigo, desde, hasta, variable));
    }
}
