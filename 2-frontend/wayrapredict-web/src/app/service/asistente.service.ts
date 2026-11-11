import { HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { PreguntaAsistente, RespuestaAsistente } from '../model/asistente';

// Fin de una respuesta por partes
export interface FinRespuesta {
  modelo: string;
  fechaDatos: string | null;
}

// Error del asistente con el mensaje para el usuario (el del backend cuando lo hay)
export class ErrorAsistente extends Error {
  constructor(mensaje: string, readonly estado = 0) {
    super(mensaje);
  }
}

// Asistente conversacional (Gemini, a través del backend). La clave de la API nunca llega al navegador.
@Injectable({ providedIn: 'root' })
export class AsistenteService {
  private apiURL = `${environment.apiUrl}/api/libre/asistente`;

  // Estación que el usuario está viendo (la fijan el dashboard y el detalle de estación): da contexto a preguntas
  // como "¿cómo estará mañana?"
  readonly estacionEnPantalla = signal<string | null>(null);

  constructor(private http: HttpClient) {}

  // Respuesta completa de una vez (se conserva para usos simples y pruebas)
  preguntar(pregunta: PreguntaAsistente): Observable<RespuestaAsistente> {
    return this.http.post<RespuestaAsistente>(this.apiURL, pregunta);
  }

  // Respuesta por partes (Server-Sent Events): llama a alTexto con cada fragmento apenas llega.
  // Se usa fetch porque EventSource solo admite GET. El servicio es público: no lleva token.
  async preguntarEnVivo(pregunta: PreguntaAsistente, alTexto: (fragmento: string) => void, cancelar?: AbortSignal): Promise<FinRespuesta> {
    let respuesta: Response;
    try {
      respuesta = await fetch(`${this.apiURL}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify(pregunta),
        signal: cancelar,
      });
    } catch {
      throw new ErrorAsistente('No se pudo conectar con el servidor. Verifica que el backend esté en marcha.');
    }
    if (!respuesta.ok || !respuesta.body) {
      // 400/404/429/503: el backend responde JSON {mensaje}
      const cuerpo = await respuesta.json().catch(() => null);
      throw new ErrorAsistente(cuerpo?.mensaje ?? 'No pude responder en este momento. Inténtalo de nuevo.', respuesta.status);
    }

    const lector = respuesta.body.getReader();
    const decodificador = new TextDecoder();
    let pendiente = '';
    let fin: FinRespuesta | null = null;
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      pendiente += decodificador.decode(value, { stream: true });
      // Cada evento termina con una línea en blanco
      let corte: number;
      while ((corte = pendiente.search(/\r?\n\r?\n/)) >= 0) {
        const bloque = pendiente.slice(0, corte);
        pendiente = pendiente.slice(corte).replace(/^\r?\n\r?\n/, '');
        let evento = 'message';
        const datos: string[] = [];
        for (const linea of bloque.split(/\r?\n/)) {
          if (linea.startsWith('event:')) evento = linea.slice(6).trim();
          else if (linea.startsWith('data:')) datos.push(linea.slice(5).replace(/^ /, ''));
        }
        if (!datos.length) continue;
        const json = JSON.parse(datos.join('\n'));
        if (evento === 'texto') alTexto(json.t);
        else if (evento === 'fin') fin = json as FinRespuesta;
        else if (evento === 'error') throw new ErrorAsistente(json.mensaje ?? 'No pude responder en este momento.');
      }
    }
    if (!fin) throw new ErrorAsistente('La respuesta se interrumpió. Inténtalo de nuevo.');
    return fin;
  }
}
