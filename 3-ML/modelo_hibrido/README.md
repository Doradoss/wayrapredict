# Modelo híbrido Prophet-LSTM

Código del **modelo híbrido Prophet-LSTM** que usa la plataforma WayraPredict para pronosticar el promedio diario del contaminante de cada estación (SO₂ en La Oroya; PM10 en Huaraucaca e Ilo) a 1, 2 y 3 días.

- **Prophet** aprende la tendencia y los ciclos (semana y año).
- La **red LSTM** (Keras/TensorFlow) aprende de los días anteriores y corrige lo que Prophet no explica.
- El pronóstico final combina ambos y trae un **intervalo de incertidumbre**, que se usa para las alertas.

## Orden de ejecución

| Paso | Script | Qué hace |
|---|---|---|
| 1 | `1_dataset.py` | Arma el dataset diario de las tres estaciones |
| 2 | `2_entrenar_componentes.py` | Entrena la LSTM de cada estación |
| 3 | `3_combinar_prophet_lstm.py` | Combina Prophet y la LSTM (peso elegido con la validación) |
| 4 | `4_serie_completa.py` | Completa la serie de pronósticos de todo el periodo |
| 5 | `5_pronostico_futuro.py` | Pronostica los próximos 1 a 3 días |
| 6 | `6_guardar_modelos.py` | Guarda los modelos entrenados (`.keras`, Prophet y configuración) |
| 7 | `7_exportar_plataforma.py` | Genera los archivos que se cargan en la base con `../10-CARGAR_BD.py` |

`v3_entradas.py` reúne las variables de entrada que usan los pasos.

Se ejecutan desde la carpeta `3-ML/` (por ejemplo, `python modelo_hibrido/1_dataset.py`), después de los scripts de preparación y del modelo base de esa carpeta. Los datos y los modelos entrenados no se incluyen por su tamaño.
