import { afterNextRender, Component, computed, DestroyRef, ElementRef, inject, input, signal, viewChild } from '@angular/core';
import { claseCategoria, diferenciaDias, fechaLarga, nombreOrigen, numero } from '../../../util/formato';

export interface PuntoObservado {
  fecha: string;
  valor: number | null;
  origen?: string | null;
}

export interface PuntoPronostico {
  fecha: string;
  valor: number;
  inferior: number | null;
  superior: number | null;
}

interface XY {
  x: number;
  y: number;
}

let siguienteId = 0;

// Gráfico de la serie diaria (SVG propio): bandas INCA, observado (curva suave con área en degradado),
// predicción punteada con su intervalo, ECA de 24 h, guía OMS y la línea del día actual.
// Al cambiar los datos, la curva se vuelve a dibujar con animación; al pasar el cursor se muestra una guía con el detalle del día.
@Component({
  selector: 'app-grafico-serie',
  templateUrl: './grafico-serie.html',
  styleUrl: './grafico-serie.css',
})
export class GraficoSerie {
  observados = input<PuntoObservado[]>([]);
  pronostico = input<PuntoPronostico[]>([]);
  referencia = input.required<string>();   // fecha del "día actual"
  eca = input.required<number>();
  oms = input<number | null>(null);
  unidad = input('µg/m³');
  alto = input(300);
  // true: el gráfico ocupa todo el alto disponible de su contenedor (p. ej., para quedar parejo con la tarjeta vecina)
  llenar = input(false);

  private lienzo = viewChild<ElementRef<HTMLElement>>('lienzo');
  private altoMedido = signal<number | null>(null);
  // Alto del dibujo en unidades del viewBox (el ancho es siempre 720)
  altoEf = computed(() => {
    const m = this.altoMedido();
    return this.llenar() && m ? Math.max(220, m) : this.alto();
  });

  constructor() {
    // Con "llenar", se mide el contenedor y el viewBox se ajusta a su proporción (sin repetir la animación)
    afterNextRender(() => {
      const el = this.lienzo()?.nativeElement;
      if (!el || typeof ResizeObserver === 'undefined') return;
      const ro = new ResizeObserver(([e]) => {
        const { width, height } = e.contentRect;
        if (this.llenar() && width > 0 && height > 0) this.altoMedido.set(Math.round((height * this.ancho) / width));
      });
      ro.observe(el);
      this.destroyRef.onDestroy(() => ro.disconnect());
    });
  }
  private destroyRef = inject(DestroyRef);

  readonly id = `g${siguienteId++}`;
  readonly ancho = 720;
  readonly izq = 44;
  readonly der = 14;
  readonly arriba = 14;
  readonly abajo = 28;

  // Índice de la fecha bajo el cursor
  activo = signal<number | null>(null);

  // Fechas del eje X (observadas + pronosticadas, en orden)
  fechas = computed(() => {
    const set = new Set([...this.observados().map((p) => p.fecha), ...this.pronostico().map((p) => p.fecha)]);
    return [...set].sort();
  });

  // Clave de los datos: cuando cambia, se recrean los trazos y se repite la animación
  clave = computed(() =>
    this.referencia() + '|' + this.observados().map((p) => p.valor ?? '-').join(',') + '|' + this.pronostico().map((p) => p.valor).join(',')
  );

  // Paso redondo del eje Y (10, 20, 25, 50...) y máximo como múltiplo de ese paso
  private paso = computed(() => {
    const valores = [
      ...this.observados().map((p) => p.valor ?? 0),
      ...this.pronostico().flatMap((p) => [p.valor, p.superior ?? p.valor]),
    ];
    const max = Math.max(...valores, 0.5 * this.eca()) * 1.08;
    return { paso: this.pasoBonito(max / 4), max };
  });
  private ymax = computed(() => Math.ceil(this.paso().max / this.paso().paso) * this.paso().paso);

  base = computed(() => this.altoEf() - this.abajo);

