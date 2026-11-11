# WayraPredict · Componente de Machine Learning (modelo híbrido Prophet-LSTM)

Esta parte del proyecto prepara los datos de calidad del aire, entrena los modelos que **pronostican el promedio diario** de un contaminante para los próximos 1 a 3 días y carga los resultados en la base de datos que usa la plataforma web.

---

## 1. Qué hace, en palabras simples

1. **Junta los datos** de vigilancia de la calidad del aire del OEFA (Plataforma Nacional de Datos Abiertos) y los registros de alta resolución de las estaciones.
2. **Los limpia:**
   - quita valores imposibles y rachas de ceros del sensor;
   - reconstruye la hora cuando falta;
   - convierte unidades.
3. **Calcula promedios diarios.** Un día es válido si tiene al menos 18 horas con dato. La precipitación se suma y la dirección del viento se promedia como vector.
4. **Entrena un modelo híbrido por estación:**
   - **Prophet** aprende la tendencia y los ciclos (diferencias entre días de la semana y épocas del año).
   - Una **red neuronal LSTM** aprende de lo ocurrido en los días anteriores (el contaminante y la meteorología) y corrige lo que Prophet no explica.
   - El pronóstico final combina ambos e incluye un **intervalo de incertidumbre**.
5. **Evalúa** el modelo con datos que no usó para entrenar:
   - **error:** RMSE, MAE y R²;
   - **comparación:** contra modelos simples (persistencia, «mañana igual que hoy», y Prophet solo);
   - **alertas:** qué tan bien anticipa los días «Moderada» o peores del INCA.
6. **Clasifica** cada pronóstico según el **INCA** (Índice de Calidad del Aire del MINAM): INCA = concentración ÷ ECA-Aire de 24 h × 100 → Buena, Moderada, Mala o Umbral de cuidado.
7. **Carga** mediciones, modelos y predicciones en PostgreSQL. La API REST (backend) las lee y la aplicación web (frontend) las muestra.

## 2. Estaciones y contaminantes

| Departamento | Estación | Contaminante | Por qué |
|---|---|---|---|
| Junín | CA-CC-01 · La Oroya | SO₂ (dióxido de azufre) | Cerca de un complejo metalúrgico (fundición), que emite sobre todo SO₂ |
| Pasco | CA-HUAR-01 · Huaraucaca | PM10 (material particulado) | Zona de minería a tajo abierto |
| Moquegua | CA-ILO-02 · Ilo-Pacocha | PM10 | Zona industrial y minera |

Las estaciones se eligieron por cobertura de datos: suficientes días con medición y continuidad para entrenar y evaluar.

## 3. Versiones del modelo

| Versión | Qué es |
|---|---|
| v1 | Modelo híbrido Prophet-LSTM, con selección por horizonte (1, 2 o 3 días) usando la validación |
| v2 | Combinación de varios componentes, incluidos pronósticos meteorológicos de Open-Meteo para el día objetivo |
| v3 | Versión vigente en la plataforma: modelo híbrido Prophet-LSTM de la carpeta `modelo_hibrido/` |

La base de datos guarda las tres versiones de cada estación; una está marcada como **vigente**.

## 4. Reglas que siguen todos los modelos

- **Sin «trampa» temporal:** los datos se separan por fecha (entrenamiento → validación → prueba). La limpieza, el escalado y la elección de hiperparámetros solo usan el período de entrenamiento o de validación.
- **Escala logarítmica** `log(1 + x)` para entrenar y **corrección de Duan** al volver a µg/m³.
- **Validación con origen móvil (walk-forward):** el modelo se vuelve a ajustar a medida que avanza el tiempo, como ocurriría en la operación real.
- **Reproducibilidad:** semillas fijas y resultados guardados en archivos.

## 5. Scripts (en orden)

