# WayraPredict Web (Angular 22): segunda versión (rediseño)

Frontend de la plataforma WayraPredict. Consume la API REST del backend (`1-backend/wayrapredict-api`) con datos reales: estilo propio con acento verde azulado, fuente Lato, animaciones y modo noche.

## En palabras simples

Es la **página web** que ven las personas. No guarda datos propios: cada pantalla pide la información al backend (estaciones, pronósticos, alertas, cuentas) y la muestra con tarjetas, gráficos y tablas.

**Cómo está organizado:**
- **`component/`:** una carpeta por pantalla, más los componentes que se reutilizan (gráfico, barras, lista desplegable, encabezado, asistente).
- **`service/`:** las llamadas a la API.
- **`model/`:** la forma de los datos, igual que en el backend.
- **`interceptor/` y `guard/`:** la sesión (token JWT) y los permisos por rol.
- **`styles.css`:** el diseño (tema claro y modo noche).

**Herramientas:**
- **Base:** Angular 22 con componentes *standalone* y *signals*, en TypeScript.
- **Comunicación:** `HttpClient` y `fetch` (para la respuesta del asistente por partes).
- **Gráficos:** SVG propio, sin librerías.
- **Pruebas en el navegador:** Playwright con Microsoft Edge.

**En Azure** se publica como sitio estático en **Azure Static Web Apps** (plan Free). La dirección del backend en producción está en `src/environments/environment.prod.ts`.

## Cómo ejecutarlo

1. **Arranca el backend** (IntelliJ → `WayrapredictApiApplication`) y espera a ver `Tomcat started on port 8080`.
2. **Abre una terminal en esta carpeta** e instala las dependencias. Solo hace falta la primera vez:
   ```
   cd "C:\Users\danie\Downloads\PRUEBA_PROPHET-LSTM_OEFA\2-frontend\wayrapredict-web"
   npm install
   ```
3. **Inicia el frontend:**
   ```
   npm start
   ```
4. **Abre la plataforma** en http://localhost:4200.

El backend solo acepta peticiones desde `http://localhost:4200` (CORS). Si cambias el puerto del frontend, define `WAYRA_CORS_ORIGENES` en el backend.

La dirección del backend está en `src/environments/environment.ts` (`apiUrl`).

## Requisitos

- **Node.js 22.22 o superior** (probado con 24.19) y npm.
- **Angular 22:** el CLI se instala con el proyecto. No hace falta instalarlo de forma global; `npm start` usa el local.

## Pantallas (como en la referencia)

| Ruta | Pantalla | Acceso |
|---|---|---|
| `/login` | 1 · Iniciar sesión (con el aviso de cuenta pendiente o rechazada) | Público |
| `/registro` | 2 · Solicitar cuenta institucional (correo `.gob.pe`, contraseña ≥ 8, confirmación y Ley N.° 29733) | Público |
| `/registro-enviado` | 3 · Solicitud enviada | Público |
| `/dashboard` | 4 · Tarjetas de estaciones, alerta anticipada, gráfico (14 días + pronóstico) y próximos días | Público |
| `/estacion/:codigo` | 5 · Detalle: gráfico de 30 días + pronóstico, recomendaciones, meteorología, predicciones pasadas con verificación y desempeño del modelo | Público; el botón «Verificar» solo aparece para `usuario_institucional` |
| `/alertas` | 6 · Alertas vigentes y finalizadas con filtros y resumen | Público |
| (botón flotante) | 7 · Asistente: panel visible, **todavía sin respuestas** (la integración con Gemini es la siguiente fase) | Público |
| `/admin` | 8 · Usuarios y solicitudes (aprobar, rechazar o revocar, cambiar rol) y ejecuciones del proceso | **Solo `administrador`**: el menú no aparece y la ruta está protegida por un guard |
| `/ayuda` | 9 · Nosotros y preguntas frecuentes | Público |

## Estructura

```
src/
├── environments/environment.ts   dirección del backend
├── styles.css                    sistema de diseño: tokens del tema claro y del modo noche ([data-tema="oscuro"]), colores INCA y componentes
└── app/
    ├── app.config.ts             HttpClient con el interceptor del token, router
    ├── app.routes.ts             rutas, con dos layouts (acceso y aplicación)
    ├── model/                    interfaces con los mismos campos que los DTO del backend
    ├── service/                  LoginService (sesión), EstacionService, PrediccionService, UsuarioService, AvisoService, TemaService (claro / noche)
    ├── interceptor/              agrega "Authorization: Bearer <token>" y cierra la sesión si el backend responde 401
    ├── guard/                    authGuard (sesión) y adminGuard (rol administrador)
    ├── util/formato.ts           fechas, números, categorías INCA y nombres
    └── component/
        ├── layout/               AppLayout (barra lateral con el menú y «Cerrar sesión» abajo; barra superior con pestañas,
        │                         alertas, tema y «Salir») y AuthLayout (panel de marca)
        ├── shared/               Encabezado (título de cada pantalla), GraficoSerie (gráfico SVG animado), BarrasDias (barras animadas)
        │                         y ChatAsistente
        └── login, registro, dashboard, estacion, alertas, admin, ayuda
```

