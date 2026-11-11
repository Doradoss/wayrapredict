# Análisis inicial del backend de WayraPredict (instrucciones_12_backend.md)

Revisé las dos referencias (solo `src/` y `pom.xml`) y el esquema 1.4. Dejé creado `1-backend/CLAUDE.md` para registrar las decisiones; no creé el proyecto ni escribí código. En esta PC está **Java 17.0.4** y **Maven no está instalado**, así que usaré el Maven Wrapper (`mvnw`) que trae el proyecto generado.

## 1. Lo que encontré en las referencias

**Cómo funciona el JWT de la plantilla (`jwt-20242`):**
- **`JwtTokenUtil`:** genera y valida el token con JJWT 0.9.1, firma HS512 y clave en `jwt.secret`. El token dura 7 horas, tiene el usuario como asunto y guarda el rol en un dato del token llamado `role`.
- **`JwtUserDetailsService`:** busca el usuario por nombre y arma el usuario de Spring con sus roles como permisos. La cuenta habilitada sale de `enabled`.
- **`JwtRequestFilter`:** lee la cabecera `Authorization: Bearer …`, valida el token y deja al usuario autenticado en la petición.
- **`JwtAuthenticationEntryPoint`:** responde 401 cuando no hay autenticación.
- **`JwtAuthenticationController`:** `POST /authenticate` recibe usuario y contraseña (`JwtRequest`) y devuelve el token (`JwtResponse`).
- **`WebSecurityConfig`:** sin estado, CSRF desactivado, BCrypt y reglas por ruta con `hasAuthority`. Las rutas de `/api/libre/**` son públicas.
- **`CORS`:** un filtro propio que permite todos los orígenes.
- **Usuarios:** tabla `users` más una tabla `roles` aparte (uno a muchos).
- **Problemas de la plantilla:**
  - mezcla Spring Boot 2.7 (`javax`) con springdoc 2.6, que necesita Boot 3;
  - JJWT 0.9.1 es antiguo y tiene métodos obsoletos;
  - la clave y la contraseña de la base están escritas en `application.properties`.

**Tus convenciones en `ejemplo2`:**
- Spring Boot 3.3, `jakarta`, Lombok (`@Data` y `@NoArgsConstructor`) y ModelMapper.
- Carpetas `entities`, `repositories`, `serviceinterfaces`, `serviceimplements` (solo el del JWT), `controllers`, `dtos/<Entidad>DTO/`, `securities` y `util`.
- **Repositorios:** `JpaRepository` con consultas `@Query` nativas en SQL que devuelven `List<Tuple>`, con alias explícitos y un comentario en español arriba de cada una.
- **Servicios:** clases `@Service` sin interfaz, con inyección por constructor (`final` + constructor). Mapean con ModelMapper y convierten los `Tuple` a DTO con `tuple.get("alias", Tipo.class)`.
- **Controladores:** `@RestController` + `@CrossOrigin`, rutas en minúsculas con guiones (`/findall-…`, `/registrar-…`) y respuestas `ResponseEntity<DTO>`. Los prefijos de ruta indican el rol (`/api/libre`, `/api/admin`, `/api/user`).

## 2. Estructura propuesta para `1-backend/wayrapredict-api/`

```
src/main/java/com/wayrapredict/api/
├── WayrapredictApiApplication.java
├── entities/          Estacion, Variable, CategoriaInca, Usuario, EjecucionProceso,
│                      MedicionDiaria, Modelo, Prediccion, VAlerta (vista, solo lectura)
├── repositories/      un repositorio por entidad + VAlertaRepository
│                      (consultas nativas con Tuple, como en ejemplo2)
├── dtos/
│   ├── EstacionDTO/  MedicionDTO/  PrediccionDTO/  AlertaDTO/  ModeloDTO/
│   ├── UsuarioDTO/   (solicitud de cuenta, perfil, cambio de rol o estado)
│   └── EjecucionDTO/
├── serviceinterfaces/ EstacionService, MedicionService, PrediccionService, AlertaService,
│                      ModeloService, UsuarioService, EjecucionService
├── serviceimplements/ JwtUserDetailsService
├── controllers/       JwtAuthenticationController, Estacion…, Medicion…, Prediccion…,
│                      Alerta…, Modelo…, Usuario…, Admin…
├── securities/        JwtTokenUtil, JwtRequestFilter, JwtAuthenticationEntryPoint,
│                      JwtRequest, JwtResponse, WebSecurityConfig
├── util/              CORS (o configuración de CORS) y manejo global de errores
└── config/            OpenAPI (Swagger con botón de token)
src/main/resources/application.properties   → solo ${WAYRA_DB_*} y ${WAYRA_JWT_SECRET}
```

**Rutas por rol, al estilo de `ejemplo2`:**

