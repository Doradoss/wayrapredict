package com.wayrapredict.api.repositories;

import com.wayrapredict.api.entities.Usuario;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface UsuarioRepository extends JpaRepository<Usuario, Integer> {

    //El correo funciona como nombre de usuario (sin distinguir mayúsculas)
    Optional<Usuario> findByCorreoIgnoreCase(String correo);

    boolean existsByCorreoIgnoreCase(String correo);

    boolean existsByRol(String rol);

    List<Usuario> findByEstadoOrderByFechaRegistroAsc(String estado);

    List<Usuario> findAllByOrderByFechaRegistroDesc();
}