## Decisiones

- **Componentes standalone y servicios con `HttpClient`,** igual que el ejemplo del curso (`2-frontend/ejemplo1`). El estado de cada pantalla usa *signals*, porque Angular 22 trabaja sin zone.js.
- **Sin Angular Material ni `angular-jwt`.** El diseño es CSS propio, y menos dependencias evitan problemas de compatibilidad.
- **Tema claro y modo noche:** botón en la barra superior y en la barra lateral. Se guarda en `localStorage` (`wayra-tema`); la primera vez se usa el tema del sistema. Un script en `index.html` lo aplica antes de pintar, para evitar el parpadeo.
- **Sesión:**
  - el token y los datos del usuario (correo, rol y nombre, que devuelve `/authenticate`) se guardan en `sessionStorage` y se borran al cerrar el navegador;
  - el token vence a las 7 horas;
  - el interceptor cierra la sesión si el backend responde 401, por ejemplo si un administrador revocó la cuenta.
- **El gráfico es SVG propio, sin librerías:**
  - dibuja las bandas INCA, el ECA de 24 h, la guía OMS, la línea del día actual, la serie observada (curva suave con área en degradado) y el pronóstico punteado con su intervalo;
  - la curva se dibuja con animación cada vez que cambian los datos (por ejemplo, al cambiar de estación o de departamento);
  - al pasar el cursor muestra una guía vertical y un recuadro con la fecha, el valor observado y su origen, la predicción con su intervalo y la categoría INCA.
- **Filtros del dashboard:** al elegir un departamento o un contaminante, el gráfico y los próximos días pasan a la primera estación visible; si ninguna estación coincide, el gráfico se oculta. Usan el componente `shared/desplegable` (lista animada, accesible con teclado y que se cierra al hacer clic fuera).
- **Fechas:** «Predicciones cargadas el» es el `fecha_fin` de la ejecución del proceso que registró las predicciones (cuándo se cargaron en la base). El «día actual» de cada estación es otra fecha: el último día con medición considerado (último dato − 3 días en la v3).
- **Preguntas frecuentes:** acordeón propio que se desliza al abrir y cerrar (en lugar de `<details>`, que no se puede animar en todos los navegadores).
- **«Día actual» de cada estación:** es la fecha de referencia que entrega el backend, es decir, el último día con medición. Los próximos días son los pronósticos de 1 a 3 días desde esa fecha.

## Probado (05/11/2026)

Rediseño (Playwright + Edge, tema claro y noche, escritorio y 390 px de ancho): el gráfico cambia al elegir Junín, Pasco o Moquegua y al filtrar por contaminante; el cambio de departamento en el detalle de estación navega a la estación correcta; el tema se recuerda; el administrador ve su nombre, correo y rol arriba de la barra lateral, y tanto «Cerrar sesión» como «Salir» cierran la sesión; sin errores en la consola ni desplazamiento horizontal en el celular.

Primera versión:

Con el backend conectado como `wayra_api` y los datos de la versión 3:
- **Pantallas públicas** (dashboard, estación, alertas, ayuda, login y registro): sin errores en la consola del navegador.
- **Flujo completo en el navegador:**
  1. la solicitud con un correo que no es `.gob.pe` muestra el error;
  2. con un correo válido, la solicitud se envía;
  3. el login pendiente muestra «La cuenta está pendiente de aprobación»;
  4. el administrador aprueba desde Administración;
  5. la autoridad inicia sesión y verifica una predicción, que pasa a mostrar «Verificado por autoridad»;
  6. la autoridad que intenta entrar a `/admin` vuelve al dashboard.
- **Datos de prueba:** se borraron al terminar.

## Pendiente

- ~~Asistente con Gemini~~: hecho (06/11/2026). El panel usa `POST /api/libre/asistente`; la clave de Gemini solo existe en el backend.
- **Diseño para móviles:** ya funciona (la barra lateral se abre con el botón de menú), pero falta revisarlo pantalla por pantalla.
- **Correo de contacto y enlaces legales,** que la referencia deja pendientes.
