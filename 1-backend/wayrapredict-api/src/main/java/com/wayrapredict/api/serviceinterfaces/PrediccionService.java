package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.PrediccionDTO.PrediccionDto;
import com.wayrapredict.api.entities.Usuario;
import com.wayrapredict.api.repositories.PrediccionRepository;
import com.wayrapredict.api.repositories.UsuarioRepository;
import com.wayrapredict.api.util.NoEncontradoException;
import com.wayrapredict.api.util.ReglaNegocioException;
import jakarta.persistence.Tuple;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

import static com.wayrapredict.api.util.TupleUtil.*;

@Service
@Transactional(readOnly = true)
public class PrediccionService {
    final PrediccionRepository prediccionRepository;
    final EstacionService estacionService;
    final UsuarioRepository usuarioRepository;

    public PrediccionService(PrediccionRepository prediccionRepository, EstacionService estacionService,
                             UsuarioRepository usuarioRepository) {
        this.prediccionRepository = prediccionRepository;
        this.estacionService = estacionService;
        this.usuarioRepository = usuarioRepository;
    }

    //Próximos días: predicciones de la última ejecución de la estación (vigente o respaldo) posteriores a la
    //fecha de referencia. Cada una indica la versión del modelo que la generó.
    public List<PrediccionDto> proximosDias(String codigo) {
        estacionService.validarExiste(codigo);
        return prediccionRepository.proximosDias(codigo).stream().map(t -> aDto(t, false)).toList();
    }

    //Historial: predicciones con fecha objetivo hasta la fecha de referencia, con el valor observado
    public List<PrediccionDto> historial(String codigo, LocalDate desde, LocalDate hasta) {
        estacionService.validarExiste(codigo);
        LocalDate inicio = desde != null ? desde : LocalDate.of(1900, 1, 1);
        LocalDate fin = hasta != null ? hasta : LocalDate.of(9999, 12, 31);
        if (inicio.isAfter(fin)) {
            throw new IllegalArgumentException("La fecha 'desde' debe ser anterior o igual a 'hasta'");
        }
        return prediccionRepository.historial(codigo, inicio, fin).stream().map(t -> aDto(t, true)).toList();
    }

    //Detalle de una predicción
    public PrediccionDto findById(Long id) {
        return prediccionRepository.detalle(id).stream().findFirst().map(t -> aDto(t, false))
                .orElseThrow(() -> new NoEncontradoException("Predicción no encontrada: " + id));
    }

    //Predicciones del historial que aún no se verificaron (con su valor observado), para el usuario institucional
    public List<PrediccionDto> porVerificar(String codigo, LocalDate desde, LocalDate hasta) {
        return historial(codigo, desde, hasta).stream().filter(p -> !Boolean.TRUE.equals(p.getVerificado())).toList();
    }

    //Verifica una predicción: registra quién y cuándo (las 3 columnas juntas, como exige el esquema)
    @Transactional
    public PrediccionDto verificar(Long id, String correoUsuario) {
        PrediccionDto actual = findById(id);
        if (Boolean.TRUE.equals(actual.getVerificado())) {
            throw new ReglaNegocioException("La predicción " + id + " ya fue verificada por " + actual.getVerificadoPor());
        }
        Usuario usuario = usuarioRepository.findByCorreoIgnoreCase(correoUsuario)
                .orElseThrow(() -> new NoEncontradoException("Usuario no encontrado: " + correoUsuario));
        if (prediccionRepository.verificar(id, usuario.getIdUsuario(), LocalDateTime.now()) == 0) {
            throw new ReglaNegocioException("La predicción " + id + " ya fue verificada");
        }
        return findById(id);
    }

    PrediccionDto aDto(Tuple t, boolean conObservado) {
        return new PrediccionDto(largo(t, "id_prediccion"), texto(t, "estacion"), texto(t, "contaminante"),
                fecha(t, "fecha_objetivo"), fecha(t, "fecha_referencia"), entero(t, "dias_desde_referencia"),
                decimal(t, "valor"), decimal(t, "limite_inferior"), decimal(t, "limite_superior"),
                decimal(t, "valor_inca"), booleano(t, "supera_eca"), texto(t, "categoria_inca"),
                texto(t, "color_hex"), texto(t, "recomendacion"), texto(t, "version_modelo"),
                booleano(t, "modelo_vigente"), largo(t, "id_ejecucion"), booleano(t, "verificado"),
                texto(t, "verificado_por"), fechaHora(t, "fecha_verificacion"),
                conObservado ? decimal(t, "observado") : null,
                conObservado ? texto(t, "origen_observado") : null,
                conObservado ? texto(t, "categoria_observada") : null,
                conObservado ? texto(t, "color_observado") : null);
    }
}
