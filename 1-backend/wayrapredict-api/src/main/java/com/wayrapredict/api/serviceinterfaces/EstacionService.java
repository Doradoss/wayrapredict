package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.EstacionDTO.EstacionDto;
import com.wayrapredict.api.entities.Estacion;
import com.wayrapredict.api.repositories.EstacionRepository;
import com.wayrapredict.api.util.NoEncontradoException;
import jakarta.persistence.Tuple;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import static com.wayrapredict.api.util.TupleUtil.*;

@Service
@Transactional(readOnly = true)
public class EstacionService {
    final EstacionRepository estacionRepository;

    public EstacionService(EstacionRepository estacionRepository) {
        this.estacionRepository = estacionRepository;
    }

    //Lista las estaciones con su contaminante y fecha de referencia
    public List<EstacionDto> findAll() {
        return estacionRepository.estacionesConReferencia(null).stream().map(this::aDto).toList();
    }

    //Estación por código (p. ej. CA-CC-01)
    public EstacionDto findByCodigo(String codigo) {
        return estacionRepository.estacionesConReferencia(codigo).stream().findFirst().map(this::aDto)
                .orElseThrow(() -> new NoEncontradoException("Estación no encontrada: " + codigo));
    }

    //Nombre de cada estación por su código (p. ej. CA-CC-01 -> La Oroya)
    public Map<String, String> nombresPorCodigo() {
        return estacionRepository.findAll().stream().collect(Collectors.toMap(Estacion::getCodigo, Estacion::getNombre));
    }

    //Comprueba que la estación exista (lanza 404 si no)
    public void validarExiste(String codigo) {
        if (estacionRepository.findByCodigo(codigo).isEmpty()) {
            throw new NoEncontradoException("Estación no encontrada: " + codigo);
        }
    }

    private EstacionDto aDto(Tuple t) {
        return new EstacionDto(entero(t, "id_estacion"), texto(t, "codigo"), texto(t, "nombre"),
                texto(t, "departamento"), texto(t, "provincia"), texto(t, "distrito"),
                decimal(t, "este"), decimal(t, "norte"), entero(t, "zona_utm"), entero(t, "altitud"),
                booleano(t, "activa"), texto(t, "contaminante"), texto(t, "contaminante_nombre"),
                texto(t, "unidad"), decimal(t, "eca_24h"), decimal(t, "oms_24h"), fecha(t, "fecha_referencia"),
                decimal(t, "ultimo_valor"), decimal(t, "ultimo_valor_inca"), texto(t, "categoria_ultimo_valor"),
                texto(t, "color_ultimo_valor"), fechaHora(t, "ultima_actualizacion"));
    }
}