  x(fecha: string): number {
    const f = this.fechas();
    const i = f.indexOf(fecha);
    const n = Math.max(f.length - 1, 1);
    return this.izq + (i * (this.ancho - this.izq - this.der)) / n;
  }

  y(valor: number): number {
    const v = Math.min(Math.max(valor, 0), this.ymax());
    return this.base() - (v / this.ymax()) * (this.base() - this.arriba);
  }

  // Bandas INCA: Buena (0 – ECA/2), Moderada (ECA/2 – ECA) y Mala (sobre el ECA)
  bandas = computed(() => {
    const e = this.eca();
    const lim = [0, 0.5 * e, e, this.ymax()];
    return ['buena', 'moderada', 'mala']
      .map((n, i) => ({ clase: n, y1: this.y(Math.min(lim[i + 1], this.ymax())), y0: this.y(Math.min(lim[i], this.ymax())) }))
      .filter((b) => b.y0 > b.y1)
      .map((b) => ({ clase: b.clase, y: b.y1, alto: b.y0 - b.y1 }));
  });

  marcas = computed(() => {
    const paso = this.paso().paso;
    const n = Math.round(this.ymax() / paso);
    return Array.from({ length: n + 1 }, (_, k) => ({ y: this.y(k * paso), texto: numero(k * paso) }));
  });

  ecaVisible = computed(() => this.eca() <= this.ymax());
  omsVisible = computed(() => this.oms() !== null && this.oms()! <= this.ymax());

  // Tramos observados continuos (la línea se corta donde no hay medición)
  private tramos = computed<XY[][]>(() => {
    const tramos: XY[][] = [];
    let actual: XY[] = [];
    for (const p of this.observados()) {
      if (p.valor === null) {
        if (actual.length) tramos.push(actual);
        actual = [];
        continue;
      }
      actual.push({ x: this.x(p.fecha), y: this.y(p.valor) });
    }
    if (actual.length) tramos.push(actual);
    return tramos;
  });

  trazoObservado = computed(() => this.tramos().map((t) => this.suave(t)).join(' '));
  areaObservado = computed(() =>
    this.tramos()
      .filter((t) => t.length > 1)
      .map((t) => `${this.suave(t)} L${t[t.length - 1].x.toFixed(1)},${this.base()} L${t[0].x.toFixed(1)},${this.base()} Z`)
      .join(' ')
  );

  // Punto de partida de la predicción: el último observado hasta el día actual
  private ancla = computed(() => {
    const obs = this.observados().filter((p) => p.valor !== null && p.fecha <= this.referencia());
    const a = obs.length ? obs[obs.length - 1] : null;
    return a ? { x: this.x(a.fecha), y: this.y(a.valor!) } : null;
  });

  trazoPronostico = computed(() => {
    const pts = this.pronostico().map((p) => ({ x: this.x(p.fecha), y: this.y(p.valor) }));
    if (!pts.length) return '';
    const a = this.ancla();
    return this.suave(a ? [a, ...pts] : pts);
  });

  intervalo = computed(() => {
    const pts = this.pronostico().filter((p) => p.inferior !== null && p.superior !== null);
    if (!pts.length) return '';
    const a = this.ancla();
    const sup = pts.map((p) => ({ x: this.x(p.fecha), y: this.y(p.superior!) }));
    const inf = pts.map((p) => ({ x: this.x(p.fecha), y: this.y(p.inferior!) })).reverse();
    const ida = this.suave(a ? [a, ...sup] : sup);
    const vuelta = this.suave(a ? [...inf, a] : inf).replace(/^M/, 'L');
    return `${ida} ${vuelta} Z`;
  });

  puntosObservados = computed(() =>
    this.observados().filter((p) => p.valor !== null).map((p) => ({ x: this.x(p.fecha), y: this.y(p.valor!) }))
  );
  puntosPronostico = computed(() => this.pronostico().map((p) => ({ x: this.x(p.fecha), y: this.y(p.valor) })));

  xHoy = computed(() => this.x(this.referencia()));
  hayHoy = computed(() => this.fechas().includes(this.referencia()));

