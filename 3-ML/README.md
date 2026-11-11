# WayraPredict · Componente de Machine Learning (modelo híbrido Prophet-LSTM)

Esta carpeta prepara los datos de calidad del aire, entrena los modelos que **pronostican el promedio diario** de un contaminante para los próximos 1 a 3 días y genera los archivos que se cargan en la base de datos de la plataforma web.

---

## 1. Qué hace, en palabras simples

1. **Junta los datos** de vigilancia de la calidad del aire del OEFA y los registros de alta resolución de las estaciones.
2. **Los limpia:** quita valores imposibles y rachas de ceros del sensor, reconstruye la hora cuando falta y convierte unidades.
3. **Calcula promedios diarios.** Un día es válido si tiene al menos 18 horas con dato.
4. **Entrena un modelo híbrido por estación:**
   - **Prophet** aprende la tendencia y los ciclos (semana y año).
   - Una **red neuronal LSTM** aprende de los días anteriores y corrige lo que Prophet no explica.
   - El pronóstico final combina ambos e incluye un **intervalo de incertidumbre**, que se usa para las alertas.
5. **Clasifica** cada pronóstico según el **INCA** del MINAM: INCA = concentración ÷ ECA-Aire de 24 h × 100 → Buena, Moderada, Mala o Umbral de cuidado.
6. **Carga** mediciones, modelos y predicciones en PostgreSQL. El backend las lee y la web las muestra.

## 2. Estaciones

| Departamento | Estación | Contaminante |
|---|---|---|
| Junín | CA-CC-01 · La Oroya | SO₂ (dióxido de azufre) |
| Pasco | CA-HUAR-01 · Huaraucaca | PM10 (material particulado) |
| Moquegua | CA-ILO-02 · Ilo-Pacocha | PM10 |

## 3. Versiones del modelo

La base de datos guarda las predicciones **por versión de modelo**, y una versión está marcada como **vigente** en cada estación. La plataforma usa la **v3**.

| Versión | Qué es | En este repositorio |
|---|---|---|
| v1 | Primer modelo híbrido Prophet-LSTM, entrenado con las mediciones del contaminante y la meteorología de la estación | Scripts `02`–`05` y `04c`, con sus modelos en `modelos/` (demostrativa) |
| v2 | Combinación de varios componentes que agrega pronósticos meteorológicos de Open-Meteo | Componentes guardados en `v2/` (demostrativa; la v3 parte de su configuración) |
| **v3 (vigente)** | Modelo híbrido Prophet-LSTM entrenado con el **dataset enriquecido** | Carpeta `modelo_hibrido/` (pasos 1 a 7) |

La v1 y la v2 se conservan para mostrar la evolución del modelo y porque sus predicciones siguen en la base como versiones anteriores.

## 4. Carpetas

| Carpeta | Contenido |
|---|---|
| `checkpoints/` | Datasets diarios de las tres estaciones (`03_dataset_*`) y resultados intermedios del modelo base (pronósticos de Prophet, hiperparámetros, selección del híbrido) |
| `modelos/` | Modelos entrenados de la v1 (Prophet, LSTM e híbrido) |
| `v2/` | Componentes de la v2 y los pronósticos meteorológicos que usan |
| `modelo_hibrido/` | **Modelo vigente (v3):** scripts y, al ejecutarlos, sus datos, modelos y archivos para la plataforma |
| `plataforma/` | Archivos base para la carga (estaciones, mediciones, modelos y predicciones de la v1 y la v2) |

## 5. Scripts

**Funciones compartidas** (las usan todos los demás):

| Script | Qué hace |
|---|---|
| `wayra_comun.py` | **El más importante:** configuración (rutas, estaciones, cortes de fechas), umbrales (ECA, OMS, INCA), métricas y carga de datasets |
| `wayra_prophet.py` | Prophet: ajuste, pronóstico y validación con origen móvil |
| `wayra_lstm.py` | Red LSTM (Keras): ventanas de entrada, entrenamiento con semilla fija y pronóstico |
| `wayra_hibrido.py` | Combinación Prophet + LSTM, corrección de Duan y reglas de alerta |
| `motor.py` | Entrena los componentes del híbrido (LSTM con pronóstico meteorológico) y elige el peso de Prophet con la validación |
| `wayra_alta_resolucion.py` | Lee los archivos de 5 minutos de las estaciones, sin modificarlos |

**1. Preparación de datos** (necesitan los datos crudos del OEFA, que no se incluyen por su tamaño; sus resultados, los datasets diarios, ya están en `checkpoints/`):

| Script | Qué hace |
|---|---|
| `01-EDA-CALIDAD_AIRE_v3.py` | Limpieza y análisis del archivo del OEFA: valida horas, quita valores inválidos y arma el dataset diario |
| `01b-EDA-ALTA-RESOLUCION.py` | Lo mismo con los registros de alta resolución de La Oroya y la serie combinada |
| `00d-INVENTARIO_PASCO_MOQUEGUA.py` | Lee los archivos de Pasco y Moquegua y arma sus datasets diarios |
| `00f-HUARAUCACA_COMBINADA.py`, `00h-ILO_COMBINADA.py` | Completan Huaraucaca con la estación vecina y arman el dataset de Ilo |

