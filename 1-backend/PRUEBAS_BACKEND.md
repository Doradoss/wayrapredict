# Pruebas del backend WayraPredict y comparación con el mockup del frontend (02/11/2026)

## 1. Resumen

- **55 de 55 pruebas de la API pasaron**, sin errores. Es la segunda corrida, hecha después de implementar los cambios de la sección 5; la primera tuvo 52 de 52. Las respuestas tardaron entre 2 y 600 ms; la más lenta fue la primera carga de la especificación OpenAPI.
- **Pruebas unitarias (`mvnw test`):** 5 de 5 pasan (JWT). La prueba de arranque se salta, como estaba previsto, porque aún no existe `WAYRA_API_DB_USER`.
- **Base de datos:** las pruebas se hicieron contra la base real `wayrapredict` con la **versión 3 cargada** (v3 vigente en las tres estaciones). Todo lo que las pruebas escribieron se revirtió al terminar:
  - la tabla `usuario` volvió a quedar vacía;
  - la predicción verificada volvió a `verificado = false`.
- **Swagger:** disponible en `http://localhost:8080/doc/swagger-ui/index.html`, con 20 rutas documentadas en `/v3/api-docs`.

## 2. Cómo se probó

1. Se compiló el proyecto con `.\mvnw.cmd package` y se ejecutó el `.jar` en el puerto 8080.
2. **Conexión:** el usuario `postgres`, porque `wayra_api` todavía no está creado.
3. **Administrador de prueba temporal:** `admin.pruebas@wayrapredict.pe`. Lo crea `InicializadorAdministrador` a partir de las variables `WAYRA_ADMIN_*` y se borró al terminar.
4. **Clave JWT aleatoria:** solo para esta corrida.
5. **Script de pruebas en Python:** hace las peticiones HTTP una por una y compara el código de estado obtenido con el esperado. Cubre:
   - endpoints públicos;
   - login;
   - solicitud y aprobación de cuentas;
   - permisos por rol;
   - verificación de predicciones;
   - administración;
   - errores (400, 401, 403, 404 y 409);
   - Swagger.
6. **Flujo completo probado:**
   - un ciudadano consulta sin cuenta;
   - un institucional solicita su cuenta;
   - el login con la cuenta pendiente se rechaza (403);
   - el administrador aprueba la cuenta;
   - el institucional inicia sesión y verifica una predicción;
   - una segunda verificación de la misma predicción da 409;
   - el administrador revoca la cuenta y el token del institucional deja de servir (401).

## 3. Resultados de cada prueba

