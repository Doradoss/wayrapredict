package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.util.ServicioNoDisponibleException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import tools.jackson.databind.json.JsonMapper;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

//Cliente de la API de Gemini (Interactions API, POST /v1beta/interactions?alt=sse) sin SDK.
// - La clave se lee SOLO de la variable de entorno WAYRA_GEMINI_API_KEY y viaja en la cabecera x-goog-api-key.
// - store=false: Google no guarda la conversación; la memoria la envía el frontend en cada pregunta.
// - La respuesta llega por partes (stream): cada fragmento de texto se entrega apenas llega (alFragmento), para que el
//   usuario vea la respuesta mientras se escribe.
// - Rapidez: si un modelo no empieza a responder dentro de un límite (8 s el principal, 15 s los respaldos) o responde
//   429/5xx, se pasa al siguiente modelo SIN reintentar el mismo. Tras un fallo del principal, durante el minuto siguiente
//   se va directo al respaldo. Una vez que empezó a llegar texto ya no se cambia de modelo.
// - Razonamiento ("thinking") mínimo por defecto: reduce mucho el tiempo hasta la primera palabra. Si un modelo no admite
//   ese nivel, se reintenta una sola vez con "low" y se recuerda para las siguientes preguntas.
// - El log registra modelo, estado, tiempos y tokens, nunca el texto de las preguntas.
@Service
public class GeminiService {
    private static final Logger log = LoggerFactory.getLogger(GeminiService.class);
    private static final Set<Integer> TRANSITORIOS = Set.of(408, 429, 500, 502, 503, 504);
    private static final JsonMapper JSON = JsonMapper.builder().build();

    //Intervención de la conversación: rol "usuario" o "asistente"
    public record Turno(String rol, String texto) {}

    //Texto generado y modelo que respondió
    public record Resultado(String texto, String modelo) {}

    //Resultado de una transmisión: texto completo, estado final y uso de tokens
    public record Transmision(String texto, String estado, Map<?, ?> uso, long msPrimerTexto) {}

    //Gemini respondió con un código de error HTTP
    public static class ErrorGemini extends RuntimeException {
        final int estado;
        final String cuerpo;

        public ErrorGemini(int estado, String cuerpo) {
            super("Gemini respondió " + estado);
            this.estado = estado;
            this.cuerpo = cuerpo == null ? "" : cuerpo;
        }
    }

    //El modelo no empezó a responder (o no terminó) dentro del tiempo permitido
    public static class SinRespuestaATiempo extends RuntimeException {
        public SinRespuestaATiempo(String mensaje) {
            super(mensaje);
        }
    }

