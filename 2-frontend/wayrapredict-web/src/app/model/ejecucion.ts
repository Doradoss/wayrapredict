// GET /api/admin/ejecuciones
export interface Ejecucion {
  idEjecucion: number;
  fechaInicio: string;
  fechaFin: string | null;
  estado: string;
  mensajeError: string | null;
  predicciones: number;
  mediciones: number;
}