| # | Prueba | Método y ruta | Esperado | Obtenido | ms | Resultado |
|---|---|---|---|---|---|---|
| 1 | Lista de estaciones | `GET /api/libre/estaciones` | 2xx | 200 | 335 | ✅ |
| 2 | Estación por código | `GET /api/libre/estacion/CA-CC-01` | 2xx | 200 | 35 | ✅ |
| 3 | Estación inexistente | `GET /api/libre/estacion/XX-00` | 404 | 404 | 18 | ✅ |
| 4 | Serie diaria por defecto CA-CC-01 | `GET /api/libre/serie-diaria/CA-CC-01` | 2xx | 200 | 46 | ✅ |
| 5 | Próximos días CA-CC-01 | `GET /api/libre/predicciones-proximos-dias/CA-CC-01` | 2xx | 200 | 35 | ✅ |
| 6 | Serie diaria por defecto CA-HUAR-01 | `GET /api/libre/serie-diaria/CA-HUAR-01` | 2xx | 200 | 23 | ✅ |
| 7 | Próximos días CA-HUAR-01 | `GET /api/libre/predicciones-proximos-dias/CA-HUAR-01` | 2xx | 200 | 10 | ✅ |
| 8 | Serie diaria por defecto CA-ILO-02 | `GET /api/libre/serie-diaria/CA-ILO-02` | 2xx | 200 | 22 | ✅ |
| 9 | Próximos días CA-ILO-02 | `GET /api/libre/predicciones-proximos-dias/CA-ILO-02` | 2xx | 200 | 10 | ✅ |
| 10 | Serie diaria con rango | `GET /api/libre/serie-diaria/CA-HUAR-01?desde=2026-06-01&hasta=2026-06-27` | 2xx | 200 | 15 | ✅ |
| 11 | Mediciones en formato largo (PM10) | `GET /api/libre/mediciones/CA-HUAR-01?desde=2026-06-20&hasta=2026-06-27&variable=PM10` | 2xx | 200 | 16 | ✅ |
| 12 | Historial de predicciones | `GET /api/libre/predicciones-historial/CA-ILO-02?desde=2026-05-15&hasta=2026-05-28` | 2xx | 200 | 20 | ✅ |
| 13 | Rango de fechas inválido | `GET /api/libre/predicciones-historial/CA-ILO-02?desde=2026-05-28&hasta=2026-05-01` | 400 | 400 | 7 | ✅ |
| 14 | Alertas (todas) | `GET /api/libre/alertas` | 2xx | 200 | 110 | ✅ |
| 15 | Alertas vigentes | `GET /api/libre/alertas?estado=vigente` | 2xx | 200 | 9 | ✅ |
| 16 | Alertas finalizadas de La Oroya | `GET /api/libre/alertas?estacion=CA-CC-01&estado=finalizada` | 2xx | 200 | 16 | ✅ |
| 17 | Alertas con estado inválido | `GET /api/libre/alertas?estado=otro` | 400 | 400 | 5 | ✅ |
| 18 | Métricas del modelo vigente | `GET /api/libre/metricas-modelo-vigente` | 2xx | 200 | 13 | ✅ |
| 19 | Métricas de todas las versiones (La Oroya) | `GET /api/libre/metricas-modelos?estacion=CA-CC-01` | 2xx | 200 | 8 | ✅ |
| 20 | Categorías INCA | `GET /api/libre/categorias-inca` | 2xx | 200 | 15 | ✅ |
| 21 | Login administrador | `POST /authenticate` | 2xx | 200 | 326 | ✅ |
| 22 | Login con contraseña incorrecta | `POST /authenticate` | 401 | 401 | 70 | ✅ |
| 23 | Perfil sin token | `GET /api/cuenta/mi-perfil` | 401 | 401 | 8 | ✅ |
| 24 | Perfil con token (administrador) | `GET /api/cuenta/mi-perfil` | 2xx | 200 | 62 | ✅ |
| 25 | Token inválido | `GET /api/cuenta/mi-perfil` | 401 | 401 | 4 | ✅ |
| 26 | Solicitar cuenta | `POST /api/libre/solicitar-cuenta` | 201 | 201 | 88 | ✅ |
| 27 | Solicitar cuenta con correo repetido | `POST /api/libre/solicitar-cuenta` | 409 | 409 | 7 | ✅ |
| 28 | Solicitar cuenta con datos inválidos | `POST /api/libre/solicitar-cuenta` | 400 | 400 | 32 | ✅ |
| 29 | Solicitar cuenta con correo que no es .gob.pe | `POST /api/libre/solicitar-cuenta` | 400 | 400 | 4 | ✅ |
| 30 | Solicitar cuenta sin aceptar el tratamiento de datos | `POST /api/libre/solicitar-cuenta` | 400 | 400 | 4 | ✅ |
| 31 | Solicitar cuenta sin el campo de aceptación | `POST /api/libre/solicitar-cuenta` | 400 | 400 | 4 | ✅ |
| 32 | Login con cuenta pendiente | `POST /authenticate` | 403 | 403 | 69 | ✅ |
| 33 | Usuarios pendientes (administrador) | `GET /api/admin/usuarios?estado=pendiente` | 2xx | 200 | 16 | ✅ |
| 34 | Aprobar usuario | `PUT /api/admin/aprobar-usuario/6` | 2xx | 200 | 32 | ✅ |
| 35 | Login institucional aprobado | `POST /authenticate` | 2xx | 200 | 72 | ✅ |
| 36 | Perfil institucional | `GET /api/cuenta/mi-perfil` | 2xx | 200 | 11 | ✅ |
| 37 | Institucional entra a administración | `GET /api/admin/usuarios` | 403 | 403 | 11 | ✅ |
| 38 | Administrador entra a verificación | `GET /api/institucional/predicciones-por-verificar/CA-CC-01` | 403 | 403 | 7 | ✅ |
| 39 | Ciudadano (sin token) entra a verificación | `GET /api/institucional/predicciones-por-verificar/CA-CC-01` | 401 | 401 | 3 | ✅ |
| 40 | Predicciones por verificar | `GET /api/institucional/predicciones-por-verificar/CA-CC-01` | 2xx | 200 | 41 | ✅ |
| 41 | Verificar una predicción | `PUT /api/institucional/verificar-prediccion/3594` | 2xx | 200 | 37 | ✅ |
| 42 | Verificar la misma predicción otra vez | `PUT /api/institucional/verificar-prediccion/3594` | 409 | 409 | 11 | ✅ |
| 43 | Verificar una predicción inexistente | `PUT /api/institucional/verificar-prediccion/999999999` | 404 | 404 | 11 | ✅ |
| 44 | Historial muestra la verificación | `GET /api/libre/predicciones-historial/CA-CC-01?desde=2025-09-01&hasta=2025-09-01` | 2xx | 200 | 11 | ✅ |
| 45 | Lista de usuarios (todos) | `GET /api/admin/usuarios` | 2xx | 200 | 12 | ✅ |
| 46 | Cambiar rol con valor inválido | `PUT /api/admin/cambiar-rol/6` | 400 | 400 | 10 | ✅ |
| 47 | Usuarios aprobados | `GET /api/admin/usuarios?estado=aprobado` | 2xx | 200 | 9 | ✅ |
| 48 | Administrador intenta cambiar su propio rol | `PUT /api/admin/cambiar-rol/5` | 409 | 409 | 10 | ✅ |
| 49 | Administrador intenta rechazarse | `PUT /api/admin/rechazar-usuario/5` | 409 | 409 | 9 | ✅ |
| 50 | Estado de las ejecuciones | `GET /api/admin/ejecuciones` | 2xx | 200 | 32 | ✅ |
| 51 | Rechazar (revocar) al institucional | `PUT /api/admin/rechazar-usuario/6` | 2xx | 200 | 11 | ✅ |
| 52 | Token del usuario revocado | `GET /api/cuenta/mi-perfil` | 401 | 401 | 5 | ✅ |
| 53 | Login del usuario rechazado | `POST /authenticate` | 403 | 403 | 67 | ✅ |
| 54 | Swagger UI | `GET /doc/swagger-ui/index.html` | 2xx | 200 | 36 | ✅ |
| 55 | Especificación OpenAPI | `GET /v3/api-docs` | 2xx | 200 | 511 | ✅ |

