# WayraPredict API (Spring Boot 4.1.1, Java 17)

Backend de la plataforma WayraPredict. Lee la base PostgreSQL `wayrapredict`, que el ML crea y carga (`esquema_wayrapredict.sql` v1.4 y `10-CARGAR_BD.py`). El esquema nunca se modifica: se usa `ddl-auto=validate`.

## En palabras simples

El backend es el **intermediario** entre la aplicación web y la base de datos:
1. **Recibe** peticiones del navegador, por ejemplo «dame el pronóstico de La Oroya».
2. **Revisa** si la persona tiene permiso.
3. **Consulta** la base de datos y **responde** en formato JSON.

También maneja las cuentas (solicitud, aprobación, roles) y el asistente, que consulta a Gemini con los datos de la plataforma.

**Organización por capas (paquete `com.wayrapredict.api`):**

| Capa | Qué hace |
|---|---|
| `controllers` | Reciben las peticiones HTTP y devuelven JSON (un controlador por tema: estaciones, predicciones, alertas, cuenta, administración, asistente) |
| `serviceinterfaces` | Reglas del negocio: qué se puede hacer y cómo (por ejemplo, no verificar dos veces una predicción) y el armado del contexto del asistente |
| `repositories` | Consultas a la base de datos (Spring Data JPA y SQL nativo) |
| `entities` | Clases que representan las tablas |
| `dtos` | Forma exacta del JSON de entrada y salida, con sus validaciones |
| `securities` | Inicio de sesión con token JWT, filtro que valida el token en cada petición y permisos por rol |
| `config` | Documentación Swagger y creación del primer administrador |
| `util` | Errores uniformes en español y utilidades |

**Herramientas:**
- **Base:** Java 17 y Spring Boot 4.1 (Web MVC, Data JPA, Security, Validation).
- **Datos:** PostgreSQL con el usuario `wayra_api`, que tiene permisos mínimos.
- **Seguridad:** tokens JWT (JJWT, firma HS512) y contraseñas cifradas con BCrypt.
- **Documentación:** Swagger (springdoc-openapi).
- **Asistente:** cliente HTTP de Java hacia la Interactions API de Gemini.
- **Pruebas:** JUnit y Mockito.
- **Construcción:** Maven Wrapper (`mvnw`).

**En Azure** corre en **App Service** (Linux, Java 17). Las variables de entorno de la sección 2 se configuran como *Application settings*, cifradas en Azure.

## 1. Requisitos

- Java 17. Maven no hace falta: se usa el wrapper `mvnw` / `mvnw.cmd`.
- La base `wayrapredict` cargada y el usuario `wayra_api` creado con `../sql/crear_usuario_wayra_api.sql`. Ese script se ejecuta en pgAdmin como postgres, después de cambiar la contraseña de ejemplo.

## 2. Variables de entorno (nunca se escriben en el código)

| Variable | Uso | Ejemplo / valor por defecto |
|---|---|---|
| `WAYRA_DB_HOST`, `WAYRA_DB_PORT`, `WAYRA_DB_NAME` | Conexión (compartidas con el ML) | `localhost`, `5432`, `wayrapredict` |
| `WAYRA_API_DB_USER`, `WAYRA_API_DB_PASSWORD` | Usuario propio del backend | `wayra_api` y su contraseña |
| `WAYRA_JWT_SECRET` | Clave del token (≥ 64 caracteres, HS512) | texto aleatorio largo |
| `WAYRA_ADMIN_CORREO`, `WAYRA_ADMIN_PASSWORD` | Primer administrador (solo si no existe ninguno; contraseña ≥ 8) | tu correo y una contraseña |
| `WAYRA_CORS_ORIGENES` | Orígenes del frontend, separados por coma | `http://localhost:4200` |
| `WAYRA_API_PORT` | Puerto | `8080` |
| `WAYRA_GEMINI_API_KEY` | Clave de la API de Gemini (asistente). Si falta, todo funciona salvo el asistente, que responde 503 | clave de Google AI Studio |
| `WAYRA_GEMINI_MODELO` | Modelo principal del asistente | `gemini-3.6-flash` (el más rápido medido; `gemini-3.8-flash` tardaba más de 45 s en el plan gratuito) |
| `WAYRA_GEMINI_MODELO_RESPALDO` | Modelos de respaldo, en orden y separados por coma | `gemini-3.6-flash,gemini-3.5-flash-lite` |
| `WAYRA_GEMINI_RAZONAMIENTO` | Nivel de razonamiento: `minimal` (más rápido), `low`, `medium`, `high` | `minimal` |

