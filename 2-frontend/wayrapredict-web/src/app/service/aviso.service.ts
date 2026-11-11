import { Injectable, signal } from '@angular/core';

// Aviso breve en la parte inferior de la pantalla (equivalente al snackbar del ejemplo)
@Injectable({ providedIn: 'root' })
export class AvisoService {
  readonly aviso = signal<{ texto: string; error: boolean } | null>(null);
  private temporizador?: ReturnType<typeof setTimeout>;

  mostrar(texto: string, error = false): void {
    this.aviso.set({ texto, error });
    clearTimeout(this.temporizador);
    this.temporizador = setTimeout(() => this.aviso.set(null), 3500);
  }
}