## 4. Qué devuelve la API con la versión 3 (comprobado)

| Dato | Valor devuelto |
|---|---|
| Fecha de referencia ("día actual") | CA-CC-01 25/06, CA-HUAR-01 27/06, CA-ILO-02 28/05 |
| Próximos días | 3 por estación, todos `versionModelo = v3`, `modeloVigente = true`, categoría "Buena", con intervalo y recomendación |
| Métricas del modelo vigente (prueba a 1 día) | CA-CC-01 RMSE 25,36 / MAE 19,16 / R² 0,77; CA-HUAR-01 5,64 / 3,77 / 0,91; CA-ILO-02 4,79 / 3,21 / 0,83 |
| Alertas | 36 finalizadas (Moderada o Mala), 0 vigentes (los próximos días son "Buena") |
| Serie diaria por defecto | 96 días: 90 hasta la referencia más los 3 días siguientes, con la meteorología de cada día y su origen |
| Historial | Predicción, observado, origen del observado, verificado, quién verificó y cuándo |
| Errores | JSON en español, por ejemplo `{"estado": 403, "mensaje": "La cuenta está pendiente de aprobación por un administrador"}` |

**Ajustes hechos en la base durante esta revisión** (con `10-CARGAR_BD.py`; no cambió el esquema):
- **Fecha de las ejecuciones 2 y 3:** pasó a la de la carga de la v3, porque es la que se mostraría como "Última actualización de predicciones".
- **Meteorología pronosticada:** se quitó la de los días posteriores al último dato real (45 filas). Ya no corresponde a los 3 días que se pronostican, que tienen meteorología medida.

## 5. Mockup del frontend frente a la API

Referencia: `wayrapredict-referencia-frontend.html`, con 9 pantallas.

