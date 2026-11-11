package com.wayrapredict.api.securities;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

//Pruebas unitarias del token JWT (sin base de datos)
class JwtTokenUtilTest {

    private static final String SECRETO = "clave-de-prueba-solo-para-tests-0123456789-0123456789-0123456789-abcdef";
    private JwtTokenUtil util;
    private UserDetails usuario;

    @BeforeEach
    void preparar() {
        util = crear(SECRETO, 60_000);
        usuario = new User("ana@institucion.pe", "x", List.of(new SimpleGrantedAuthority("usuario_institucional")));
    }

    private JwtTokenUtil crear(String secreto, long validezMs) {
        JwtTokenUtil u = new JwtTokenUtil();
        ReflectionTestUtils.setField(u, "secret", secreto);
        ReflectionTestUtils.setField(u, "validezMs", validezMs);
        u.iniciar();
        return u;
    }

    @Test
    void generaYValidaElToken() {
        String token = util.generateToken(usuario, "Ana Prueba");
        assertEquals("ana@institucion.pe", util.getUsernameFromToken(token));
        assertEquals("usuario_institucional", util.getClaimFromToken(token, c -> c.get("role", String.class)));
        assertTrue(util.validateToken(token, usuario));
    }

    @Test
    void rechazaTokenDeOtroUsuario() {
        String token = util.generateToken(usuario, "Ana Prueba");
        UserDetails otro = new User("otro@institucion.pe", "x", List.of());
        assertFalse(util.validateToken(token, otro));
    }

    @Test
    void rechazaTokenFirmadoConOtraClave() {
        String token = crear(SECRETO.replace('a', 'b'), 60_000).generateToken(usuario, "Ana Prueba");
        assertThrows(io.jsonwebtoken.security.SignatureException.class, () -> util.getUsernameFromToken(token));
    }

    @Test
    void rechazaTokenExpirado() {
        String token = crear(SECRETO, -1_000).generateToken(usuario, "Ana Prueba");
        assertThrows(io.jsonwebtoken.ExpiredJwtException.class, () -> util.getUsernameFromToken(token));
    }

    @Test
    void exigeClaveDeAlMenos64Caracteres() {
        assertThrows(IllegalStateException.class, () -> crear("corta", 60_000));
    }
}