    @Value("${wayra.gemini.api-key:}")
    private String apiKey;
    @Value("${wayra.gemini.url:https://generativelanguage.googleapis.com/v1beta/interactions}")
    private String url;
    @Value("${wayra.gemini.modelo:gemini-3.6-flash}")
    private String modelo;
    //Uno o más modelos de respaldo, separados por coma, en orden de preferencia
    @Value("${wayra.gemini.modelo-respaldo:gemini-3.6-flash,gemini-3.5-flash-lite}")
    private String modeloRespaldo;
    @Value("${wayra.gemini.api-revision:2026-05-20}")
    private String apiRevision;
    //Nivel de razonamiento: minimal (más rápido), low, medium o high
    @Value("${wayra.gemini.razonamiento:minimal}")
    private String razonamiento;
    @Value("${wayra.gemini.primer-texto-principal-ms:8000}")
    private long primerTextoPrincipalMs;
    @Value("${wayra.gemini.primer-texto-respaldo-ms:15000}")
    private long primerTextoRespaldoMs;
    @Value("${wayra.gemini.timeout-segundos:45}")
    private int timeoutSegundos;
    @Value("${wayra.gemini.max-tokens:2048}")
    private int maxTokens;
    @Value("${wayra.gemini.pausa-principal-ms:60000}")
    private long pausaPrincipalMs;

    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    private final ScheduledExecutorService vigilante = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "gemini-vigilante");
        t.setDaemon(true);
        return t;
    });
    //Modelos que no admiten el razonamiento configurado (se usa "low" con ellos)
    private final Map<String, String> razonamientoPorModelo = new ConcurrentHashMap<>();
    //Momento del último fallo pasajero del modelo principal: durante la pausa se va directo al respaldo
    private volatile long ultimoFalloPrincipal = 0;

    public boolean configurado() {
        return apiKey != null && !apiKey.isBlank();
    }

    //Genera la respuesta completa (sin ir mostrando el texto)
    public Resultado generar(String instrucciones, List<Turno> conversacion) {
        return generar(instrucciones, conversacion, fragmento -> {});
    }

    //Genera la respuesta entregando cada fragmento de texto apenas llega
    public Resultado generar(String instrucciones, List<Turno> conversacion, Consumer<String> alFragmento) {
        if (!configurado()) {
            throw new ServicioNoDisponibleException("El asistente no está configurado en el servidor");
        }
        List<String> respaldos = respaldos();
        boolean principalEnPausa = !respaldos.isEmpty() && System.currentTimeMillis() - ultimoFalloPrincipal < pausaPrincipalMs;
        List<String> modelos = new ArrayList<>();
        if (!principalEnPausa) {
            modelos.add(modelo);
        }
        modelos.addAll(respaldos);

        for (int i = 0; i < modelos.size(); i++) {
            String m = modelos.get(i);
            boolean esPrincipal = m.equals(modelo);
            String nivel = razonamientoPorModelo.getOrDefault(m, razonamiento);
            AtomicBoolean empezo = new AtomicBoolean(false);
            long inicio = System.currentTimeMillis();
            try {
                Transmision t = transmitir(cuerpo(m, nivel, instrucciones, conversacion), fragmento -> {
                    empezo.set(true);
                    alFragmento.accept(fragmento);
                }, esPrincipal ? primerTextoPrincipalMs : primerTextoRespaldoMs);
                log.info("Gemini {} respondió: primer texto en {} ms, total {} ms (estado {}, tokens {})", m, t.msPrimerTexto(),
                        System.currentTimeMillis() - inicio, t.estado(), resumenUso(t.uso()));
                if (t.texto().isBlank()) {
                    throw new ServicioNoDisponibleException("El asistente no generó una respuesta. Inténtalo de nuevo.");
                }
                return new Resultado(t.texto().strip(), m);
            } catch (ErrorGemini e) {
                log.warn("Gemini {} respondió {} en {} ms", m, e.estado, System.currentTimeMillis() - inicio);
                if (e.estado == 400 && e.cuerpo.toLowerCase(Locale.ROOT).contains("thinking level") && !"low".equals(nivel)) {
                    //Este modelo no admite el nivel de razonamiento pedido: se repite una vez con "low"
                    razonamientoPorModelo.put(m, "low");
                    i--;
                    continue;
                }
                if (e.estado == 402) {
                    throw new ServicioNoDisponibleException("El asistente no está disponible: se agotó el saldo de la API de Gemini");
                }
                if (!TRANSITORIOS.contains(e.estado)) {
                    //400/401/403/404: problema de configuración (clave o modelo); no tiene sentido probar otro modelo
                    throw new ServicioNoDisponibleException("El asistente no está disponible por un problema de configuración del servidor");
                }
                if (esPrincipal) {
                    ultimoFalloPrincipal = System.currentTimeMillis();
                }
            } catch (SinRespuestaATiempo e) {
                log.warn("Gemini {} sin respuesta a tiempo ({} ms): {}", m, System.currentTimeMillis() - inicio, e.getMessage());
                if (esPrincipal) {
                    ultimoFalloPrincipal = System.currentTimeMillis();
                }
            }
            if (empezo.get()) {
                //Ya se mostró parte de la respuesta: no se puede cambiar de modelo a mitad
                throw new ServicioNoDisponibleException("La respuesta se interrumpió. Inténtalo de nuevo.");
            }
        }
        throw new ServicioNoDisponibleException("El asistente no está disponible en este momento por alta demanda. Inténtalo de nuevo en unos minutos.");
    }

    private Map<String, Object> cuerpo(String m, String nivel, String instrucciones, List<Turno> conversacion) {
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("max_output_tokens", maxTokens);
        if (nivel != null && !nivel.isBlank()) {
            config.put("thinking_level", nivel);
        }
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("model", m);
        cuerpo.put("store", false);
        cuerpo.put("stream", true);
        cuerpo.put("system_instruction", instrucciones);
        cuerpo.put("generation_config", config);
        cuerpo.put("input", conversacion.stream().map(GeminiService::paso).toList());
        return cuerpo;
    }

    //Envío HTTP con la respuesta por partes (Server-Sent Events). Separado para poder simularlo en las pruebas.
    // - Si no llega la primera parte de texto en limitePrimerTextoMs, se corta la conexión (SinRespuestaATiempo).
    // - La respuesta completa tiene un máximo de timeoutSegundos.
    protected Transmision transmitir(Map<String, Object> cuerpo, Consumer<String> alFragmento, long limitePrimerTextoMs) {
        HttpRequest peticion = HttpRequest.newBuilder(URI.create(url + "?alt=sse"))
                .timeout(Duration.ofMillis(limitePrimerTextoMs))
                .header("Content-Type", "application/json")
                .header("x-goog-api-key", apiKey)
                .header("Api-Revision", apiRevision)
                .POST(HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(cuerpo), StandardCharsets.UTF_8))
                .build();
        long inicio = System.currentTimeMillis();
        HttpResponse<InputStream> respuesta;
        try {
            respuesta = http.send(peticion, HttpResponse.BodyHandlers.ofInputStream());
        } catch (IOException e) {
            throw new SinRespuestaATiempo("sin respuesta del servidor: " + e.getClass().getSimpleName());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SinRespuestaATiempo("interrumpido");
        }
        if (respuesta.statusCode() != 200) {
            String error;
            try (InputStream in = respuesta.body()) {
                error = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            } catch (IOException e) {
                error = "";
            }
            throw new ErrorGemini(respuesta.statusCode(), error);
        }

        AtomicBoolean recibido = new AtomicBoolean(false);
        AtomicBoolean cortado = new AtomicBoolean(false);
        InputStream flujo = respuesta.body();
        Runnable cortar = () -> {
            cortado.set(true);
            try {
                flujo.close();
            } catch (IOException ignorado) {
                //la conexión ya estaba cerrada
            }
        };
        ScheduledFuture<?> perroPrimerTexto = vigilante.schedule(() -> {
            if (!recibido.get()) cortar.run();
        }, Math.max(0, limitePrimerTextoMs - (System.currentTimeMillis() - inicio)), TimeUnit.MILLISECONDS);
        ScheduledFuture<?> perroTotal = vigilante.schedule(cortar, timeoutSegundos, TimeUnit.SECONDS);

        StringBuilder texto = new StringBuilder();
        String estado = null;
        Map<?, ?> uso = null;
        long msPrimerTexto = -1;
        try (BufferedReader lector = new BufferedReader(new InputStreamReader(flujo, StandardCharsets.UTF_8))) {
            String linea;
            while ((linea = lector.readLine()) != null) {
                if (!linea.startsWith("data:")) {
                    continue;          //"event: ...", comentarios ": keep-alive" y líneas vacías
                }
                String dato = linea.substring(5).trim();
                if (dato.isEmpty()) continue;
                if (dato.equals("[DONE]")) break;
                Map<?, ?> evento = JSON.readValue(dato, Map.class);
                Object tipo = evento.get("event_type");
                if (evento.get("error") instanceof Map<?, ?> err) {
                    Object codigo = err.get("code");
                    throw new ErrorGemini(codigo instanceof Number n ? n.intValue() : 503, String.valueOf(err.get("message")));
                }
                if ("step.delta".equals(tipo) && evento.get("delta") instanceof Map<?, ?> delta
                        && "text".equals(delta.get("type")) && delta.get("text") instanceof String fragmento && !fragmento.isEmpty()) {
                    if (!recibido.getAndSet(true)) {
                        msPrimerTexto = System.currentTimeMillis() - inicio;
                    }
                    texto.append(fragmento);
                    alFragmento.accept(fragmento);
                } else if ("interaction.completed".equals(tipo) && evento.get("interaction") instanceof Map<?, ?> interaccion) {
                    estado = String.valueOf(interaccion.get("status"));
                    uso = interaccion.get("usage") instanceof Map<?, ?> u ? u : null;
                }
            }
        } catch (IOException e) {
            if (cortado.get() && !recibido.get()) {
                throw new SinRespuestaATiempo("no empezó a responder en " + limitePrimerTextoMs + " ms");
            }
            throw new SinRespuestaATiempo(cortado.get() ? "superó " + timeoutSegundos + " s" : "conexión interrumpida");
        } finally {
            perroPrimerTexto.cancel(false);
            perroTotal.cancel(false);
        }
        if (!recibido.get() && cortado.get()) {
            throw new SinRespuestaATiempo("no empezó a responder en " + limitePrimerTextoMs + " ms");
        }
        return new Transmision(texto.toString(), estado, uso, msPrimerTexto);
    }

    private List<String> respaldos() {
        if (modeloRespaldo == null || modeloRespaldo.isBlank()) {
            return List.of();
        }
        return Arrays.stream(modeloRespaldo.split(",")).map(String::trim).filter(x -> !x.isEmpty() && !x.equals(modelo)).distinct().toList();
    }

    //Paso de la Interactions API: user_input o model_output con su contenido de texto
    private static Map<String, Object> paso(Turno t) {
        String tipo = "asistente".equals(t.rol()) ? "model_output" : "user_input";
        return Map.of("type", tipo, "content", List.of(Map.of("type", "text", "text", t.texto())));
    }

    private static String resumenUso(Map<?, ?> uso) {
        if (uso == null) {
            return "—";
        }
        return "entrada " + uso.get("total_input_tokens") + ", salida " + uso.get("total_output_tokens")
                + ", razonamiento " + uso.get("total_thought_tokens");
    }
}