**2. Modelo base (v1)** (se ejecutan por fuente: `WAYRA_FUENTE=combinada` para La Oroya y `WAYRA_FUENTE=pasco_moquegua` para Pasco y Moquegua):

| Script | Qué hace |
|---|---|
| `05-HIPERPARAMETROS.py` | Busca los hiperparámetros de Prophet y de la LSTM con Optuna, solo con la validación |
| `02-PROPHET.py` | Prophet por estación, con validación de origen móvil |
| `03-LSTM.py` | LSTM sola, como modelo de comparación |
| `04d-LSTM_GLOBAL.py` | LSTM entrenada con las tres estaciones a la vez |
| `04c-HIBRIDO_V2.py` | **Híbrido de la v1:** combina Prophet y LSTM y elige la mejor variante por horizonte |

**3. Modelo vigente (v3)**: `modelo_hibrido/`, pasos 1 a 7 (detalle en su README).

**4. Carga en la base:**

| Script | Qué hace |
|---|---|
| `10-CARGAR_BD.py` | Carga los archivos de la plataforma en PostgreSQL, en una sola transacción y sin duplicar si se repite |
| `esquema_wayrapredict.sql` | Esquema de la base de datos (tablas y vista de alertas) |

## 6. Cómo se ejecuta

1. **Instalar las librerías** (Python 3.12):
   ```
   pip install -r requirements.txt
   ```
2. **Abrir una terminal en esta carpeta (`3-ML/`).** Todos los scripts se ejecutan desde aquí.
3. **Correr la v3** (los datos de entrada ya están incluidos):
   ```
   python modelo_hibrido/1_dataset.py
   set WAYRA_FUENTE=combinada        (y luego pasco_moquegua)
   python modelo_hibrido/2_entrenar_componentes.py
   ...                                (pasos 3 a 6, con las dos fuentes)
   python modelo_hibrido/7_exportar_plataforma.py
   ```
4. **Cargar la base:** definir las variables de conexión (`WAYRA_DB_HOST`, `WAYRA_DB_PORT`, `WAYRA_DB_NAME`, `WAYRA_DB_USER`, `WAYRA_DB_PASSWORD`) y ejecutar:
   ```
   set WAYRA_RAIZ=modelo_hibrido/version_final
   python 10-CARGAR_BD.py
   ```
   Las contraseñas **nunca** se escriben en el código.

En Spyder se puede ejecutar cada script por celdas (`# %%`), con la carpeta de trabajo en `3-ML/`.

## 7. Proceso de predicción en la nube (Docker + Azure Container Instances)

La carpeta `proceso/` empaqueta la cadena del modelo vigente en una **imagen Docker**:

- `proceso/Dockerfile`: imagen con Python 3.12, las librerías de `requirements.txt`, el código y los datos de esta carpeta.
- `proceso/ejecutar_proceso.py`: ejecuta los pasos 1 a 7 de `modelo_hibrido/` y luego, según la variable `MODO`:
  - `verificar` (por defecto): compara los pronósticos generados con los de la base, **sin escribir nada**;
  - `cargar`: carga los resultados en la base con `10-CARGAR_BD.py`.

**Cómo se publica y ejecuta:**
1. GitHub Actions (`.github/workflows/proceso.yml`) construye la imagen y la publica en **GitHub Container Registry** (`ghcr.io/doradoss/wayrapredict-proceso`) cada vez que cambia `3-ML/`.
2. **Azure Container Instances** descarga la imagen, la ejecuta una vez (sin reinicios) y se cobra solo por los segundos de uso.
3. La conexión a la base se pasa con variables de entorno seguras (`WAYRA_DB_*`).

## 8. Herramientas

| Herramienta | Para qué |
|---|---|
| Python 3.12 (Spyder / Google Colab) | Lenguaje y entornos de trabajo |
| pandas, NumPy | Manejo de datos |
| Prophet | Tendencia y estacionalidad |
| TensorFlow / Keras | Red neuronal LSTM |
| Optuna | Búsqueda de hiperparámetros |
| SciPy, statsmodels, scikit-learn | Pruebas estadísticas y métricas |
| Matplotlib | Gráficos |
| Open-Meteo | Pronósticos meteorológicos (v2) |
| psycopg2 | Conexión con PostgreSQL |
| Docker | Imagen del proceso de predicción |

## 9. Relación con el resto de la plataforma

```
Datos OEFA ──► 3-ML (limpieza → modelo híbrido → predicciones) ──► PostgreSQL
                                                                     │
                                     API REST (Spring Boot) ◄────────┘
                                              │
                                     Aplicación web (Angular)
```

La plataforma solo lee los resultados guardados en la base; el entrenamiento se ejecuta aparte.