| Pantalla | Qué necesita | API que lo cubre | Estado |
|---|---|---|---|
| 1 Iniciar sesión | Login, aviso de cuenta pendiente | `POST /authenticate` (401 credenciales; 403 pendiente o rechazada, con mensaje) | ✅ |
| 2 Solicitar cuenta | Nombres, apellidos, correo, institución, cargo, contraseña, aceptación de la Ley 29733 | `POST /api/libre/solicitar-cuenta` | ✅ **Nuevo:** el correo debe terminar en `.gob.pe` y se exige `aceptaTratamientoDatos = true`. La confirmación de la contraseña se resuelve en el frontend |
| 3 Solicitud enviada | Pantalla estática | — | ✅ |
| 4 Dashboard: tarjetas | Departamento, estación, código, contaminante | `GET /api/libre/estaciones` | ✅ |
| 4 Dashboard: "Último promedio diario" y su categoría | Valor del día de referencia y categoría INCA | `GET /api/libre/estaciones` | ✅ **Nuevo:** `ultimoValor`, `ultimoValorInca`, `categoriaUltimoValor` y `colorUltimoValor` |
| 4 Dashboard: franja Mañana / +2 d / +3 d | Categoría de los 3 próximos días | `GET /api/libre/predicciones-proximos-dias/{codigo}` | ✅ |
| 4 Dashboard: aviso de alerta | Alertas vigentes | `GET /api/libre/alertas?estado=vigente` | ✅ |
| 4 Dashboard: "Última actualización de predicciones" | Fecha y hora de la última ejecución | `GET /api/libre/estaciones` | ✅ **Nuevo:** `ultimaActualizacionPredicciones`, la fecha de fin de la última ejecución con predicciones de la estación |
| 4 / 5 Gráfico | Serie observada, pronóstico, intervalo, bandas INCA, ECA y OMS | `serie-diaria` + `predicciones-proximos-dias` + `categorias-inca` + `eca24h` y `oms24h` de `/estaciones` | ✅ El mockup muestra 5–7 días de pronóstico; el modelo da 3 |
| 5 Recomendaciones | Recomendación según la categoría prevista | Campo `recomendacion` de cada predicción | ✅ |
| 5 Condiciones meteorológicas recientes | Temperatura, humedad, viento, precipitación | `serie-diaria` (con el origen de cada valor) | ✅ |
| 5 Predicciones pasadas y verificación | Previsto, observado, categoría observada, distintivo y botón «Verificar» | `predicciones-historial` y `PUT /api/institucional/verificar-prediccion/{id}` | ✅ **Nuevo:** `categoriaObservada` y `colorObservado`. El botón «Verificar» se muestra solo con rol institucional |
| 5 Desempeño del modelo | RMSE, MAE y R² | `GET /api/libre/metricas-modelo-vigente?estacion=` | ✅ |
| Barra superior con usuario | Nombre, rol, institución | `GET /api/cuenta/mi-perfil` | ✅ |
| 6 Alertas: tabla | Estado, fecha prevista, departamento, estación, contaminante, valor, categoría, supera ECA | `GET /api/libre/alertas` (vista `v_alerta`) | ✅ **Nuevo:** `estacionNombre` ("La Oroya") |
| 6 Alertas: resumen y filtros | Conteos (vigentes, con superación del ECA, estaciones con alerta) y filtros | Se calculan en el frontend sobre la misma lista | ✅ |
| 7 Asistente | Preguntas y respuestas en lenguaje sencillo | — | ❌ **Falta** (fase posterior con Gemini, decidida en instrucciones_13) |
| 8 Administración: usuarios | Lista, búsqueda, aprobar, rechazar, cambiar rol, aviso de pendientes | `GET /api/admin/usuarios?estado=`, `PUT aprobar-usuario`, `rechazar-usuario`, `cambiar-rol` | ✅ **Solo administradores**: `/api/admin/**` exige el rol; probado: institucional → 403 y ciudadano → 401. La búsqueda se hace en el frontend |
| 8 Administración: última ejecución del proceso | Pasos con estado y fecha | `GET /api/admin/ejecuciones` | ⚠️ La tabla no tiene "tipo de paso". El mockup muestra 3 pasos (carga de datos, predicciones, clasificación). Por ahora se pueden mostrar las ejecuciones con su número de predicciones y mediciones |
| 9 Nosotros y FAQ | Contenido estático | — | ✅ |

## 6. Qué falta para terminar el backend

**A. Tareas tuyas (configuración, una sola vez):**
1. Ejecutar `sql/crear_usuario_wayra_api.sql` en pgAdmin, cambiando antes `CAMBIAR_ESTA_CONTRASENA`.
2. Definir las variables de entorno del README:
   - `WAYRA_API_DB_USER` y `WAYRA_API_DB_PASSWORD`;
   - `WAYRA_JWT_SECRET`, de 64 caracteres o más;
   - `WAYRA_ADMIN_CORREO` y `WAYRA_ADMIN_PASSWORD`. **Con estas dos el backend crea tu administrador real la primera vez que arranca**, porque hoy no hay ningún usuario.
3. Arrancar el backend con `wayra_api` y confirmar que funcionan la verificación y el alta de usuarios, y que cualquier otra escritura falla.

**B. Cambios implementados el 02/11/2026** (sin tocar el esquema de la base; compila y pasa las pruebas):
1. Solicitud de cuenta: el correo debe terminar en `.gob.pe` y `aceptaTratamientoDatos` debe ser `true` (Ley N.° 29733).
   **El frontend debe enviar ese campo.** La aceptación no se guarda en la base: sin ella, la solicitud no se registra.
2. `/api/libre/estaciones` y `/estacion/{codigo}`: agregan `ultimoValor`, `ultimoValorInca`, `categoriaUltimoValor`, `colorUltimoValor` y
   `ultimaActualizacionPredicciones`.
3. `predicciones-historial` (y `predicciones-por-verificar`): agregan `categoriaObservada` y `colorObservado`.
4. `alertas`: agrega `estacionNombre`.
5. Pendiente para más adelante: el endpoint del asistente (Gemini).

Los pasos de configuración están explicados en palabras simples en `PASOS_PGADMIN_Y_ARRANQUE.md`.

**C. No hace falta cambiar el esquema de la base:** ya tiene todo lo que pide el mockup (nombres, apellidos, institución, cargo, verificación y recomendaciones). El esquema real exportado está en `sql/esquema_actual_wayrapredict.sql`.
