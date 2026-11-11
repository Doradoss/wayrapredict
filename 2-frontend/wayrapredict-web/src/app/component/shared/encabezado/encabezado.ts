import { Component, input } from '@angular/core';

// Encabezado de cada pantalla: título, subtítulo y, a la derecha, lo que la pantalla proyecte (filtros, botones)
@Component({
  selector: 'app-encabezado',
  template: `
    <header class="encabezado">
      <div>
        @if (eyebrow()) { <span class="eyebrow">{{ eyebrow() }}</span> }
        <h1>{{ titulo() }}</h1>
        @if (subtitulo()) { <p class="sub-title">{{ subtitulo() }}</p> }
      </div>
      <div class="encabezado__extra"><ng-content/></div>
    </header>
  `,
  styles: [`
    .encabezado { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px 24px; flex-wrap: wrap; margin-bottom: 20px; }
    .encabezado .eyebrow { display: block; margin-bottom: 4px; }
    .encabezado__extra:empty { display: none; }
  `],
})
export class Encabezado {
  titulo = input.required<string>();
  subtitulo = input('');
  eyebrow = input('');
}
