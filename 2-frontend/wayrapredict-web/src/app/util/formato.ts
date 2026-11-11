// Utilidades de formato: fechas (sin desfase de zona horaria), números, categorías INCA y nombres

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'set', 'oct', 'nov', 'dic'];

// 'AAAA-MM-DD' -> Date local (evita que el navegador lo corra un día por la zona horaria)
export function aFecha(iso: string): Date {
  const [a, m, d] = iso.substring(0, 10).split('-').map(Number);
  return new Date(a, m - 1, d);
}

export function aIso(f: Date): string {
  const m = String(f.getMonth() + 1).padStart(2, '0');
  const d = String(f.getDate()).padStart(2, '0');
  return `${f.getFullYear()}-${m}-${d}`;
}

export function sumarDias(iso: string, dias: number): string {
  const f = aFecha(iso);
  f.setDate(f.getDate() + dias);
  return aIso(f);
}

export function diferenciaDias(desde: string, hasta: string): number {
  return Math.round((aFecha(hasta).getTime() - aFecha(desde).getTime()) / 86400000);
}

// 26 jun 2026
export function fechaLarga(iso: string | null | undefined): string {
  if (!iso) return '—';
  const f = aFecha(iso);
  return `${f.getDate()} ${MESES[f.getMonth()]} ${f.getFullYear()}`;
}

// 26/06
export function fechaCorta(iso: string): string {
  const f = aFecha(iso);
  return `${String(f.getDate()).padStart(2, '0')}/${String(f.getMonth() + 1).padStart(2, '0')}`;
}

// 02/11/2026 17:13 (fecha y hora del servidor, sin zona)
export function fechaHora(iso: string | null | undefined): string {
  if (!iso) return '—';
  const [fecha, hora = ''] = iso.split('T');
  const [a, m, d] = fecha.split('-');
  return `${d}/${m}/${a}${hora ? ' ' + hora.substring(0, 5) : ''}`;
}

// Días respecto del "día actual" de la estación: Mañana, En 2 días, Hoy, Hace 3 días
export function relativo(dias: number): string {
  if (dias === 0) return 'Hoy';
  if (dias === 1) return 'Mañana';
  if (dias > 1) return `En ${dias} días`;
  return dias === -1 ? 'Hace 1 día' : `Hace ${-dias} días`;
}

// Número con coma decimal
export function numero(v: number | null | undefined, decimales = 0): string {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return v.toLocaleString('es-PE', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

// Clase CSS de una categoría INCA (tag--buena, b-mala, p-moderada, ...)
export function claseCategoria(nombre: string | null | undefined): string {
  switch ((nombre ?? '').toLowerCase()) {
    case 'buena': return 'buena';
    case 'moderada': return 'moderada';
    case 'mala': return 'mala';
    case 'umbral de cuidado': return 'cuidado';
    default: return 'sin-dato';
  }
}

// Gravedad para ordenar categorías
export function gravedad(nombre: string | null | undefined): number {
  return ['buena', 'moderada', 'mala', 'cuidado'].indexOf(claseCategoria(nombre));
}

// SO2 -> SO₂
export function nombreContaminante(codigo: string | null | undefined): string {
  if (codigo === 'SO2') return 'SO₂';
  if (codigo === 'PM2.5') return 'PM2.5';
  return codigo ?? '';
}

// ug/m3 -> µg/m³
export function unidad(u: string | null | undefined): string {
  return (u ?? 'µg/m³').replace('ug/m3', 'µg/m³');
}

export function nombreRol(rol: string | null | undefined): string {
  return rol === 'administrador' ? 'Administrador' : rol === 'usuario_institucional' ? 'Usuario institucional' : '';
}

// Origen de una medición, en palabras
export function nombreOrigen(origen: string | null | undefined): string {
  switch (origen) {
    case 'estacion': return 'medido por la estación';
    case 'estacion_vecina': return 'estimado con una estación vecina';
    case 'servicio_meteo': return 'reanálisis meteorológico';
    case 'pronostico_meteo': return 'pronóstico meteorológico';
    default: return '';
  }
}

// Mensaje de error del backend ({fecha, estado, error, mensaje}) o uno genérico
export function mensajeError(err: any, porDefecto = 'Ocurrió un error. Inténtalo de nuevo.'): string {
  if (err?.status === 0) return 'No se pudo conectar con el servidor. Verifica que el backend esté en marcha.';
  return err?.error?.mensaje ?? porDefecto;
}
