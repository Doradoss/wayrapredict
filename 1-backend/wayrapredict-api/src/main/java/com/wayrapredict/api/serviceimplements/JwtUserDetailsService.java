package com.wayrapredict.api.serviceimplements;

import com.wayrapredict.api.entities.Usuario;
import com.wayrapredict.api.repositories.UsuarioRepository;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;

//Clase 2 (como en la plantilla): carga el usuario para Spring Security.
//Adaptado al esquema: el correo es el usuario; el rol sale de la columna usuario.rol (no hay tabla de roles);
//solo los usuarios con estado 'aprobado' quedan habilitados (pendiente o rechazado = cuenta deshabilitada).
@Service
public class JwtUserDetailsService implements UserDetailsService {
    final UsuarioRepository usuarioRepository;

    public JwtUserDetailsService(UsuarioRepository usuarioRepository) {
        this.usuarioRepository = usuarioRepository;
    }

    @Override
    public UserDetails loadUserByUsername(String correo) throws UsernameNotFoundException {
        Usuario usuario = usuarioRepository.findByCorreoIgnoreCase(correo)
                .orElseThrow(() -> new UsernameNotFoundException("Usuario no existe"));
        boolean habilitado = Usuario.ESTADO_APROBADO.equals(usuario.getEstado());
        return new User(usuario.getCorreo(), usuario.getHashContrasena(), habilitado, true, true, true,
                List.of(new SimpleGrantedAuthority(usuario.getRol())));
    }
}
