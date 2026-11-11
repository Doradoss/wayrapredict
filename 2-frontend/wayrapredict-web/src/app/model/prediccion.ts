// Predicción (próximos días, historial o pendientes de verificar)
export interface Prediccion {
  idPrediccion: number;
  estacion: string;
  contaminante: string;
  fechaObjetivo: string;
  fechaReferencia: string;
  diasDesdeReferencia: number;
  valor: number;
  limiteInferior: number | null;
  limiteSuperior: number | null;
  valorInca: number;
  superaEca: boolean;
  categoriaInca: string;
  colorHex: string;
  recomendacion: string;
  versionModelo: string;
  modeloVigente: boolean;
  idEjecucion: number;
  verificado: boolean;
  verificadoPor: string | null;
  fechaVerificacion: string | null;
  observado: number | null;            // solo en el historial
  origenObservado: string | null;
  categoriaObservada: string | null;
  colorObservado: string | null;
}
