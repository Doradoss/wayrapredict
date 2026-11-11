import { Injectable, signal } from '@angular/core';

// Sección o pregunta de "Nosotros y ayuda" que se pidió abrir desde un enlace (pie de página, acceso).
// El contador hace que un segundo clic en el mismo enlace vuelva a llevar a la pregunta.
@Injectable({ providedIn: 'root' })
export class AyudaDestinoService {
  readonly destino = signal<{ id: string; n: number } | null>(null);
  private n = 0;

  pedir(id: string): void {
    this.destino.set({ id, n: ++this.n });
  }
}
