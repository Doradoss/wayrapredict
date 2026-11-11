// Métricas del modelo (prueba a 1 día)
export interface MetricaModelo {
  estacion: string;
  estacionNombre: string;
  contaminante: string;
  idModelo: number;
  version: string;
  vigente: boolean;
  fechaEntrenamiento: string;
  rmse: number;
  mae: number;
  r2: number;
  unidad: string;
}
