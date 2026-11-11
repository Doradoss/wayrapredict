package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.EstacionDTO.EstacionDto;
import com.wayrapredict.api.dtos.MedicionDTO.MedicionDto;
import com.wayrapredict.api.dtos.MedicionDTO.SerieDiariaDto;
import com.wayrapredict.api.repositories.MedicionDiariaRepository;
import jakarta.persistence.Tuple;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;

import static com.wayrapredict.api.util.TupleUtil.*;

@Service
@Transactional(readOnly = true)
public class MedicionService {
    //Días que se muestran por defecto antes de la fecha de referencia
    public static final int DIAS_POR_DEFECTO = 90;

    final MedicionDiariaRepository medicionRepository;
    final EstacionService estacionService;

    public MedicionService(MedicionDiariaRepository medicionRepository, EstacionService estacionService) {
        this.medicionRepository = medicionRepository;
        this.estacionService = estacionService;
    }

    //Serie diaria (gráfico + tooltip). Por defecto: los 90 días previos a la fecha de referencia (último dato
    //medido por la estación) y los días posteriores que tengan meteorología pronosticada.
    public List<SerieDiariaDto> serieDiaria(String codigo, LocalDate desde, LocalDate hasta) {
        EstacionDto estacion = estacionService.findByCodigo(codigo);
        LocalDate referencia = estacion.getFechaReferencia();
        LocalDate[] rango = rango(codigo, referencia, desde, hasta);
        return medicionRepository.serieDiaria(codigo, rango[0], rango[1]).stream().map(t -> new SerieDiariaDto(
                fecha(t, "fecha"),
                referencia != null && fecha(t, "fecha").isAfter(referencia),
                decimal(t, "contaminante"), texto(t, "origen_contaminante"),
                decimal(t, "temperatura"), texto(t, "origen_temperatura"),
                decimal(t, "humedad_relativa"), texto(t, "origen_humedad_relativa"),
                decimal(t, "velocidad_viento"), texto(t, "origen_velocidad_viento"),
                decimal(t, "direccion_viento"), texto(t, "origen_direccion_viento"),
                decimal(t, "presion_barometrica"), texto(t, "origen_presion_barometrica"),
                decimal(t, "precipitacion"), texto(t, "origen_precipitacion"))).toList();
    }

    //Mediciones en formato largo, opcionalmente de una sola variable (p. ej. PM10, TEMPERATURA)
    public List<MedicionDto> mediciones(String codigo, LocalDate desde, LocalDate hasta, String variable) {
        EstacionDto estacion = estacionService.findByCodigo(codigo);
        LocalDate[] rango = rango(codigo, estacion.getFechaReferencia(), desde, hasta);
        List<Tuple> filas = medicionRepository.medicionesPorEstacion(codigo, rango[0], rango[1], variable);
        return filas.stream().map(t -> new MedicionDto(fecha(t, "fecha"), texto(t, "variable"),
                texto(t, "variable_nombre"), texto(t, "tipo"), texto(t, "unidad"), decimal(t, "valor"),
                texto(t, "origen"))).toList();
    }

    private LocalDate[] rango(String codigo, LocalDate referencia, LocalDate desde, LocalDate hasta) {
        LocalDate fin = hasta != null ? hasta : medicionRepository.ultimaFechaConDatos(codigo);
        if (fin == null) {
            fin = LocalDate.now();
        }
        LocalDate base = referencia != null ? referencia : fin;
        LocalDate inicio = desde != null ? desde : base.minusDays(DIAS_POR_DEFECTO - 1);
        if (inicio.isAfter(fin)) {
            throw new IllegalArgumentException("La fecha 'desde' debe ser anterior o igual a 'hasta'");
        }
        return new LocalDate[]{inicio, fin};
    }
}
