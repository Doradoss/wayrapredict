# WayraPredict

**Plataforma de vigilancia predictiva de la calidad del aire** en zonas con actividad minero-industrial del Perú (Junín, Pasco y Moquegua).

WayraPredict pronostica el promedio diario de contaminantes (SO₂ y PM10) para los próximos días con un **modelo híbrido Prophet-LSTM**, clasifica cada pronóstico según el **Índice de Calidad del Aire (INCA)** del MINAM, avisa con **alertas** cuando se espera calidad Moderada o peor y lo explica en lenguaje sencillo con un **asistente conversacional** (Gemini).

> Proyecto de tesis de Ingeniería de Sistemas de Información (UPC). Autores: Daniel Bustamante Cabrera y Kevin Ayquipa Villar. Su nombre une *wayra* («aire» en quechua) y *predict*.

---

## Arquitectura

```
                         Usuarios: ciudadanía · personal de instituciones · administradores
                                               │ HTTPS
                                               ▼
                     ┌──────────────────────────────────────────────┐
                     │  Frontend · Angular (Azure Static Web Apps)  │
                     └──────────────────────────────────────────────┘
                                               │ API REST (JSON)
                                               ▼
                     ┌──────────────────────────────────────────────┐        ┌──────────────────┐
                     │  Backend · Spring Boot (Azure App Service)   │──────► │  API de Gemini   │
                     │  autenticación JWT · roles · asistente       │ HTTPS  │  (asistente)     │
                     └──────────────────────────────────────────────┘        └──────────────────┘
                                               │ JDBC (SSL)
                                               ▼
                     ┌───────────────────────────────┐   ┌──────────────────────────────┐
                     │  PostgreSQL (Azure Database)  │   │  Azure Blob Storage (modelos) │
                     └───────────────────────────────┘   └──────────────────────────────┘
                                               ▲
                     ┌──────────────────────────────────────────────┐
                     │  Machine Learning · Python (Prophet + LSTM)  │ ◄── Datos abiertos del OEFA
                     │  entrenamiento y carga de predicciones       │
                     └──────────────────────────────────────────────┘
```

| Capa | Tecnología | Carpeta | Documentación |
|---|---|---|---|
| Presentación | Angular 22 (TypeScript), CSS propio, gráficos SVG | `2-frontend/wayrapredict-web` | [README del frontend](2-frontend/wayrapredict-web/README.md) |
| Negocio (API REST) | Spring Boot 4.1 (Java 17), Spring Security + JWT, Spring Data JPA | `1-backend/wayrapredict-api` | [README del backend](1-backend/wayrapredict-api/README.md) |
| Datos | PostgreSQL 16 | `3-ML/esquema_wayrapredict.sql` | Esquema con 8 tablas y la vista `v_alerta` |
| Modelo de predicción | Python: Prophet, TensorFlow/Keras (LSTM), Optuna | `3-ML` | [README del ML](3-ML/README.md) |
| Asistente | API de Gemini (Interactions API), a través del backend | `1-backend/.../GeminiService.java` | Sección «Asistente» del README del backend |

## Qué puede hacer cada usuario

| Usuario | Acceso |
|---|---|
| Ciudadanía (sin cuenta) | Ver el inicio con las estaciones y su pronóstico, el detalle de cada estación, las alertas, la ayuda y el asistente |
| Usuario institucional (correo `.gob.pe`, cuenta aprobada) | Además, verificar las predicciones pasadas («Verificado por autoridad») |
| Administrador | Aprobar o rechazar cuentas, cambiar roles y revisar las ejecuciones del proceso de carga |

## Cómo ejecutarlo en una computadora

Guía paso a paso: [COMO_ENCENDER_LA_APLICACION.md](COMO_ENCENDER_LA_APLICACION.md).

En resumen:
1. **Base de datos:** PostgreSQL 16 con la base `wayrapredict` (esquema en `3-ML/esquema_wayrapredict.sql`, datos cargados con `3-ML/10-CARGAR_BD.py`).
2. **Backend:** `cd 1-backend/wayrapredict-api` y `./mvnw spring-boot:run`. Escucha en http://localhost:8080 y la documentación Swagger está en `/doc/swagger-ui/index.html`.
3. **Frontend:** `cd 2-frontend/wayrapredict-web`, luego `npm install` y `npm start`. Se abre en http://localhost:4200.

Las contraseñas y claves se leen de **variables de entorno**; nunca están en el código (ver el README del backend).

## Despliegue en la nube (Microsoft Azure)

| Componente | Servicio de Azure | Plan |
|---|---|---|
| Frontend | Azure Static Web Apps | Free |
| Backend | Azure App Service (Linux, Java 17) | B1 |
| Base de datos | Azure Database for PostgreSQL – Flexible Server | Burstable B1ms, 32 GB |
| Archivos de los modelos | Azure Blob Storage | Standard LRS |

Cada cambio que se sube a la rama `main` se publica automáticamente con **GitHub Actions** (`.github/workflows/`). Las claves de producción se guardan cifradas en la configuración de Azure y en los secretos del repositorio.

## Estructura del repositorio

```
├── 1-backend/wayrapredict-api/     API REST (Spring Boot)
├── 1-backend/sql/                  usuario de base de datos con permisos mínimos
├── 2-frontend/wayrapredict-web/    aplicación web (Angular)
├── 3-ML/                           modelo de Machine Learning (Python)
│   ├── 01-…10-*.py, wayra_*.py     preparación de datos, entrenamiento y carga en la base
│   ├── modelo_hibrido/             modelo híbrido Prophet-LSTM que usa la plataforma
│   └── esquema_wayrapredict.sql    esquema de la base de datos
└── COMO_ENCENDER_LA_APLICACION.md  guía para ejecutarlo localmente
```

Los datos de entrada (varios GB), los modelos entrenados y los resultados intermedios no se incluyen por su tamaño.

## Fuente de datos

Vigilancia y seguimiento ambiental de la calidad del aire del **OEFA**, publicado en la Plataforma Nacional de Datos Abiertos del Perú. Umbrales: ECA-Aire (D.S. 003-2017-MINAM), guía de la OMS (2021) e INCA del MINAM.
