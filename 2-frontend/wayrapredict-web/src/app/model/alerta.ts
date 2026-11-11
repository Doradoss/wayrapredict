// GET /api/libre/alertas: predicción de categoría Moderada o superior (vista v_alerta)
export interface Alerta {
  idPrediccion: number;
  estacion: string;
  estacionNombre: string;
  departamento: string;
  contaminante: string;
  fechaObjetivo: string;
  fechaReferencia: string;
  diasDesdeReferencia: number;
  valor: number;
  valorInca: number;
  categoriaInca: string;
  colorHex: string;
  superaEca: boolean;
  estado: string;            // vigente | finalizada
}
