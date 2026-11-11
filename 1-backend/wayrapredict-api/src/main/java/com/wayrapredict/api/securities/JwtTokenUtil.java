package com.wayrapredict.api.securities;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

//Clase 1 (como en la plantilla): genera y valida el token JWT.
//Cambio frente a la plantilla: JJWT 0.13 (API actual). La clave se arma con Keys.hmacShaKeyFor y se valida
//al arrancar (HS512 exige al menos 64 bytes); antes se pasaba el texto directo a signWith (método obsoleto).
@Component
public class JwtTokenUtil {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.validez-ms}")
    private long validezMs;

    private SecretKey clave;

    @PostConstruct
    void iniciar() {
        byte[] bytes = secret == null ? new byte[0] : secret.getBytes(StandardCharsets.UTF_8);
        if (bytes.length < 64) {
            throw new IllegalStateException("WAYRA_JWT_SECRET debe tener al menos 64 caracteres (HS512)");
        }
        clave = Keys.hmacShaKeyFor(bytes);
    }

    //Obtiene el usuario (correo) del token
    public String getUsernameFromToken(String token) {
        return getClaimFromToken(token, Claims::getSubject);
    }

    //Obtiene la fecha de expiración del token
    public Date getExpirationDateFromToken(String token) {
        return getClaimFromToken(token, Claims::getExpiration);
    }

    public <T> T getClaimFromToken(String token, Function<Claims, T> claimsResolver) {
        return claimsResolver.apply(getAllClaimsFromToken(token));
    }

    //Lee los datos del token verificando la firma con la clave secreta
    private Claims getAllClaimsFromToken(String token) {
        return Jwts.parser().verifyWith(clave).build().parseSignedClaims(token).getPayload();
    }

    private boolean isTokenExpired(String token) {
        return getExpirationDateFromToken(token).before(new Date());
    }

    //Genera el token del usuario: asunto = correo; datos extra = rol y nombre
    public String generateToken(UserDetails userDetails, String nombre) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("nombre", nombre);
        claims.put("role", userDetails.getAuthorities().stream().map(r -> r.getAuthority())
                .collect(Collectors.joining()));
        return doGenerateToken(claims, userDetails.getUsername());
    }

    //Firma HS512 con la clave secreta, con fecha de emisión y de expiración
    private String doGenerateToken(Map<String, Object> claims, String subject) {
        long ahora = System.currentTimeMillis();
        return Jwts.builder().claims(claims).subject(subject).issuedAt(new Date(ahora))
                .expiration(new Date(ahora + validezMs))
                .signWith(clave, Jwts.SIG.HS512).compact();
    }

    //El token es válido si es del mismo usuario y no ha expirado
    public boolean validateToken(String token, UserDetails userDetails) {
        final String username = getUsernameFromToken(token);
        return username.equalsIgnoreCase(userDetails.getUsername()) && !isTokenExpired(token);
    }

    public long getValidezMs() {
        return validezMs;
    }
}
