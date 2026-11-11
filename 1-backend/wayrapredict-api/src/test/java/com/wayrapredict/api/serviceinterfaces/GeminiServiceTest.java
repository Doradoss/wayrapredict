package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.util.ServicioNoDisponibleException;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

import static org.junit.jupiter.api.Assertions.*;

//Pruebas del cliente de Gemini con la API simulada (no se llama a Google ni se gasta cuota)
class GeminiServiceTest {

    //Respuesta simulada: una lista de fragmentos de texto, un error HTTP o "sin respuesta a tiempo"
    record Fragmentos(List<String> partes) {}

    //Cliente cuya transmisión sigue un guion, y anota los modelos, niveles de razonamiento y límites usados
    static class GeminiSimulado extends GeminiService {
        final List<Object> guion;
        final List<String> modelos = new ArrayList<>();
        final List<Map<String, Object>> cuerpos = new ArrayList<>();
        final List<Long> limites = new ArrayList<>();

        GeminiSimulado(Object... guion) {
            this.guion = new ArrayList<>(List.of(guion));
            ReflectionTestUtils.setField(this, "apiKey", "clave-de-prueba");
            ReflectionTestUtils.setField(this, "modelo", "gemini-3.6-flash");
            ReflectionTestUtils.setField(this, "modeloRespaldo", "gemini-3.5-flash-lite");
            ReflectionTestUtils.setField(this, "razonamiento", "minimal");
            ReflectionTestUtils.setField(this, "maxTokens", 2048);
            ReflectionTestUtils.setField(this, "primerTextoPrincipalMs", 8000L);
            ReflectionTestUtils.setField(this, "primerTextoRespaldoMs", 15000L);
            ReflectionTestUtils.setField(this, "pausaPrincipalMs", 0L);
        }

        @Override
        protected Transmision transmitir(Map<String, Object> cuerpo, Consumer<String> alFragmento, long limitePrimerTextoMs) {
            modelos.add((String) cuerpo.get("model"));
            cuerpos.add(cuerpo);
            limites.add(limitePrimerTextoMs);
            Object siguiente = guion.remove(0);
            if (siguiente instanceof RuntimeException e) {
                throw e;
            }
            StringBuilder texto = new StringBuilder();
            for (String parte : ((Fragmentos) siguiente).partes()) {
                alFragmento.accept(parte);
                texto.append(parte);
            }
            return new Transmision(texto.toString(), "completed", null, 100);
        }
    }

    private static Fragmentos respuesta(String... partes) {
        return new Fragmentos(List.of(partes));
    }

    private static GeminiService.ErrorGemini error(int estado, String cuerpo) {
        return new GeminiService.ErrorGemini(estado, cuerpo);
    }

    private static final List<GeminiService.Turno> PREGUNTA = List.of(new GeminiService.Turno("usuario", "¿Qué es el INCA?"));

    @Test
    void entregaCadaFragmentoYDevuelveElTextoCompleto() {
        GeminiSimulado g = new GeminiSimulado(respuesta("El INCA ", "es un ", "índice."));
        List<String> recibidos = new ArrayList<>();
        GeminiService.Resultado r = g.generar("reglas", PREGUNTA, recibidos::add);
        assertEquals(List.of("El INCA ", "es un ", "índice."), recibidos);
        assertEquals("El INCA es un índice.", r.texto());
        assertEquals("gemini-3.6-flash", r.modelo());
        Map<String, Object> cuerpo = g.cuerpos.get(0);
        assertEquals(false, cuerpo.get("store"));
        assertEquals(true, cuerpo.get("stream"));
        assertEquals("reglas", cuerpo.get("system_instruction"));
        assertEquals("minimal", ((Map<?, ?>) cuerpo.get("generation_config")).get("thinking_level"));
    }

    @Test
    void siElPrincipalEstaSaturadoPasaDirectoAlRespaldoSinReintentar() {
        GeminiSimulado g = new GeminiSimulado(error(503, "high demand"), respuesta("Respuesta del respaldo"));
        GeminiService.Resultado r = g.generar("reglas", PREGUNTA);
        assertEquals(List.of("gemini-3.6-flash", "gemini-3.5-flash-lite"), g.modelos);
        assertEquals("gemini-3.5-flash-lite", r.modelo());
        assertEquals(List.of(8000L, 15000L), g.limites);       //el respaldo tiene más tiempo para empezar
    }

