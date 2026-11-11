import { Component, computed, input, signal } from '@angular/core';
import { claseCategoria, numero } from '../../../util/formato';

export interface BarraDia {
  etiqueta: string;          // "Hoy", "Mañana", "+2 d"
  valor: number | null;
  categoria: string | null;
  observado: boolean;        // true: medición del día actual; false: predicción
  detalle?: string;          // texto del tooltip
}

// Barras verticales animadas (crecen al aparecer y al cambiar de estación). Color según la categoría INCA;
// al pasar el cursor, las demás barras se atenúan. La línea punteada marca el ECA-Aire de 24 h.
@Component({
  selector: 'app-barras-dias',
  template: `
    @for (k of [clave()]; track k) {
      <div class="barras" [class.barras--foco]="foco() !== null" [style.height.px]="alto()">
        @if (ecaFrac() <= 1) {
          <div class="barras__eca" [style.bottom]="'calc(22px + ' + ecaFrac() + ' * (100% - 48px))'"><span>ECA {{ eca() }}</span></div>
        }
        @for (b of barras(); track $index) {
          <div class="barras__col" [class.activa]="foco() === $index" (pointerenter)="foco.set($index)" (pointerleave)="foco.set(null)"
               [title]="b.detalle ?? ''">
            <div class="barras__pista">
              <span class="barras__valor" [style.bottom]="'calc((100% - 22px) * ' + frac(b.valor) + ' + 4px)'"
                    [style.animation-delay.ms]="500 + $index * 110">{{ num(b.valor, 0) }}</span>
              <i [class]="'barras__barra b-' + cat(b.categoria)" [class.barras__barra--obs]="b.observado"
                 [style.height]="'calc((100% - 22px) * ' + frac(b.valor) + ')'" [style.animation-delay.ms]="120 + $index * 110"></i>
            </div>
            <span class="barras__etq">{{ b.etiqueta }}</span>
          </div>
        }
      </div>
    }
  `,
  styles: [`
    .barras { position: relative; display: flex; align-items: stretch; gap: 14px; margin-top: 16px; padding-top: 4px; }
    .barras__col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 0; transition: opacity .2s; cursor: default; }
    .barras--foco .barras__col:not(.activa) { opacity: .4; }
    .barras__valor { position: absolute; left: 0; right: 0; text-align: center; line-height: 18px; font-size: 13px; font-weight: 900; color: var(--heading);
      animation: aparecer .4s ease both; }
    .barras__pista { position: relative; flex: 1; width: 100%; display: flex; align-items: flex-end; border-bottom: 1px solid var(--border-medium); }
    .barras__barra { display: block; width: 100%; border-radius: 3px 3px 0 0; transform-origin: bottom;
      animation: subir .7s cubic-bezier(.2, .9, .3, 1.15) both; min-height: 3px; }
    .barras__barra--obs { opacity: .55; background-image: repeating-linear-gradient(135deg, transparent 0 5px, #ffffff40 5px 8px); }
    .barras__etq { line-height: 16px; font-size: 11px; color: var(--body-subtle); white-space: nowrap; }
    .barras__eca { position: absolute; left: 0; right: 0; border-top: 1.5px dashed var(--inca-cuidado); pointer-events: none; z-index: 1; }
    .barras__eca span { position: absolute; right: 0; top: -16px; font-size: 10px; font-weight: 700; color: var(--inca-cuidado-text); }
    @keyframes subir { from { transform: scaleY(0); } to { transform: scaleY(1); } }
  `],
})
export class BarrasDias {
  barras = input<BarraDia[]>([]);
  eca = input.required<number>();
  alto = input(170);
  foco = signal<number | null>(null);
  cat = claseCategoria;
  num = numero;

  clave = computed(() => this.barras().map((b) => `${b.etiqueta}:${b.valor}`).join('|'));
  // Escala: el mayor entre los valores y la mitad del ECA, con margen
  private maximo = computed(() => Math.max(...this.barras().map((b) => b.valor ?? 0), 0.5 * this.eca()) * 1.15);
  // Altura del ECA como fracción de la pista de las barras
  ecaFrac = computed(() => this.eca() / this.maximo());

  // Alto relativo de la barra (0–1)
  frac(v: number | null): number {
    return v === null ? 0 : Math.min(1, v / this.maximo());
  }
}
