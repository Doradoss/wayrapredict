package com.wayrapredict.api.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.ToString;

import java.time.LocalDateTime;

//Usuario de la plataforma: el correo funciona como nombre de usuario.
//Rol: administrador | usuario_institucional. Estado: pendiente | aprobado | rechazado.
@Entity
@Table(name = "usuario")
@Data
@NoArgsConstructor
public class Usuario {
    public static final String ROL_ADMINISTRADOR = "administrador";
    public static final String ROL_INSTITUCIONAL = "usuario_institucional";
    public static final String ESTADO_PENDIENTE = "pendiente";
    public static final String ESTADO_APROBADO = "aprobado";
    public static final String ESTADO_RECHAZADO = "rechazado";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id_usuario")
    private Integer idUsuario;
    @Column(name = "nombres", nullable = false, length = 80)
    private String nombres;
    @Column(name = "apellidos", nullable = false, length = 80)
    private String apellidos;
    @Column(name = "correo", nullable = false, length = 150, unique = true)
    private String correo;
    @ToString.Exclude
    @Column(name = "hash_contrasena", nullable = false, length = 255)
    private String hashContrasena;
    @Column(name = "institucion", length = 150)
    private String institucion;
    @Column(name = "cargo", length = 100)
    private String cargo;
    @Column(name = "rol", nullable = false, length = 25)
    private String rol;
    @Column(name = "estado", nullable = false, length = 12)
    private String estado;
    @Column(name = "fecha_registro", nullable = false)
    private LocalDateTime fechaRegistro;

    @ToString.Exclude
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "aprobado_por")
    private Usuario aprobadoPor;

    @Column(name = "fecha_aprobacion")
    private LocalDateTime fechaAprobacion;
}
