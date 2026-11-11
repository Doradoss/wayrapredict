package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.EjecucionDTO.EjecucionDto;
import com.wayrapredict.api.repositories.EjecucionProcesoRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

import static com.wayrapredict.api.util.TupleUtil.*;

@Service
@Transactional(readOnly = true)
public class EjecucionService {
    final EjecucionProcesoRepository ejecucionRepository;

    public EjecucionService(EjecucionProcesoRepository ejecucionRepository) {
        this.ejecucionRepository = ejecucionRepository;
    }

    //Estado de las ejecuciones del proceso (más recientes primero)
    public List<EjecucionDto> findAll() {
        return ejecucionRepository.ejecucionesConConteo().stream().map(t -> new EjecucionDto(
                largo(t, "id_ejecucion"), fechaHora(t, "fecha_inicio"), fechaHora(t, "fecha_fin"),
                texto(t, "estado"), texto(t, "mensaje_error"), largo(t, "predicciones"), largo(t, "mediciones"))).toList();
    }
}
