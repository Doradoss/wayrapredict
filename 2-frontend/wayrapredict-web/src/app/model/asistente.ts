// POST /api/libre/asistente
export interface MensajeAsistente {
  rol: 'usuario' | 'asistente';
  texto: string;
}

export interface PreguntaAsistente {
  pregunta: string;
  estacion?: string | null;      // código de la estación que el usuario está viendo
  historial: MensajeAsistente[];  // memoria: intervenciones anteriores de esta conversación
}

export interface RespuestaAsistente {
  respuesta: string;
  fechaDatos: string | null;      // día actual más reciente de las estaciones (AAAA-MM-DD)
  modelo: string;                 // modelo de Gemini que respondió
}
