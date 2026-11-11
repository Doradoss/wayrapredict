package com.wayrapredict.api.controllers;

import com.wayrapredict.api.dtos.AsistenteDTO.PreguntaAsistenteDto;
import com.wayrapredict.api.dtos.AsistenteDTO.RespuestaAsistenteDto;
import com.wayrapredict.api.serviceinterfaces.AsistenteService;
import com.wayrapredict.api.util.ServicioNoDisponibleException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.PreDestroy;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@CrossOrigin
@RestController
@RequestMapping("/api/libre")
@Tag(name = "Asistente (público)", description = "Asistente conversacional con Gemini sobre la calidad del aire")
public class AsistenteController {
    private static final Logger log = LoggerFactory.getLogger(AsistenteController.class);

    final AsistenteService asistenteService;
    //Hilos para las respuestas por partes (cada pregunta ocupa uno mientras Gemini responde)
    private final ExecutorService hilos = Executors.newFixedThreadPool(16);

    public AsistenteController(AsistenteService asistenteService) {
        this.asistenteService = asistenteService;
    }

    //Pregunta al asistente (sin login). La memoria de la conversación llega en "historial".
    @Operation(summary = "Pregunta al asistente de calidad del aire (respuesta completa)",
            description = "Responde con los datos reales de la plataforma (estaciones, pronóstico de 1 a 3 días, alertas e INCA). "
                    + "Límite de preguntas por minuto por cliente (429). Si Gemini no responde: 503.")
    @PostMapping("/asistente")
    public ResponseEntity<RespuestaAsistenteDto> preguntar(@Valid @RequestBody PreguntaAsistenteDto dto, HttpServletRequest request) {
        return ResponseEntity.ok(asistenteService.preguntar(dto, cliente(request)));
    }

    //Igual que el anterior, pero la respuesta llega por partes (Server-Sent Events) mientras Gemini la escribe:
    // event "texto" {t}: fragmento de texto · event "fin" {modelo, fechaDatos} · event "error" {mensaje}
    @Operation(summary = "Pregunta al asistente con la respuesta por partes (text/event-stream)",
            description = "Eventos: 'texto' con cada fragmento ({\"t\": ...}), 'fin' ({\"modelo\", \"fechaDatos\"}) o 'error' ({\"mensaje\"}). "
                    + "Los errores de validación (400), estación inexistente (404) y límite por minuto (429) se responden antes, en JSON.")
    @PostMapping(value = "/asistente/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter preguntarEnVivo(@Valid @RequestBody PreguntaAsistenteDto dto, HttpServletRequest request) {
        //Validación, límite y contexto ANTES de abrir el stream: así los errores 400/404/429 salen como JSON normal
        AsistenteService.PreguntaPreparada preparada = asistenteService.preparar(dto, cliente(request));
        SseEmitter emisor = new SseEmitter(120_000L);
        hilos.execute(() -> {
            try {
                RespuestaAsistenteDto r = asistenteService.responder(preparada, fragmento -> enviar(emisor, "texto", Map.of("t", fragmento)));
                Map<String, Object> fin = new LinkedHashMap<>();
                fin.put("modelo", r.getModelo());
                fin.put("fechaDatos", r.getFechaDatos() == null ? null : r.getFechaDatos().toString());
                enviar(emisor, "fin", fin);
                emisor.complete();
            } catch (ClienteDesconectado e) {
                emisor.complete();
            } catch (ServicioNoDisponibleException e) {
                enviarError(emisor, e.getMessage());
            } catch (RuntimeException e) {
                log.warn("Error en la respuesta por partes del asistente: {}", e.getClass().getSimpleName());
                enviarError(emisor, "No pude responder en este momento. Inténtalo de nuevo.");
            }
        });
        return emisor;
    }

    //El navegador cerró la conexión (por ejemplo, cerró el panel)
    private static class ClienteDesconectado extends RuntimeException {}

    private static void enviar(SseEmitter emisor, String evento, Object datos) {
        try {
            emisor.send(SseEmitter.event().name(evento).data(datos, MediaType.APPLICATION_JSON));
        } catch (IOException | IllegalStateException e) {
            throw new ClienteDesconectado();
        }
    }

    private static void enviarError(SseEmitter emisor, String mensaje) {
        try {
            enviar(emisor, "error", Map.of("mensaje", mensaje));
            emisor.complete();
        } catch (ClienteDesconectado ignorado) {
            emisor.complete();
        }
    }

    @PreDestroy
    void cerrar() {
        hilos.shutdownNow();
    }

    //Dirección del cliente (la primera de X-Forwarded-For si hay un proxy delante)
    private static String cliente(HttpServletRequest request) {
        String reenviado = request.getHeader("X-Forwarded-For");
        if (reenviado != null && !reenviado.isBlank()) {
            return reenviado.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}