    @Test
    void siElPrincipalNoEmpiezaAResponderATiempoPasaAlRespaldo() {
        GeminiSimulado g = new GeminiSimulado(new GeminiService.SinRespuestaATiempo("8 s"), respuesta("respaldo"));
        GeminiService.Resultado r = g.generar("reglas", PREGUNTA);
        assertEquals(List.of("gemini-3.6-flash", "gemini-3.5-flash-lite"), g.modelos);
        assertEquals("gemini-3.5-flash-lite", r.modelo());
    }

    @Test
    void trasUnFalloDelPrincipalLaSiguientePreguntaVaDirectoAlRespaldo() {
        GeminiSimulado g = new GeminiSimulado(error(429, "quota"), respuesta("uno"), respuesta("dos"));
        ReflectionTestUtils.setField(g, "pausaPrincipalMs", 60_000L);
        g.generar("reglas", PREGUNTA);
        g.generar("reglas", PREGUNTA);
        assertEquals(List.of("gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash-lite"), g.modelos);
    }

    @Test
    void siUnModeloNoAdmiteRazonamientoMinimoRepiteConLow() {
        GeminiSimulado g = new GeminiSimulado(error(400, "Thinking level THINKING_LEVEL_MINIMAL is not supported for this model"),
                respuesta("ok"), respuesta("ok de nuevo"));
        g.generar("reglas", PREGUNTA);
        g.generar("reglas", PREGUNTA);
        assertEquals(List.of("gemini-3.6-flash", "gemini-3.6-flash", "gemini-3.6-flash"), g.modelos);
        List<Object> niveles = g.cuerpos.stream().map(c -> ((Map<?, ?>) c.get("generation_config")).get("thinking_level")).map(Object.class::cast).toList();
        assertEquals(List.of("minimal", "low", "low"), niveles);   //se recuerda para las siguientes preguntas
    }

    @Test
    void siTodoFallaResponde503() {
        GeminiSimulado g = new GeminiSimulado(error(503, "x"), error(503, "x"));
        assertThrows(ServicioNoDisponibleException.class, () -> g.generar("reglas", PREGUNTA));
        assertEquals(2, g.modelos.size());
    }

    @Test
    void unErrorDeConfiguracionNoPruebaOtrosModelos() {
        GeminiSimulado g = new GeminiSimulado(error(400, "API key not valid"));
        assertThrows(ServicioNoDisponibleException.class, () -> g.generar("reglas", PREGUNTA));
        assertEquals(1, g.modelos.size());
    }

    @Test
    void sinSaldoAvisaClaramente() {
        GeminiSimulado g = new GeminiSimulado(error(402, "Payment Required"));
        ServicioNoDisponibleException e = assertThrows(ServicioNoDisponibleException.class, () -> g.generar("reglas", PREGUNTA));
        assertTrue(e.getMessage().contains("saldo"));
    }

    @Test
    void sinClaveNoLlamaAGemini() {
        GeminiSimulado g = new GeminiSimulado();
        ReflectionTestUtils.setField(g, "apiKey", "");
        assertThrows(ServicioNoDisponibleException.class, () -> g.generar("reglas", PREGUNTA));
        assertTrue(g.modelos.isEmpty());
    }

    @Test
    void laConversacionSeEnviaComoPasosDeUsuarioYDelModelo() {
        GeminiSimulado g = new GeminiSimulado(respuesta("ok"));
        g.generar("reglas", List.of(new GeminiService.Turno("usuario", "hola"), new GeminiService.Turno("asistente", "¡Hola!"),
                new GeminiService.Turno("usuario", "¿y mañana?")));
        List<?> input = (List<?>) g.cuerpos.get(0).get("input");
        assertEquals(3, input.size());
        assertEquals("user_input", ((Map<?, ?>) input.get(0)).get("type"));
        assertEquals("model_output", ((Map<?, ?>) input.get(1)).get("type"));
    }
}
