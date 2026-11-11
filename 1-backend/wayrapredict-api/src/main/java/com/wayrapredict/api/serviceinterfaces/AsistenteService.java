package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.AlertaDTO.AlertaDto;
import com.wayrapredict.api.dtos.AsistenteDTO.MensajeAsistenteDto;
import com.wayrapredict.api.dtos.AsistenteDTO.PreguntaAsistenteDto;
import com.wayrapredict.api.dtos.AsistenteDTO.RespuestaAsistenteDto;
import com.wayrapredict.api.dtos.CategoriaIncaDTO.CategoriaIncaDto;
import com.wayrapredict.api.dtos.EstacionDTO.EstacionDto;
import com.wayrapredict.api.dtos.PrediccionDTO.PrediccionDto;
import com.wayrapredict.api.util.DemasiadasSolicitudesException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

//Asistente conversacional: responde preguntas de la ciudadanía sobre la calidad del aire con los datos reales de la
//plataforma. Arma un contexto con las estaciones, el pronóstico de 1 a 3 días, las alertas vigentes y las categorías
//del INCA (todo desde la base de datos) y se lo entrega a Gemini junto con reglas fijas de comportamiento.
//No guarda las preguntas: la memoria de la conversación la envía el navegador.
@Service
public class AsistenteService {
    private static final int TURNOS_MEMORIA = 6;
    private static final DateTimeFormatter FECHA = DateTimeFormatter.ofPattern("d 'de' MMMM 'de' yyyy", new Locale("es", "PE"));

    final EstacionService estacionService;
    final PrediccionService prediccionService;
    final AlertaService alertaService;
    final CategoriaIncaService categoriaIncaService;
    final GeminiService geminiService;

    @Value("${wayra.asistente.preguntas-por-minuto:10}")
    private int preguntasPorMinuto;

    //Marcas de tiempo de las preguntas recientes por cliente (dirección IP), para el límite por minuto
    private final Map<String, Deque<Long>> recientes = new ConcurrentHashMap<>();

    public AsistenteService(EstacionService estacionService, PrediccionService prediccionService, AlertaService alertaService,
                            CategoriaIncaService categoriaIncaService, GeminiService geminiService) {
        this.estacionService = estacionService;
        this.prediccionService = prediccionService;
        this.alertaService = alertaService;
        this.categoriaIncaService = categoriaIncaService;
        this.geminiService = geminiService;
    }

    //Pregunta lista para enviar a Gemini: instrucciones (reglas + contexto), conversación y fecha de los datos
    public record PreguntaPreparada(String instrucciones, List<GeminiService.Turno> conversacion, LocalDate fechaDatos) {}

    //Respuesta completa (POST /api/libre/asistente)
    public RespuestaAsistenteDto preguntar(PreguntaAsistenteDto dto, String cliente) {
        return responder(preparar(dto, cliente), fragmento -> {});
    }

    //Responde entregando cada fragmento de texto apenas llega (POST /api/libre/asistente/stream)
    public RespuestaAsistenteDto responder(PreguntaPreparada p, java.util.function.Consumer<String> alFragmento) {
        GeminiService.Resultado r = geminiService.generar(p.instrucciones(), p.conversacion(), alFragmento);
        return new RespuestaAsistenteDto(r.texto(), p.fechaDatos(), r.modelo());
    }

    //Valida, aplica el límite por minuto y arma el contexto. Lanza 400/404/429 antes de llamar a Gemini.
    public PreguntaPreparada preparar(PreguntaAsistenteDto dto, String cliente) {
        controlarLimite(cliente);
        List<EstacionDto> estaciones = estacionService.findAll();
        if (dto.getEstacion() != null && !dto.getEstacion().isBlank()) {
            estacionService.validarExiste(dto.getEstacion());
        }
        String instrucciones = REGLAS + "\n\n" + contexto(estaciones, dto.getEstacion());

        //Memoria: últimas intervenciones (empezando por una del usuario) + la pregunta actual
        List<MensajeAsistenteDto> historial = dto.getHistorial() == null ? List.of() : dto.getHistorial();
        List<MensajeAsistenteDto> ultimos = historial.subList(Math.max(0, historial.size() - TURNOS_MEMORIA), historial.size());
        List<GeminiService.Turno> conversacion = new ArrayList<>();
        for (MensajeAsistenteDto m : ultimos) {
            if (conversacion.isEmpty() && !"usuario".equals(m.getRol())) {
                continue;
            }
            conversacion.add(new GeminiService.Turno(m.getRol(), m.getTexto()));
        }
        conversacion.add(new GeminiService.Turno("usuario", dto.getPregunta().strip()));

        LocalDate fechaDatos = estaciones.stream().map(EstacionDto::getFechaReferencia).filter(Objects::nonNull)
                .max(LocalDate::compareTo).orElse(null);
        return new PreguntaPreparada(instrucciones, conversacion, fechaDatos);
    }

