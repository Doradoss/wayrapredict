// GET /api/libre/serie-diaria/{codigo}: un día con el contaminante, la meteorología y el origen de cada valor
export interface SerieDiaria {
  fecha: string;
  posteriorAReferencia: boolean;
  contaminante: number | null;
  origenContaminante: string | null;
  temperatura: number | null;
  origenTemperatura: string | null;
  humedadRelativa: number | null;
  origenHumedadRelativa: string | null;
  velocidadViento: number | null;
  origenVelocidadViento: string | null;
  direccionViento: number | null;
  origenDireccionViento: string | null;
  presionBarometrica: number | null;
  origenPresionBarometrica: string | null;
  precipitacion: number | null;
  origenPrecipitacion: string | null;
}