| Script | Qué hace |
|---|---|
| `wayra_comun.py` | Configuración compartida: rutas, estaciones, cortes de fechas, umbrales (ECA, OMS, INCA), métricas y carga de datasets |
| `wayra_alta_resolucion.py` | Lectura de los archivos de alta resolución (5 minutos) de las estaciones, sin modificar los originales |
| `wayra_prophet.py`, `wayra_lstm.py`, `wayra_hibrido.py` | Funciones de Prophet, de la LSTM (Keras/TensorFlow) y del híbrido |
| `00d`, `00f`, `00h` | Lectura y combinación de las fuentes de datos por estación |
| `01-EDA-CALIDAD_AIRE_v3.py`, `01b-EDA-ALTA-RESOLUCION.py` | Limpieza, validación, análisis exploratorio, INCA y dataset diario por estación |
| `02-PROPHET.py` | Prophet por estación (modelo base y componente del híbrido) |
| `03-LSTM.py` | LSTM sola (modelo base) |
| `04c-HIBRIDO_V2.py`, `04d-LSTM_GLOBAL.py` | Modelo híbrido y una LSTM entrenada con las tres estaciones a la vez |
| `motor.py` | Funciones de entrenamiento de los componentes del modelo (LSTM, combinación y búsqueda con Optuna) |
| `05-HIPERPARAMETROS.py` | Ajuste de hiperparámetros con Optuna, solo con datos de validación |
| `09-EXPORTAR_PLATAFORMA.py`, `09a-PRONOSTICO_ULTIMO_DATO.py` | Arma los archivos para la plataforma (mediciones, modelos, predicciones) y el pronóstico desde el último dato |
| `10-CARGAR_BD.py` | Carga todo en PostgreSQL en una sola transacción, sin duplicar si se repite |
| `modelo_hibrido/` | Modelo híbrido Prophet-LSTM vigente en la plataforma (ver su README) |

## 6. Herramientas

| Herramienta | Para qué |
|---|---|
| Python 3 (Spyder / Google Colab) | Lenguaje y entornos de trabajo. Los scripts se ejecutan por celdas (`# %%`) |
| pandas, NumPy | Manejo de datos |
| Prophet | Tendencia y estacionalidad |
| TensorFlow / Keras | Red neuronal LSTM |
| Optuna | Búsqueda de hiperparámetros (optimización bayesiana) |
| SciPy, statsmodels, scikit-learn | Pruebas estadísticas, métricas y descomposición de series |
| Matplotlib | Gráficos |
| Open-Meteo | Meteorología histórica y pronosticada |
| psycopg2 | Conexión con PostgreSQL para la carga |

## 7. Cómo se ejecuta

1. **Configurar los datos:** los datos de entrada (el archivo del OEFA y las carpetas `Datos_crudos_*`) no están en el repositorio por su tamaño (varios GB). Se colocan en esta carpeta (`3-ML/`).
2. **Correr los scripts** en el orden de la tabla anterior, desde Spyder (celda por celda) o con `python <script>.py`. Las rutas se configuran en `wayra_comun.py`; no hay rutas absolutas en el código.
3. **Cargar la base:** se definen las variables de entorno de conexión (`WAYRA_DB_HOST`, `WAYRA_DB_PORT`, `WAYRA_DB_NAME`, `WAYRA_DB_USER`, `WAYRA_DB_PASSWORD`) y se ejecuta `10-CARGAR_BD.py`. Las contraseñas **nunca** se escriben en el código.

El esquema de la base de datos está en `esquema_wayrapredict.sql`.

## 8. Relación con el resto de la plataforma

```
Datos OEFA ──► Scripts de ML (limpieza → modelo híbrido → predicciones) ──► PostgreSQL
                                                                              │
                                     API REST (Spring Boot) ◄─────────────────┘
                                              │
                                     Aplicación web (Angular)
```

El entrenamiento es un proceso periódico y manual (en Spyder o Google Colab). La plataforma solo lee los resultados guardados.