    //Límite de preguntas por minuto por cliente (protege la cuota de la API)
    void controlarLimite(String cliente) {
        long ahora = System.currentTimeMillis();
        Deque<Long> marcas = recientes.computeIfAbsent(cliente == null ? "?" : cliente, k -> new ArrayDeque<>());
        synchronized (marcas) {
            while (!marcas.isEmpty() && ahora - marcas.peekFirst() > 60_000) {
                marcas.pollFirst();
            }
            if (marcas.size() >= preguntasPorMinuto) {
                throw new DemasiadasSolicitudesException("Hiciste muchas preguntas seguidas. Espera un momento antes de volver a preguntar.");
            }
            marcas.addLast(ahora);
        }
    }

    //Contexto con los datos reales de la plataforma, en texto
    String contexto(List<EstacionDto> estaciones, String estacionActual) {
        StringBuilder sb = new StringBuilder("DATOS ACTUALES DE LA PLATAFORMA WAYRAPREDICT\n");
        sb.append("\nCategorías del INCA (Índice de Calidad del Aire del MINAM; INCA = concentración promedio de 24 h ÷ ECA-Aire de 24 h × 100):\n");
        for (CategoriaIncaDto c : categoriaIncaService.findAll()) {
            sb.append("- ").append(c.getNombre()).append(" (color ").append(COLORES.getOrDefault(c.getNombre(), "sin color"))
                    .append(", INCA ").append(rango(c)).append("): ").append(c.getRecomendacion()).append('\n');
        }
        sb.append("\nEstaciones de vigilancia (\"día actual\" = último día con medición de la estación; los pronósticos cuentan desde ese día):\n");
        for (EstacionDto e : estaciones) {
            sb.append("\n* ").append(e.getNombre()).append(" (").append(e.getCodigo()).append("), ")
                    .append(e.getDepartamento()).append(", provincia de ").append(e.getProvincia())
                    .append(e.getAltitud() != null ? ", " + e.getAltitud() + " m s. n. m." : "").append('\n');
            sb.append("  Contaminante vigilado: ").append(e.getContaminanteNombre()).append(" (").append(e.getContaminante())
                    .append("). ECA-Aire 24 h: ").append(num(e.getEca24h())).append(" µg/m³; guía OMS 24 h: ").append(num(e.getOms24h())).append(" µg/m³.\n");
            sb.append("  Día actual: ").append(fecha(e.getFechaReferencia())).append(". Promedio medido ese día: ")
                    .append(num(e.getUltimoValor())).append(" µg/m³ (INCA ").append(num(e.getUltimoValorInca())).append(", ")
                    .append(e.getCategoriaUltimoValor() == null ? "sin categoría" : e.getCategoriaUltimoValor()).append(").\n");
            List<PrediccionDto> proximos = prediccionService.proximosDias(e.getCodigo());
            if (proximos.isEmpty()) {
                sb.append("  Pronóstico: no disponible.\n");
            }
            for (PrediccionDto p : proximos) {
                sb.append("  Pronóstico ").append(relativo(p.getDiasDesdeReferencia())).append(" (").append(fecha(p.getFechaObjetivo())).append("): ")
                        .append(num(p.getValor())).append(" µg/m³, intervalo ").append(num(p.getLimiteInferior())).append("–").append(num(p.getLimiteSuperior()))
                        .append(" µg/m³, INCA ").append(num(p.getValorInca())).append(", categoría ").append(p.getCategoriaInca())
                        .append(Boolean.TRUE.equals(p.getSuperaEca()) ? ", SUPERA el ECA-Aire" : "").append(".\n");
            }
        }
        List<AlertaDto> alertas = alertaService.buscar(null, "vigente");
        sb.append("\nAlertas vigentes (pronósticos de categoría Moderada o peor): ");
        if (alertas.isEmpty()) {
            sb.append("ninguna.\n");
        } else {
            sb.append('\n');
            for (AlertaDto a : alertas) {
                sb.append("- ").append(a.getEstacionNombre()).append(" (").append(a.getDepartamento()).append("), ")
                        .append(fecha(a.getFechaObjetivo())).append(": ").append(a.getCategoriaInca()).append(", ")
                        .append(num(a.getValor())).append(" µg/m³").append(Boolean.TRUE.equals(a.getSuperaEca()) ? ", supera el ECA-Aire" : "").append(".\n");
            }
        }
        if (estacionActual != null && !estacionActual.isBlank()) {
            estaciones.stream().filter(e -> e.getCodigo().equalsIgnoreCase(estacionActual)).findFirst().ifPresent(e ->
                    sb.append("\nEl usuario está viendo la estación ").append(e.getNombre()).append(" (").append(e.getDepartamento())
                            .append("). Si pregunta sin indicar el lugar, responde sobre esta estación.\n"));
        }
        return sb.toString();
    }