| Prefijo | Quién accede | Qué incluye |
|---|---|---|
| `/authenticate` | todos | login |
| `/api/libre/**` | todos | estaciones, mediciones con origen, predicciones del modelo vigente, alertas, métricas, solicitud de cuenta |
| `/api/institucional/**` | `usuario_institucional` | verificación de predicciones |
| `/api/admin/**` | `administrador` | aprobar o rechazar cuentas, cambiar roles, ejecuciones del proceso |

## 3. Plan de desarrollo
1. Generar el proyecto con Spring Initializr desde la línea de comandos, con las dependencias que pediste más Lombok y ModelMapper. Compilarlo con `mvnw` antes de agregar nada.
2. Configurar `application.properties` solo con variables de entorno: `WAYRA_DB_HOST`, `WAYRA_DB_PORT`, `WAYRA_DB_NAME`, `WAYRA_DB_USER`, `WAYRA_DB_PASSWORD` y una nueva `WAYRA_JWT_SECRET`. Poner `ddl-auto=validate`, para que Hibernate nunca modifique el esquema del ML.
3. Crear las 8 entidades mapeadas al esquema real y la vista `v_alerta` como entidad de solo lectura (`@Immutable`). Arrancar contra la base cargada para que `validate` confirme el mapeo.
4. Crear los repositorios con las consultas clave:
   - **Fecha de referencia:** `MAX(fecha)` con `origen = 'estacion'`.
   - **Mediciones:** por estación y rango de fechas, con contaminante, meteorología y origen, para el gráfico y el tooltip.
   - **Predicciones:** las del modelo vigente posteriores a la fecha de referencia ("próximos días") y las pasadas.
   - **Alertas:** las vigentes y el historial.
   - **Métricas:** las del modelo vigente.
5. Pasar la seguridad JWT de la plantilla, adaptada al esquema:
   - el correo es el usuario; el rol sale de la columna `usuario.rol`, porque el esquema no tiene tabla de roles;
   - solo los usuarios con `estado = 'aprobado'` pueden iniciar sesión;
   - contraseñas con BCrypt;
   - el token guarda el rol.
6. Hacer los servicios, los DTO y los controladores públicos, y probarlos contra los datos reales: 3 estaciones, 36 474 mediciones y 705 predicciones.
7. Hacer los endpoints con login:
   - **solicitud de cuenta:** queda en estado "pendiente";
   - **verificación de predicciones:** llena `verificado`, `verificado_por` y `fecha_verificacion`, respetando la regla del esquema que exige los tres juntos;
   - **administración:** aprobar o rechazar cuentas (con `aprobado_por` y `fecha_aprobacion`), cambiar roles y listar las ejecuciones del proceso.
8. Documentar con Swagger (botón "Authorize" para el token), agregar el manejo de errores en español y configurar CORS.
9. Probar: compilación, arranque, pruebas de los endpoints principales y de la seguridad (401/403, usuario pendiente rechazado). Documentar todo en `1-backend/CLAUDE.md`, incluido cómo ejecutarlo desde IntelliJ o con `mvnw`.

## Cambios que propongo frente a la plantilla (los explicaré al implementarlos)
- **Spring Boot 3.5.x** en lugar de 2.7: la versión 2.7 ya no tiene soporte y tu `ejemplo2` ya usa Boot 3. Elijo 3.5 y no 4.0 porque la 4 cambia más cosas de la seguridad y de springdoc.
- **Nueva sintaxis de seguridad:** la de Spring Security 6. `csrf().disable()`, `authorizeRequests()` y `antMatchers` están obsoletos; se reemplazan por la forma con lambdas, `authorizeHttpRequests` y `requestMatchers`. La lógica es la misma.
- **JJWT 0.12** en lugar de 0.9.1. Es la misma idea (crear y validar con una clave), pero sin métodos obsoletos y sin las librerías JAXB.
- **Clave JWT por variable de entorno**, con una longitud mínima suficiente para HS512.

## Decisiones que necesito antes de empezar
1. ¿Confirmas Spring Boot 3.5.x y JJWT 0.12? ¿O prefieres quedarte exactamente en la versión de tu `ejemplo2` (Boot 3.3 con JJWT 0.9.1)?
2. **Primer administrador:** la tabla `usuario` está vacía. Propongo crearlo al arrancar solo si no existe ningún administrador, con las variables `WAYRA_ADMIN_CORREO` y `WAYRA_ADMIN_PASSWORD`. La alternativa es un script SQL que ejecutas tú.
3. **Rutas:** ¿te parecen bien los prefijos `/api/libre`, `/api/institucional` y `/api/admin`, con nombres de ruta al estilo `ejemplo2` (por ejemplo, `/api/libre/estaciones` o `/api/libre/predicciones-vigentes/{codigo}`)?
4. **Usuario de la base:** ¿el backend se conecta con `postgres`, o creo las instrucciones para un usuario propio con permisos limitados? Este sería de lectura en casi todo y con escritura solo en `usuario` y en las columnas de verificación de `prediccion`.

Cuando me confirmes, empiezo por el paso 1.
