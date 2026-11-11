package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.AsistenteDTO.MensajeAsistenteDto;
import com.wayrapredict.api.dtos.AsistenteDTO.PreguntaAsistenteDto;
import com.wayrapredict.api.dtos.AsistenteDTO.RespuestaAsistenteDto;
import com.wayrapredict.api.dtos.CategoriaIncaDTO.CategoriaIncaDto;
import com.wayrapredict.api.dtos.EstacionDTO.EstacionDto;
import com.wayrapredict.api.dtos.PrediccionDTO.PrediccionDto;
import com.wayrapredict.api.util.DemasiadasSolicitudesException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

//Pruebas del asistente con servicios simulados (sin base de datos ni Gemini)
class AsistenteServiceTest {
    private GeminiService gemini;
    private AsistenteService asistente;

    @BeforeEach
    void preparar() {
        EstacionService estaciones = mock(EstacionService.class);
        PrediccionService predicciones = mock(PrediccionService.class);
        AlertaService alertas = mock(AlertaService.class);
        CategoriaIncaService categorias = mock(CategoriaIncaService.class);
        gemini = mock(GeminiService.class);

        EstacionDto oroya = new EstacionDto();
        oroya.setCodigo("CA-CC-01");
        oroya.setNombre("La Oroya");
        oroya.setDepartamento("Junín");
        oroya.setProvincia("Yauli");
        oroya.setContaminante("SO2");
        oroya.setContaminanteNombre("Dióxido de azufre");
        oroya.setEca24h(new BigDecimal("250"));
        oroya.setFechaReferencia(LocalDate.of(2026, 6, 25));
        oroya.setUltimoValor(new BigDecimal("25"));
        when(estaciones.findAll()).thenReturn(List.of(oroya));

        PrediccionDto manana = new PrediccionDto();
        manana.setFechaObjetivo(LocalDate.of(2026, 6, 26));
        manana.setDiasDesdeReferencia(1);
        manana.setValor(new BigDecimal("46"));
        manana.setLimiteInferior(new BigDecimal("20"));
        manana.setLimiteSuperior(new BigDecimal("88"));
        manana.setValorInca(new BigDecimal("18.4"));
        manana.setCategoriaInca("Buena");
        when(predicciones.proximosDias("CA-CC-01")).thenReturn(List.of(manana));
        when(alertas.buscar(isNull(), eq("vigente"))).thenReturn(List.of());
        when(categorias.findAll()).thenReturn(List.of(new CategoriaIncaDto((short) 1, "Buena", "#2E8B3E",
                new BigDecimal("0"), new BigDecimal("50"), "La calidad del aire es aceptable.")));
        when(gemini.generar(anyString(), anyList(), any())).thenReturn(new GeminiService.Resultado("Mañana será Buena.", "gemini-3.8-flash"));

        asistente = new AsistenteService(estaciones, predicciones, alertas, categorias, gemini);
        ReflectionTestUtils.setField(asistente, "preguntasPorMinuto", 3);
    }

    private static PreguntaAsistenteDto pregunta(String texto) {
        PreguntaAsistenteDto dto = new PreguntaAsistenteDto();
        dto.setPregunta(texto);
        return dto;
    }

    @Test
    @SuppressWarnings("unchecked")
    void elContextoLlevaLosDatosRealesYLaRespuestaElModelo() {
        RespuestaAsistenteDto r = asistente.preguntar(pregunta("¿Cómo estará el aire mañana en La Oroya?"), "1.1.1.1");
        assertEquals("Mañana será Buena.", r.getRespuesta());
        assertEquals("gemini-3.8-flash", r.getModelo());
        assertEquals(LocalDate.of(2026, 6, 25), r.getFechaDatos());

        ArgumentCaptor<String> instrucciones = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<List<GeminiService.Turno>> conversacion = ArgumentCaptor.forClass(List.class);
        verify(gemini).generar(instrucciones.capture(), conversacion.capture(), any());
        String contexto = instrucciones.getValue();
        assertTrue(contexto.contains("La Oroya (CA-CC-01)"));
        assertTrue(contexto.contains("Pronóstico para mañana (26 de junio de 2026): 46 µg/m³"));
        assertTrue(contexto.contains("Alertas vigentes (pronósticos de categoría Moderada o peor): ninguna."));
        assertTrue(contexto.contains("No des diagnósticos"));
        assertTrue(contexto.contains("- Buena (color verde, INCA 0 a 50)"));
        assertEquals(1, conversacion.getValue().size());
    }

    @Test
    @SuppressWarnings("unchecked")
    void laMemoriaUsaLasUltimasSeisIntervencionesEmpezandoPorElUsuario() {
        PreguntaAsistenteDto dto = pregunta("¿y pasado mañana?");
        List<MensajeAsistenteDto> historial = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            historial.add(new MensajeAsistenteDto("usuario", "pregunta " + i));
            historial.add(new MensajeAsistenteDto("asistente", "respuesta " + i));
        }
        dto.setHistorial(historial);
        asistente.preguntar(dto, "2.2.2.2");
        ArgumentCaptor<List<GeminiService.Turno>> conversacion = ArgumentCaptor.forClass(List.class);
        verify(gemini).generar(anyString(), conversacion.capture(), any());
        List<GeminiService.Turno> enviados = conversacion.getValue();
        assertEquals(7, enviados.size());                       //6 de memoria + la pregunta
        assertEquals("usuario", enviados.get(0).rol());
        assertEquals("pregunta 2", enviados.get(0).texto());
        assertEquals("¿y pasado mañana?", enviados.get(6).texto());
    }

    @Test
    void limitaLasPreguntasPorMinutoPorCliente() {
        for (int i = 0; i < 3; i++) {
            asistente.preguntar(pregunta("hola"), "3.3.3.3");
        }
        assertThrows(DemasiadasSolicitudesException.class, () -> asistente.preguntar(pregunta("hola"), "3.3.3.3"));
        //otro cliente no se ve afectado
        assertDoesNotThrow(() -> asistente.preguntar(pregunta("hola"), "4.4.4.4"));
    }
}