    //Color con que la plataforma muestra cada categoría (semáforo del INCA)
    private static final Map<String, String> COLORES = Map.of("Buena", "verde", "Moderada", "amarillo",
            "Mala", "anaranjado", "Umbral de cuidado", "rojo");

    private static String rango(CategoriaIncaDto c) {
        if (c.getIncaMin() == null) return "sobre el VUEC";
        if (c.getIncaMax() == null) return "mayor a 100";
        return num(c.getIncaMin()) + " a " + num(c.getIncaMax());
    }

    private static String relativo(Integer dias) {
        if (dias == null) return "";
        return dias == 1 ? "para mañana" : "en " + dias + " días";
    }

    private static String fecha(LocalDate f) {
        return f == null ? "sin fecha" : f.format(FECHA);
    }

    private static String num(BigDecimal v) {
        return v == null ? "sin dato" : v.setScale(0, RoundingMode.HALF_UP).toPlainString();
    }

    //Reglas fijas del asistente (instrucciones de sistema)
    static final String REGLAS = """
            Eres el asistente de WayraPredict, una plataforma pública que anticipa la calidad del aire en zonas con \
            actividad minero-industrial del Perú (Junín, Pasco y Moquegua) y la explica en lenguaje sencillo.

            Reglas:
            1. Responde siempre en español sencillo y cordial, sin tecnicismos innecesarios. Sé breve: de 2 a 5 oraciones \
            o una lista corta. Puedes usar **negritas** para lo más importante.
            2. Usa SOLO los datos de la sección "DATOS ACTUALES". No inventes valores, fechas ni estaciones. Si te preguntan \
            por un lugar, contaminante o fecha que no está en los datos, dilo claramente y menciona qué estaciones sí cubre la plataforma.
            3. Cuando hables de un pronóstico, menciona la estación, la fecha, el valor aproximado en µg/m³, la categoría INCA \
            y la recomendación de esa categoría. Recuerda que es una estimación con un intervalo de incertidumbre.
            4. "Hoy" para cada estación es su "día actual" de los datos. Si preguntan por "mañana", usa el pronóstico "para mañana".
            5. Solo atiendes temas de calidad del aire, contaminantes (SO₂, PM10), el INCA, los ECA-Aire, la guía de la OMS, \
            pronósticos, alertas, recomendaciones de cuidado y el uso de la plataforma. Si preguntan otra cosa, responde \
            amablemente que solo puedes ayudar con esos temas.
            6. No des diagnósticos ni tratamientos médicos. Ante síntomas o dudas de salud, recomienda acudir a un \
            establecimiento de salud.
            7. No pidas ni repitas datos personales. Si el usuario los escribe, no los uses.
            8. Si el usuario pide más detalle, sugiere revisar la pantalla de la estación o la sección Alertas de la plataforma.
            """;
}
