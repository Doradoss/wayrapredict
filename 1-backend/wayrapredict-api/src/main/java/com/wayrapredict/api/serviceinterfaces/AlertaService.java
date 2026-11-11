package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.AlertaDTO.AlertaDto;
import com.wayrapredict.api.entities.VAlerta;
import com.wayrapredict.api.repositories.VAlertaRepository;
import org.modelmapper.ModelMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
@Transactional(readOnly = true)
public class AlertaService {
    private static final Set<String> ESTADOS = Set.of("vigente", "finalizada");

    final VAlertaRepository alertaRepository;
    final EstacionService estacionService;

    public AlertaService(VAlertaRepository alertaRepository, EstacionService estacionService) {
        this.alertaRepository = alertaRepository;
        this.estacionService = estacionService;
    }

    //Alertas (vista v_alerta) por estación y estado; "vigente" = fecha objetivo posterior a la fecha de referencia
    public List<AlertaDto> buscar(String estacion, String estado) {
        if (estado != null && !ESTADOS.contains(estado)) {
            throw new IllegalArgumentException("Estado inválido: use 'vigente' o 'finalizada'");
        }
        if (estacion != null) {
            estacionService.validarExiste(estacion);
        }
        ModelMapper modelMapper = new ModelMapper();
        Map<String, String> nombres = estacionService.nombresPorCodigo();
        List<VAlerta> alertas = alertaRepository.buscar(estacion, estado);
        return alertas.stream().map(a -> {
            AlertaDto dto = modelMapper.map(a, AlertaDto.class);
            dto.setEstacionNombre(nombres.get(a.getEstacion()));
            return dto;
        }).toList();
    }
}
