import { Component, computed, ElementRef, HostListener, inject, input, output, signal } from '@angular/core';

export interface OpcionDesplegable {
  valor: string;
  texto: string;
}

let siguienteId = 0;

// Selector con lista desplegable animada (se desliza y aparece). Accesible con teclado:
// Enter/Espacio o flechas abren; flechas recorren; Enter elige; Escape cierra.
@Component({
  selector: 'app-desplegable',
  template: `
    <span class="etq" [id]="id + '-etq'">{{ etiqueta() }}</span>
    <button type="button" class="disparador" [class.abierto]="abierto()" (click)="alternar()" (keydown)="teclado($event)"
            aria-haspopup="listbox" [attr.aria-expanded]="abierto()" [attr.aria-labelledby]="id + '-etq ' + id + '-val'">
      <span [id]="id + '-val'">{{ textoActual() }}</span>
      <svg class="ico flecha" aria-hidden="true"><use href="#i-chevron"/></svg>
    </button>
    @if (abierto()) {
      <ul class="menu" role="listbox" [attr.aria-labelledby]="id + '-etq'">
        @for (o of opciones(); track o.valor; let i = $index) {
          <li role="option" [attr.aria-selected]="o.valor === valor()" [class.sel]="o.valor === valor()" [class.foco]="i === foco()"
              [style.animation-delay.ms]="i * 35" (click)="elegir(o.valor)" (pointerenter)="foco.set(i)">
            <span>{{ o.texto }}</span>
            @if (o.valor === valor()) { <svg class="ico" aria-hidden="true"><use href="#i-check"/></svg> }
          </li>
        }
      </ul>
    }
  `,
  styles: [`
    :host { position: relative; display: inline-flex; flex-direction: column; gap: 4px; min-width: 160px; }
    .etq { font-size: 11px; color: var(--body-subtle); font-weight: 700; }
    .disparador { display: flex; align-items: center; justify-content: space-between; gap: 10px; height: 32px; padding: 0 10px 0 12px;
      font-size: 12px; font-weight: 700; color: var(--heading); background: var(--bg-surface); border: 1px solid var(--border-medium);
      border-radius: var(--radius); transition: background-color .15s, border-color .15s; }
    .disparador:hover { background: var(--bg-elevated); }
    .disparador.abierto { border-color: var(--brand); background: var(--bg-raised); }
    .flecha { transition: transform .25s cubic-bezier(.3, 1.4, .6, 1); color: var(--body); }
    .abierto .flecha { transform: rotate(180deg); }
    .menu { position: absolute; top: calc(100% + 6px); left: 0; right: 0; z-index: 20; list-style: none; padding: 4px;
      background: var(--bg-raised); border: 1px solid var(--border-medium); border-radius: var(--radius); box-shadow: var(--shadow-lg);
      transform-origin: top; animation: desplegar .22s cubic-bezier(.2, .9, .3, 1.1) both; }
    .menu li { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 10px; font-size: 12px;
      border-radius: var(--radius); cursor: pointer; color: var(--body); animation: entrar .25s ease both; }
    .menu li.foco { background: var(--bg-surface); color: var(--heading); }
    .menu li.sel { color: var(--fg-brand); font-weight: 700; }
    @keyframes desplegar { from { opacity: 0; transform: translateY(-6px) scaleY(.85); } to { opacity: 1; transform: none; } }
    @keyframes entrar { from { opacity: 0; transform: translateX(-6px); } to { opacity: 1; transform: none; } }
  `],
})
export class Desplegable {
  etiqueta = input('');
  opciones = input<OpcionDesplegable[]>([]);
  valor = input('');
  cambio = output<string>();

  readonly id = `d${siguienteId++}`;
  abierto = signal(false);
  foco = signal(0);
  private host = inject(ElementRef<HTMLElement>);

  textoActual = computed(() => this.opciones().find((o) => o.valor === this.valor())?.texto ?? '');

  alternar(): void {
    if (this.abierto()) {
      this.abierto.set(false);
      return;
    }
    this.foco.set(Math.max(0, this.opciones().findIndex((o) => o.valor === this.valor())));
    this.abierto.set(true);
  }

  elegir(v: string): void {
    this.abierto.set(false);
    if (v !== this.valor()) this.cambio.emit(v);
  }

  teclado(ev: KeyboardEvent): void {
    const n = this.opciones().length;
    if (ev.key === 'Escape') {
      this.abierto.set(false);
    } else if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      ev.preventDefault();
      if (!this.abierto()) {
        this.alternar();
        return;
      }
      this.foco.set((this.foco() + (ev.key === 'ArrowDown' ? 1 : n - 1)) % n);
    } else if ((ev.key === 'Enter' || ev.key === ' ') && this.abierto()) {
      ev.preventDefault();
      this.elegir(this.opciones()[this.foco()].valor);
    }
  }

  // Clic fuera: se cierra
  @HostListener('document:click', ['$event'])
  fuera(ev: MouseEvent): void {
    if (this.abierto() && !this.host.nativeElement.contains(ev.target as Node)) this.abierto.set(false);
  }
}
