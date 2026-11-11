// GET /api/libre/estaciones: estación con su contaminante, fecha de referencia ("día actual") y último valor medido
export interface Estacion {
  idEstacion: number;
  codigo: string;
  nombre: string;
  departamento: string;
  provincia: string | null;
  distrito: string | null;
  este: number | null;
  norte: number | null;
  zonaUtm: number | null;
  altitud: number | null;
  activa: boolean;
  contaminante: string;          // SO2 | PM10
  contaminanteNombre: string;
  unidad: string;
  eca24h: number;
  oms24h: number | null;
  fechaReferencia: string;       // AAAA-MM-DD
  ultimoValor: number | null;
  ultimoValorInca: number | null;
  categoriaUltimoValor: string | null;
  colorUltimoValor: string | null;
  ultimaActualizacionPredicciones: string | null;
}
