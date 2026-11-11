package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.ModeloDTO.MetricaModeloDto;
import com.wayrapredict.api.repositories.ModeloRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

import static com.wayrapredict.api.util.TupleUtil.*;

@Service
@Transactional(readOnly = true)
public class ModeloService {
    final ModeloRepository modeloRepository;
    final EstacionService estacionService;

    public ModeloService(ModeloRepository modeloRepository, EstacionService estacionService) {
        this.modeloRepository = modeloRepository;
        this.estacionService = estacionService;
    }

    //Métricas del modelo vigente ("Desempeño del modelo") o de todas las versiones (vigente y respaldos)
    public List<MetricaModeloDto> metricas(String estacion, boolean soloVigente) {
        if (estacion != null) {
            estacionService.validarExiste(estacion);
        }
        return modeloRepository.metricas(estacion, soloVigente).stream().map(t -> new MetricaModeloDto(
                texto(t, "estacion"), texto(t, "estacion_nombre"), texto(t, "contaminante"),
                entero(t, "id_modelo"), texto(t, "version"), booleano(t, "vigente"),
                fechaHora(t, "fecha_entrenamiento"), decimal(t, "rmse"), decimal(t, "mae"), decimal(t, "r2"),
                texto(t, "unidad"))).toList();
    }
}
