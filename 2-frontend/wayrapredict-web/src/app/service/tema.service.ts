import { Injectable, signal } from '@angular/core';

export type Tema = 'claro' | 'oscuro';

// Tema de la interfaz (claro o modo noche). Se aplica como atributo data-tema en <html> y se recuerda en el navegador.
@Injectable({ providedIn: 'root' })
export class TemaService {
  readonly tema = signal<Tema>(document.documentElement.getAttribute('data-tema') === 'oscuro' ? 'oscuro' : 'claro');

  alternar(): void {
    const nuevo: Tema = this.tema() === 'oscuro' ? 'claro' : 'oscuro';
    this.tema.set(nuevo);
    document.documentElement.setAttribute('data-tema', nuevo);
    try {
      localStorage.setItem('wayra-tema', nuevo);
    } catch {
      // sin almacenamiento (ventana privada): el tema dura solo esta sesión
    }
  }
}
