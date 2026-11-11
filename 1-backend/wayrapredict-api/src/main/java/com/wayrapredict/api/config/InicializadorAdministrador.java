package com.wayrapredict.api.config;

import com.wayrapredict.api.entities.Usuario;
import com.wayrapredict.api.repositories.UsuarioRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

//Crea el primer administrador al arrancar, SOLO si no existe ningún administrador.
//Datos desde WAYRA_ADMIN_CORREO y WAYRA_ADMIN_PASSWORD; la contraseña se guarda con BCrypt y nunca se registra
//en los logs.
@Component
public class InicializadorAdministrador implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(InicializadorAdministrador.class);

    final UsuarioRepository usuarioRepository;
    final PasswordEncoder passwordEncoder;

    @Value("${wayra.admin.correo}")
    private String correo;

    @Value("${wayra.admin.password}")
    private String password;

    public InicializadorAdministrador(UsuarioRepository usuarioRepository, PasswordEncoder passwordEncoder) {
        this.usuarioRepository = usuarioRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (usuarioRepository.existsByRol(Usuario.ROL_ADMINISTRADOR)) {
            return;
        }
        if (correo == null || correo.isBlank() || password == null || password.isBlank()) {
            log.warn("No existe ningún administrador y faltan WAYRA_ADMIN_CORREO / WAYRA_ADMIN_PASSWORD: no se creó el administrador inicial");
            return;
        }
        if (password.length() < 8) {
            log.warn("WAYRA_ADMIN_PASSWORD debe tener al menos 8 caracteres: no se creó el administrador inicial");
            return;
        }
        if (usuarioRepository.existsByCorreoIgnoreCase(correo)) {
            log.warn("El correo de WAYRA_ADMIN_CORREO ya existe con otro rol: no se creó el administrador inicial");
            return;
        }
        Usuario admin = new Usuario();
        admin.setNombres("Administrador");
        admin.setApellidos("WayraPredict");
        admin.setCorreo(correo.trim().toLowerCase());
        admin.setHashContrasena(passwordEncoder.encode(password));
        admin.setRol(Usuario.ROL_ADMINISTRADOR);
        admin.setEstado(Usuario.ESTADO_APROBADO);
        admin.setFechaRegistro(LocalDateTime.now());
        admin.setFechaAprobacion(LocalDateTime.now());
        usuarioRepository.save(admin);
        log.info("Administrador inicial creado: {}", admin.getCorreo());
    }
}