En Windows (PowerShell), una sola vez:

```
setx WAYRA_API_DB_USER wayra_api
setx WAYRA_API_DB_PASSWORD "la_contraseña_de_wayra_api"
setx WAYRA_JWT_SECRET "una-clave-aleatoria-de-al-menos-64-caracteres-....................."
setx WAYRA_ADMIN_CORREO "tu_correo@dominio.pe"
setx WAYRA_ADMIN_PASSWORD "una_contraseña_segura"
```

`WAYRA_DB_HOST`, `WAYRA_DB_PORT` y `WAYRA_DB_NAME` tienen valores por defecto para la base local. Después de `setx`, cierra y vuelve a abrir la terminal o IntelliJ.

Para generar la clave JWT en PowerShell:

```
[Convert]::ToBase64String((1..64 | ForEach-Object { Get-Random -Maximum 256 }))
```

## 3. Ejecutar

- **Terminal** (dentro de `wayrapredict-api/`): `.\mvnw.cmd spring-boot:run`, o `.\mvnw.cmd package` y luego `java -jar target\wayrapredict-api-0.0.1-SNAPSHOT.jar`.
- **IntelliJ:** abrir la carpeta `wayrapredict-api` como proyecto Maven y ejecutar `WayrapredictApiApplication`. Las variables se pueden poner también en *Run/Debug Configurations → Environment variables*.
- **Swagger:** http://localhost:8080/doc/swagger-ui/index.html. Primero se inicia sesión en `POST /authenticate`, luego se copia `jwttoken` en "Authorize".
- **Pruebas:** `.\mvnw.cmd test`. Las pruebas unitarias (5 del JWT, 10 del cliente de Gemini y 3 del asistente) no necesitan la base ni gastan cuota de Gemini (la API se simula). La de arranque solo corre si existe `WAYRA_API_DB_USER`.

## 3b. Asistente con Gemini

- **Clases:** `AsistenteController` (`POST /api/libre/asistente`), `AsistenteService` (arma el contexto con estaciones, pronóstico de 1 a 3 días, alertas vigentes y categorías INCA desde la base, y aplica el límite por minuto) y `GeminiService` (llamada HTTP a la Interactions API con `RestClient`).
- **Llamada:** `POST https://generativelanguage.googleapis.com/v1beta/interactions?alt=sse` (respuesta por partes) con la cabecera `x-goog-api-key`, `store: false` (Google no guarda la conversación), `stream: true`, `system_instruction` (reglas y contexto), `generation_config` (`max_output_tokens` 2048, `thinking_level` minimal) e `input` con la conversación como pasos `user_input` / `model_output`. El texto llega en eventos `step.delta` y se reenvía al navegador apenas llega (cliente HTTP de Java, sin SDK).
- **Rapidez y disponibilidad:** si un modelo no empieza a responder en 8 s (15 s los respaldos) o responde 429/5xx, se pasa al siguiente **sin reintentar el mismo**; durante el minuto siguiente a un fallo del principal se va directo al respaldo. Si un modelo no admite el razonamiento `minimal` (p. ej. `gemini-3.8-flash`), se repite una vez con `low` y se recuerda. Un 400/401/403/404 (clave o modelo mal configurados) no prueba otros modelos; un 402 avisa que se acabó el saldo.
- **Tiempos medidos (08/11/2026, plan gratuito, en el navegador):** con `gemini-3.6-flash` la primera palabra aparece en 2,1 s y la respuesta completa en 2,8 s (promedio de 6 preguntas, todas < 5 s); `gemini-3.8-flash` tardaba de 48 a 118 s.
- **Privacidad:** el log registra modelo, estado, tiempo y tokens, nunca el texto de las preguntas ni la clave. No se guarda nada en la base.
- **Configuración** en `application.properties` (`wayra.gemini.*`, `wayra.asistente.preguntas-por-minuto`).