  // Etiquetas del eje X relativas al día actual (−13 d … Hoy … +3 d)
  etiquetasX = computed(() => {
    const f = this.fechas();
    if (!f.length) return [];
    const ref = this.referencia();
    const saltos = Math.max(1, Math.ceil(f.length / 7));
    return f
      .filter((fecha, i) => fecha === ref || i === 0 || i === f.length - 1 || (i % saltos === 0 && Math.abs(diferenciaDias(ref, fecha)) > 1))
      .map((fecha) => {
        const d = diferenciaDias(ref, fecha);
        return { x: this.x(fecha), texto: d === 0 ? 'Hoy' : `${d > 0 ? '+' : '−'}${Math.abs(d)} d`, hoy: d === 0 };
      });
  });

  // Detalle del día bajo el cursor (guía, puntos resaltados y tooltip)
  detalle = computed(() => {
    const i = this.activo();
    const f = this.fechas();
    if (i === null || i >= f.length) return null;
    const fecha = f[i];
    const obs = this.observados().find((p) => p.fecha === fecha && p.valor !== null) ?? null;
    const pron = this.pronostico().find((p) => p.fecha === fecha) ?? null;
    const valor = obs?.valor ?? pron?.valor ?? null;
    const inca = valor !== null ? (valor / this.eca()) * 100 : null;
    const categoria = inca === null ? null : inca <= 50 ? 'Buena' : inca <= 100 ? 'Moderada' : 'Mala';
    const x = this.x(fecha);
    const d = diferenciaDias(this.referencia(), fecha);
    return {
      x,
      izqPct: (x / this.ancho) * 100,
      derecha: x > this.ancho * 0.62,
      fecha: fechaLarga(fecha),
      relativo: d === 0 ? 'Día actual' : d > 0 ? `Predicción a ${d} ${d === 1 ? 'día' : 'días'}` : `Hace ${-d} ${d === -1 ? 'día' : 'días'}`,
      obs: obs ? { y: this.y(obs.valor!), texto: numero(obs.valor, 1), origen: nombreOrigen(obs.origen) } : null,
      pron: pron
        ? {
            y: this.y(pron.valor),
            texto: numero(pron.valor, 1),
            intervalo: pron.inferior !== null ? `${numero(pron.inferior, 0)} – ${numero(pron.superior, 0)}` : null,
          }
        : null,
      inca: inca !== null ? numero(inca, 0) : null,
      categoria,
      claseCategoria: claseCategoria(categoria),
    };
  });

  mover(ev: PointerEvent): void {
    const svg = (ev.currentTarget as SVGElement).ownerSVGElement;
    const n = this.fechas().length;
    if (!svg || !n) return;
    const r = svg.getBoundingClientRect();
    const xv = ((ev.clientX - r.left) * this.ancho) / r.width;
    const paso = (this.ancho - this.izq - this.der) / Math.max(n - 1, 1);
    const i = Math.round((xv - this.izq) / paso);
    this.activo.set(Math.min(Math.max(i, 0), n - 1));
  }

  // Curva suave (Catmull-Rom convertida a Bézier), con los controles dentro del área del gráfico
  private suave(p: XY[]): string {
    if (!p.length) return '';
    const lim = (v: number) => Math.min(Math.max(v, this.arriba), this.base());
    let d = `M${p[0].x.toFixed(1)},${p[0].y.toFixed(1)}`;
    for (let i = 0; i < p.length - 1; i++) {
      const p0 = p[i - 1] ?? p[i];
      const p1 = p[i];
      const p2 = p[i + 1];
      const p3 = p[i + 2] ?? p2;
      const c1x = p1.x + (p2.x - p0.x) / 6;
      const c1y = lim(p1.y + (p2.y - p0.y) / 6);
      const c2x = p2.x - (p3.x - p1.x) / 6;
      const c2y = lim(p2.y - (p3.y - p1.y) / 6);
      d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
    }
    return d;
  }

  private pasoBonito(v: number): number {
    const exp = Math.pow(10, Math.floor(Math.log10(v)));
    const f = v / exp;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * exp;
  }
}
