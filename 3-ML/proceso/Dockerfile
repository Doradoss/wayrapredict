# Imagen del proceso de predicción de WayraPredict (se construye desde la carpeta 3-ML).
# GitHub Actions la publica en GitHub Container Registry: ghcr.io/doradoss/wayrapredict-proceso
FROM python:3.12-slim

# libgomp1: la necesitan LightGBM y TensorFlow para el cálculo en paralelo
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código, datasets diarios y modelos de entrada del repositorio
COPY . .

ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg TZ=America/Lima TF_CPP_MIN_LOG_LEVEL=2 MODO=verificar
CMD ["python", "-u", "proceso/ejecutar_proceso.py"]
