package com.wayrapredict.api.controllers;

import com.wayrapredict.api.dtos.CategoriaIncaDTO.CategoriaIncaDto;
import com.wayrapredict.api.dtos.EstacionDTO.EstacionDto;
import com.wayrapredict.api.serviceinterfaces.CategoriaIncaService;
import com.wayrapredict.api.serviceinterfaces.EstacionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@CrossOrigin
@RestController
@RequestMapping("/api/libre")
@Tag(name = "Estaciones (público)", description = "Estaciones, su contaminante y fecha de referencia; leyenda del INCA")
public class EstacionController {
    final EstacionService estacionService;
    final CategoriaIncaService categoriaService;

    public EstacionController(EstacionService estacionService, CategoriaIncaService categoriaService) {
        this.estacionService = estacionService;
        this.categoriaService = categoriaService;
    }

    //Listar todas las estaciones
    @Operation(summary = "Lista las estaciones con su contaminante y su fecha de referencia (último dato medido)")
    @GetMapping("/estaciones")
    public ResponseEntity<List<EstacionDto>> findAll() {
        return ResponseEntity.ok(estacionService.findAll());
    }

    //Estación por código
    @Operation(summary = "Una estación por su código (p. ej. CA-CC-01)")
    @GetMapping("/estacion/{codigo}")
    public ResponseEntity<EstacionDto> findByCodigo(@PathVariable String codigo) {
        return ResponseEntity.ok(estacionService.findByCodigo(codigo));
    }

    //Categorías del INCA (leyenda)
    @Operation(summary = "Categorías del INCA con color y recomendación (leyenda del semáforo)")
    @GetMapping("/categorias-inca")
    public ResponseEntity<List<CategoriaIncaDto>> categorias() {
        return ResponseEntity.ok(categoriaService.findAll());
    }
}