## 4. Endpoints

| Método y ruta | Acceso | Descripción |
|---|---|---|
| `POST /authenticate` | público | Login con `{correo, password}` → `{jwttoken, correo, rol, nombre, validezMs}`. Solo cuentas aprobadas (401 credenciales; 403 pendiente o rechazada) |
| `GET /api/libre/estaciones`, `/api/libre/estacion/{codigo}` | público | Estaciones con contaminante, ubicación, **fecha de referencia** (último dato medido), `ultimoValor` con su categoría INCA (`categoriaUltimoValor`, `colorUltimoValor`) y `ultimaActualizacionPredicciones` |
| `GET /api/libre/serie-diaria/{codigo}?desde&hasta` | público | Serie diaria para el gráfico y el tooltip: contaminante y meteorología con el **origen** de cada valor. Por defecto: 90 días hasta la referencia más los días con meteorología pronosticada (`posteriorAReferencia = true`) |
| `GET /api/libre/mediciones/{codigo}?desde&hasta&variable` | público | Lo mismo en formato largo (una fila por variable y día) |
| `GET /api/libre/predicciones-proximos-dias/{codigo}` | público | Próximos días desde la fecha de referencia. Salen de la **última ejecución** de la estación (vigente o respaldo), con `versionModelo` y `modeloVigente` |
| `GET /api/libre/predicciones-historial/{codigo}?desde&hasta` | público | Predicciones pasadas con el valor observado y su categoría INCA (`categoriaObservada`, `colorObservado`) |
| `GET /api/libre/alertas?estacion&estado` | público | Vista `v_alerta` (estado `vigente` o `finalizada`), con `estacionNombre` |
| `GET /api/libre/metricas-modelo-vigente?estacion` | público | "Desempeño del modelo": RMSE, MAE y R² del modelo vigente |
| `GET /api/libre/metricas-modelos?estacion` | público | Métricas de todas las versiones |
| `GET /api/libre/categorias-inca` | público | Leyenda del INCA |
| `POST /api/libre/asistente/stream` | público | Igual que el siguiente, pero la respuesta llega **por partes** (`text/event-stream`): eventos `texto` `{t}`, `fin` `{modelo, fechaDatos}` y `error` `{mensaje}`. Lo usa el panel del asistente. Los errores 400/404/429 se responden antes, en JSON |
| `POST /api/libre/asistente` | público | Asistente con Gemini: `{pregunta, estacion?, historial?}` → `{respuesta, fechaDatos, modelo}`. Responde con los datos reales de la base. 400 pregunta vacía o > 500 caracteres; 404 estación inexistente; 429 más de 10 preguntas por minuto por cliente; 503 Gemini no disponible |
| `POST /api/libre/solicitar-cuenta` | público | Solicitud de cuenta → usuario institucional `pendiente`. El correo debe terminar en `.gob.pe` y `aceptaTratamientoDatos` debe ser `true` (Ley N.° 29733) |
| `GET /api/cuenta/mi-perfil` | con sesión | Perfil del usuario que inició sesión |
| `GET /api/institucional/predicciones-por-verificar/{codigo}` | usuario_institucional | Predicciones pasadas sin verificar, con el valor observado |
| `PUT /api/institucional/verificar-prediccion/{id}` | usuario_institucional | Verifica la predicción (`verificado`, `verificado_por`, `fecha_verificacion`) |
| `GET /api/admin/usuarios?estado` | administrador | Lista los usuarios |
| `PUT /api/admin/aprobar-usuario/{id}` | administrador | Aprueba (registra `aprobado_por` y `fecha_aprobacion`) |
| `PUT /api/admin/rechazar-usuario/{id}` | administrador | Rechaza o revoca: el token del usuario deja de servir |
| `PUT /api/admin/cambiar-rol/{id}` | administrador | `{rol: administrador \| usuario_institucional}` |
| `GET /api/admin/ejecuciones` | administrador | Estado de las ejecuciones del proceso, con el número de predicciones y mediciones |

**Errores:** JSON en español con la forma `{fecha, estado, error, mensaje}` (400, 401, 403, 404 y 409).
