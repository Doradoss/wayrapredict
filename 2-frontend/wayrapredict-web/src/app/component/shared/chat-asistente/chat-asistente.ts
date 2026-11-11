import { Component, computed, ElementRef, HostListener, inject, signal, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';
import { filter, map } from 'rxjs';
import { MensajeAsistente } from '../../../model/asistente';
import { AsistenteService, ErrorAsistente } from '../../../service/asistente.service';
import { EstacionService } from '../../../service/estacion.service';
import { mensajeError } from '../../../util/formato';

interface Burbuja {
  rol: 'usuario' | 'asistente';
  texto: string;
  html?: string;
  error?: boolean;
  pregunta?: string;     // en un error: la pregunta, para reintentar
  enCurso?: boolean;     // la respuesta todavía está llegando
}

// Asistente conversacional (pantalla 7): botón flotante y panel de chat. Envía la pregunta al backend, que la
// responde con Gemini usando los datos reales de la plataforma; la respuesta se muestra por partes mientras se escribe. La memoria de la conversación vive solo aquí
// (se envían las intervenciones anteriores en cada pregunta) y no se guarda en ningún lado.
@Component({
  selector: 'app-chat-asistente',
  template: `
    @if (!abierto()) {
      <button type="button" class="fab" (click)="abrir()" aria-label="Abrir asistente conversacional">
        <span class="fab__simbolo"><img src="simbolo-oscuro.svg" alt="" aria-hidden="true"></span><span>¿Dudas? Pregúntale al asistente</span>
      </button>
    } @else {
      <div class="chat" role="dialog" aria-label="Asistente de calidad del aire">
        <div class="chat__cab">
          <img class="logo logo--claro simbolo" src="simbolo-claro.svg" alt="" aria-hidden="true"><img class="logo logo--oscuro simbolo" src="simbolo-oscuro.svg" alt="" aria-hidden="true">
          <div class="chat__titulo"><b>Asistente de calidad del aire</b>
            <small>@if (estacionNombre(); as n) { Contexto: {{ n }} } @else { Respuestas en lenguaje sencillo }</small></div>
          @if (mensajes().length) {
            <button type="button" class="icon-btn" (click)="nueva()" aria-label="Nueva conversación" title="Nueva conversación">
              <svg class="ico" aria-hidden="true"><use href="#i-chat"/></svg>
            </button>
          }
          <button type="button" class="icon-btn" (click)="abierto.set(false)" aria-label="Cerrar asistente" title="Cerrar">
            <svg class="ico" aria-hidden="true"><use href="#i-close"/></svg>
          </button>
        </div>

        <div class="chat__mensajes" #lista aria-live="polite">
          <div class="msg">Hola, soy el asistente de WayraPredict. Pregúntame cómo estará la calidad del aire en tu zona, qué significan los indicadores o qué precauciones tomar.</div>
          @for (m of mensajes(); track $index) {
            @if (m.rol === 'usuario') {
              <div class="msg msg--yo">{{ m.texto }}</div>
            } @else if (m.error) {
              <div class="msg msg--error">{{ m.texto }}
                @if (m.pregunta) { <button type="button" class="btn btn--sm" (click)="reintentar(m)">Reintentar</button> }
              </div>
            } @else {
              <div class="msg" [class.msg--en-curso]="m.enCurso" [innerHTML]="m.html"></div>
            }
          }
          @if (esperandoTexto()) {
            <div class="msg msg--escribiendo" aria-label="El asistente está escribiendo"><i></i><i></i><i></i></div>
          }
        </div>

        <div class="chat__pie">
          @if (!mensajes().length) {
            <div class="chat__chips">
              @for (s of sugerencias; track s) {
                <button type="button" class="btn btn--sm" (click)="enviar(s)" [disabled]="enviando()">{{ s }}</button>
              }
            </div>
          }
          <form class="chat__form" (submit)="$event.preventDefault(); enviar(texto())">
            <label class="chat__campo"><span class="sr-only">Escribe tu pregunta</span>
              <textarea class="input" rows="1" maxlength="500" placeholder="Escribe tu pregunta…" [value]="texto()"
                        (input)="texto.set($any($event.target).value)" (keydown.enter)="alPresionarEnter($event)" #campo></textarea>
            </label>
            <button type="submit" class="btn primary" aria-label="Enviar pregunta" [disabled]="enviando() || !texto().trim()">
              <svg class="ico" aria-hidden="true"><use href="#i-send"/></svg>
            </button>
          </form>
          <small class="chat__aviso">Respuestas generadas con IA (Gemini) a partir de los datos de la plataforma; pueden contener errores. No escribas datos personales.</small>
        </div>
      </div>
    }
  `,
  styles: [`
    .fab { position: fixed; right: 24px; bottom: 24px; z-index: 30; display: flex; align-items: center; gap: 10px; height: 46px; padding: 0 18px;
      background: var(--brand); color: #fff; border-radius: var(--radius-full); box-shadow: var(--shadow-lg); font-weight: 700; font-size: 13px;
      animation: toast .3s ease both; transition: background-color .15s, transform .15s; }
    .fab:hover { background: var(--brand-strong); transform: translateY(-2px); }
    .chat { position: fixed; right: 24px; bottom: 24px; z-index: 30; width: 400px; height: 600px; max-width: calc(100vw - 32px);
      max-height: calc(100vh - 48px); max-height: calc(100dvh - 48px); background: var(--bg-raised);
      border: 1px solid var(--border-medium); border-radius: 8px; box-shadow: var(--shadow-lg); display: flex; flex-direction: column; overflow: hidden;
      animation: toast .25s ease both; }
    .chat__cab { display: flex; align-items: center; gap: 10px; padding: 14px; border-bottom: 1px solid var(--border); }
    .chat__cab .simbolo { width: 34px; height: 34px; }
    .fab__simbolo { width: 30px; height: 30px; margin-left: -8px; border-radius: 50%; background: #0c1d22; display: grid; place-items: center; }
    .fab__simbolo img { width: 22px; height: 22px; }
    .chat__titulo { flex: 1; min-width: 0; }
    .chat__titulo b { display: block; color: var(--heading); font-size: 13px; }
    .chat__titulo small { color: var(--body-subtle); font-size: 11px; }
    .chat__cab, .chat__pie { flex: none; }
    .chat__mensajes { padding: 14px; display: flex; flex-direction: column; gap: 10px; background: var(--bg-surface); min-height: 0; flex: 1 1 160px; overflow-y: auto; overscroll-behavior: contain; }
    .msg { align-self: flex-start; max-width: 88%; background: var(--bg-raised); border: 1px solid var(--border); border-radius: 8px 8px 8px 2px;
      padding: 10px 12px; font-size: 13px; color: var(--heading); line-height: 1.55; animation: aparecer .3s ease both; overflow-wrap: anywhere; }
    .msg ::ng-deep ul { margin: 4px 0 4px 20px; padding: 0; }
    .msg ::ng-deep li + li { margin-top: 3px; }
    .msg ::ng-deep p + p, .msg ::ng-deep ul + p, .msg ::ng-deep p + ul { margin-top: 6px; }
    .msg--yo { align-self: flex-end; background: var(--brand); border-color: var(--brand); color: #fff; border-radius: 8px 8px 2px 8px; white-space: pre-wrap; }
    .msg--error { background: var(--inca-cuidado-soft); border-color: var(--inca-cuidado-border); color: var(--inca-cuidado-text); display: flex; flex-direction: column; gap: 8px; }
    .msg--error .btn { align-self: flex-start; }
    .msg--escribiendo { display: flex; gap: 4px; padding: 12px 14px; }
    .msg--escribiendo i { width: 7px; height: 7px; border-radius: 50%; background: var(--body-subtle); animation: rebote 1s infinite ease-in-out; }
    .msg--escribiendo i:nth-child(2) { animation-delay: .15s; } .msg--escribiendo i:nth-child(3) { animation-delay: .3s; }
    .msg--en-curso ::ng-deep > p:last-child::after, .msg--en-curso ::ng-deep > ul:last-child > li:last-child::after {
      content: ''; display: inline-block; width: 7px; height: 14px; margin-left: 3px; vertical-align: -2px;
      background: var(--fg-brand); border-radius: 1px; animation: parpadeo .9s steps(2) infinite; }
    @keyframes parpadeo { 50% { opacity: 0; } }
    @keyframes rebote { 0%, 80%, 100% { transform: translateY(0); opacity: .4; } 40% { transform: translateY(-5px); opacity: 1; } }
    .chat__pie { padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; border-top: 1px solid var(--border); }
    .chat__chips { display: flex; gap: 6px; flex-wrap: wrap; }
    .chat__form { display: flex; gap: 8px; align-items: flex-end; }
    .chat__campo { flex: 1; }
    .chat__form textarea { height: auto; min-height: 38px; max-height: 110px; padding: 9px 12px; resize: none; line-height: 1.4; font-size: 13px; field-sizing: content; }
    .chat__form .btn { height: 38px; }
    .chat__aviso { font-size: 10.5px; color: var(--body-subtle); line-height: 1.4; }
    @media (max-width: 760px), (max-height: 560px) { .chat { right: 8px; left: 8px; bottom: 8px; top: 8px; width: auto; height: auto; max-width: none; max-height: none; } }
    @media (max-width: 760px) { .fab > span:not(.fab__simbolo) { display: none; } .fab { width: 52px; height: 52px; padding: 0; justify-content: center; right: 16px; bottom: 16px; } .fab__simbolo { margin: 0; width: 36px; height: 36px; } .fab__simbolo img { width: 26px; height: 26px; } }
  `],
})
export class ChatAsistente {
  private asistente = inject(AsistenteService);
  private estacionService = inject(EstacionService);
  private router = inject(Router);
  private lista = viewChild<ElementRef<HTMLElement>>('lista');
  private campo = viewChild<ElementRef<HTMLTextAreaElement>>('campo');

  readonly sugerencias = ['¿Qué es el INCA?', '¿Cómo estará el aire mañana?', '¿Hay alertas vigentes?', '¿Qué precauciones tomo?'];
  abierto = signal(false);
  mensajes = signal<Burbuja[]>([]);
  texto = signal('');
  enviando = signal(false);
  esperandoTexto = signal(false);      // enviada, sin texto todavía: se muestran los puntos "escribiendo"
  private controlador: AbortController | null = null;

  // Nombres de las estaciones (para mostrar el contexto)
  private estaciones = toSignal(this.estacionService.getEstaciones(), { initialValue: [] });
  private url = toSignal(this.router.events.pipe(filter((e) => e instanceof NavigationEnd), map(() => this.router.url)),
    { initialValue: this.router.url });

  // Estación en pantalla solo en Inicio y en el detalle de estación
  estacionActual = computed(() =>
    this.url().startsWith('/dashboard') || this.url().startsWith('/estacion') ? this.asistente.estacionEnPantalla() : null);
  estacionNombre = computed(() => this.estaciones().find((e) => e.codigo === this.estacionActual())?.nombre ?? null);

  abrir(): void {
    this.abierto.set(true);
    setTimeout(() => this.campo()?.nativeElement.focus(), 50);
  }

  nueva(): void {
    this.controlador?.abort();
    this.mensajes.set([]);
    this.texto.set('');
  }

  alPresionarEnter(ev: Event): void {
    const k = ev as KeyboardEvent;
    if (!k.shiftKey) {
      k.preventDefault();
      this.enviar(this.texto());
    }
  }

  reintentar(m: Burbuja): void {
    this.mensajes.update((l) => l.filter((x) => x !== m));
    // quita también la pregunta que falló (se vuelve a agregar al enviar)
    this.mensajes.update((l) => (l.length && l[l.length - 1].rol === 'usuario' && l[l.length - 1].texto === m.pregunta ? l.slice(0, -1) : l));
    this.enviar(m.pregunta ?? '');
  }

  enviar(textoPregunta: string): void {
    const pregunta = textoPregunta.trim();
    if (!pregunta || this.enviando()) return;
    // Memoria: intervenciones anteriores sin errores (el backend usa las últimas 6)
    const historial: MensajeAsistente[] = this.mensajes().filter((m) => !m.error).map((m) => ({ rol: m.rol, texto: m.texto }));
    this.mensajes.update((l) => [...l, { rol: 'usuario', texto: pregunta }]);
    this.texto.set('');
    this.enviando.set(true);
    this.esperandoTexto.set(true);
    this.bajar();
    // La respuesta llega por partes: la burbuja aparece con el primer fragmento y crece mientras Gemini escribe
    const burbuja: Burbuja = { rol: 'asistente', texto: '', html: '', enCurso: true };
    this.controlador = new AbortController();
    this.asistente
      .preguntarEnVivo({ pregunta, estacion: this.estacionActual(), historial }, (fragmento) => {
        burbuja.texto += fragmento;
        burbuja.html = aHtml(burbuja.texto);
        if (this.esperandoTexto()) {
          this.esperandoTexto.set(false);
          this.mensajes.update((l) => [...l, burbuja]);
        } else {
          this.mensajes.update((l) => [...l]);   // nueva referencia: se vuelve a dibujar la burbuja
        }
        this.bajar(false);
      }, this.controlador.signal)
      .then(() => {
        burbuja.enCurso = false;
        this.mensajes.update((l) => [...l]);
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return;
        burbuja.enCurso = false;
        const texto = err instanceof ErrorAsistente ? err.message : mensajeError(err, 'No pude responder en este momento. Inténtalo de nuevo.');
        // Si ya llegó parte de la respuesta, se conserva y se avisa debajo
        this.mensajes.update((l) => [...l, { rol: 'asistente', error: true, pregunta: burbuja.texto ? undefined : pregunta, texto }]);
      })
      .finally(() => {
        this.enviando.set(false);
        this.esperandoTexto.set(false);
        this.controlador = null;
        this.bajar();
      });
  }

  private bajar(suave = true): void {
    setTimeout(() => {
      const el = this.lista()?.nativeElement;
      if (el) el.scrollTo({ top: el.scrollHeight, behavior: suave ? 'smooth' : 'auto' });
    }, 30);
  }

  // Escape cierra el panel
  @HostListener('document:keydown.escape')
  cerrar(): void {
    this.abierto.set(false);
  }
}

// Formato mínimo y seguro de la respuesta: se escapa el HTML y luego se convierten **negritas**, listas y párrafos
function aHtml(texto: string): string {
  const escapar = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const enLinea = (s: string) => escapar(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<i>$2</i>');
  const bloques: string[] = [];
  let lista: string[] = [];
  const cerrarLista = () => {
    if (lista.length) bloques.push('<ul>' + lista.map((li) => `<li>${li}</li>`).join('') + '</ul>');
    lista = [];
  };
  for (const linea of texto.split(/\r?\n/)) {
    const l = linea.trim();
    const item = l.match(/^(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (item) {
      lista.push(enLinea(item[1]));
    } else {
      cerrarLista();
      if (l) bloques.push(`<p>${enLinea(l)}</p>`);
    }
  }
  cerrarLista();
  return bloques.join('');
}
