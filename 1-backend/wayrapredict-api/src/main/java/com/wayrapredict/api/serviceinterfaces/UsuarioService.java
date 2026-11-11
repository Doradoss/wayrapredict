package com.wayrapredict.api.serviceinterfaces;

import com.wayrapredict.api.dtos.UsuarioDTO.SolicitudCuentaDto;
import com.wayrapredict.api.dtos.UsuarioDTO.UsuarioDto;
import com.wayrapredict.api.entities.Usuario;
import com.wayrapredict.api.repositories.UsuarioRepository;
import com.wayrapredict.api.util.NoEncontradoException;
import com.wayrapredict.api.util.ReglaNegocioException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

@Service
public class UsuarioService {
    private static final Set<String> ESTADOS = Set.of(Usuario.ESTADO_PENDIENTE, Usuario.ESTADO_APROBADO, Usuario.ESTADO_RECHAZADO);

    final UsuarioRepository usuarioRepository;
    final PasswordEncoder passwordEncoder;

    public UsuarioService(UsuarioRepository usuarioRepository, PasswordEncoder passwordEncoder) {
        this.usuarioRepository = usuarioRepository;
        this.passwordEncoder = passwordEncoder;
    }

    //Solicitud de cuenta: usuario institucional en estado 'pendiente' con la contraseña en BCrypt
    @Transactional
    public UsuarioDto solicitarCuenta(SolicitudCuentaDto dto) {
        String correo = dto.getCorreo().trim().toLowerCase();
        if (usuarioRepository.existsByCorreoIgnoreCase(correo)) {
            throw new ReglaNegocioException("Ya existe una cuenta con el correo " + correo);
        }
        Usuario usuario = new Usuario();
        usuario.setNombres(dto.getNombres().trim());
        usuario.setApellidos(dto.getApellidos().trim());
        usuario.setCorreo(correo);
        usuario.setHashContrasena(passwordEncoder.encode(dto.getPassword()));
        usuario.setInstitucion(dto.getInstitucion().trim());
        usuario.setCargo(dto.getCargo() == null ? null : dto.getCargo().trim());
        usuario.setRol(Usuario.ROL_INSTITUCIONAL);
        usuario.setEstado(Usuario.ESTADO_PENDIENTE);
        usuario.setFechaRegistro(LocalDateTime.now());
        return aDto(usuarioRepository.save(usuario));
    }

    //Perfil del usuario que inició sesión
    @Transactional(readOnly = true)
    public UsuarioDto perfil(String correo) {
        return aDto(buscarPorCorreo(correo));
    }

    //Lista los usuarios, opcionalmente por estado (pendiente | aprobado | rechazado)
    @Transactional(readOnly = true)
    public List<UsuarioDto> findAll(String estado) {
        if (estado == null) {
            return usuarioRepository.findAllByOrderByFechaRegistroDesc().stream().map(this::aDto).toList();
        }
        if (!ESTADOS.contains(estado)) {
            throw new IllegalArgumentException("Estado inválido: use pendiente, aprobado o rechazado");
        }
        return usuarioRepository.findByEstadoOrderByFechaRegistroAsc(estado).stream().map(this::aDto).toList();
    }

    //Aprueba una cuenta: queda registrado qué administrador la aprobó y cuándo
    @Transactional
    public UsuarioDto aprobar(Integer id, String correoAdmin) {
        Usuario usuario = buscarPorId(id);
        if (Usuario.ESTADO_APROBADO.equals(usuario.getEstado())) {
            throw new ReglaNegocioException("La cuenta ya está aprobada");
        }
        usuario.setEstado(Usuario.ESTADO_APROBADO);
        usuario.setAprobadoPor(buscarPorCorreo(correoAdmin));
        usuario.setFechaAprobacion(LocalDateTime.now());
        return aDto(usuarioRepository.save(usuario));
    }

    //Rechaza una solicitud (o revoca una cuenta aprobada). Un administrador no puede rechazarse a sí mismo.
    @Transactional
    public UsuarioDto rechazar(Integer id, String correoAdmin) {
        Usuario usuario = buscarPorId(id);
        if (usuario.getCorreo().equalsIgnoreCase(correoAdmin)) {
            throw new ReglaNegocioException("Un administrador no puede rechazar su propia cuenta");
        }
        if (Usuario.ESTADO_RECHAZADO.equals(usuario.getEstado())) {
            throw new ReglaNegocioException("La cuenta ya está rechazada");
        }
        validarNoEsUltimoAdmin(usuario);
        usuario.setEstado(Usuario.ESTADO_RECHAZADO);
        usuario.setAprobadoPor(null);
        usuario.setFechaAprobacion(null);
        return aDto(usuarioRepository.save(usuario));
    }

    //Cambia el rol de un usuario. Un administrador no puede cambiar su propio rol ni dejar el sistema sin administradores.
    @Transactional
    public UsuarioDto cambiarRol(Integer id, String rol, String correoAdmin) {
        Usuario usuario = buscarPorId(id);
        if (usuario.getCorreo().equalsIgnoreCase(correoAdmin)) {
            throw new ReglaNegocioException("Un administrador no puede cambiar su propio rol");
        }
        if (rol.equals(usuario.getRol())) {
            throw new ReglaNegocioException("El usuario ya tiene el rol " + rol);
        }
        if (Usuario.ROL_ADMINISTRADOR.equals(usuario.getRol())) {
            validarNoEsUltimoAdmin(usuario);
        }
        usuario.setRol(rol);
        return aDto(usuarioRepository.save(usuario));
    }

    private void validarNoEsUltimoAdmin(Usuario usuario) {
        if (Usuario.ROL_ADMINISTRADOR.equals(usuario.getRol()) && Usuario.ESTADO_APROBADO.equals(usuario.getEstado())) {
            long admins = usuarioRepository.findByEstadoOrderByFechaRegistroAsc(Usuario.ESTADO_APROBADO).stream()
                    .filter(u -> Usuario.ROL_ADMINISTRADOR.equals(u.getRol())).count();
            if (admins <= 1) {
                throw new ReglaNegocioException("No se puede dejar el sistema sin administradores aprobados");
            }
        }
    }

    private Usuario buscarPorId(Integer id) {
        return usuarioRepository.findById(id).orElseThrow(() -> new NoEncontradoException("Usuario no encontrado: " + id));
    }

    private Usuario buscarPorCorreo(String correo) {
        return usuarioRepository.findByCorreoIgnoreCase(correo)
                .orElseThrow(() -> new NoEncontradoException("Usuario no encontrado: " + correo));
    }

    private UsuarioDto aDto(Usuario u) {
        return new UsuarioDto(u.getIdUsuario(), u.getNombres(), u.getApellidos(), u.getCorreo(), u.getInstitucion(),
                u.getCargo(), u.getRol(), u.getEstado(), u.getFechaRegistro(),
                u.getAprobadoPor() == null ? null : u.getAprobadoPor().getCorreo(), u.getFechaAprobacion());
    }
}
