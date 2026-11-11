import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { JwtRequest } from '../../model/jwt';
import { AvisoService } from '../../service/aviso.service';
import { LoginService } from '../../service/login.service';
import { mensajeError } from '../../util/formato';

// 1 · Iniciar sesión (correo y contraseña; solo cuentas aprobadas)
@Component({
  selector: 'app-login',
  imports: [FormsModule, RouterLink],
  template: `
    <form class="form-auth" (ngSubmit)="login()">
      <div>
        <span class="eyebrow">Acceso institucional</span>
        <h2>Iniciar sesión</h2>
        <p class="sub-title">Con una cuenta institucional puedes marcar predicciones pasadas como verificadas.</p>
      </div>
      @if (pendiente()) {
        <div class="aviso aviso--advertencia"><svg class="ico ico--20" aria-hidden="true"><use href="#i-info"/></svg><span>{{ pendiente() }}</span></div>
      }
      @if (error()) {
        <div class="aviso aviso--error"><svg class="ico ico--20" aria-hidden="true"><use href="#i-warning"/></svg><span>{{ error() }}</span></div>
      }
      <label class="campo">Correo institucional
        <input class="input" type="email" name="correo" [(ngModel)]="correo" required placeholder="nombre@entidad.gob.pe" autocomplete="username">
      </label>
      <label class="campo">Contraseña
        <input class="input" type="password" name="password" [(ngModel)]="password" required placeholder="Ingresa tu contraseña" autocomplete="current-password">
      </label>
      <button type="submit" class="btn primary block" [disabled]="enviando() || !correo || !password">
        <svg class="ico" aria-hidden="true"><use href="#i-login"/></svg>{{ enviando() ? 'Ingresando…' : 'Ingresar' }}</button>
      <div class="separador">o</div>
      <a class="btn block" routerLink="/dashboard">Consultar sin cuenta (acceso ciudadano)</a>
      <span class="form-auth__cambio">¿Trabajas en una institución? <a routerLink="/registro">Solicita una cuenta</a></span>
    </form>
  `,
})
export class Login {
  correo = '';
  password = '';
  enviando = signal(false);
  error = signal('');
  pendiente = signal('');

  constructor(private loginService: LoginService, private router: Router, private aviso: AvisoService) {}

  login(): void {
    const request: JwtRequest = { correo: this.correo.trim(), password: this.password };
    this.enviando.set(true);
    this.error.set('');
    this.pendiente.set('');
    this.loginService.login(request).subscribe({
      next: (r) => {
        this.enviando.set(false);
        this.aviso.mostrar(`Bienvenido, ${r.nombre}`);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.enviando.set(false);
        if (err.status === 403) {
          // Cuenta pendiente o rechazada: el backend explica el motivo
          this.pendiente.set(mensajeError(err));
        } else if (err.status === 401) {
          this.error.set('Correo o contraseña incorrectos.');
        } else {
          this.error.set(mensajeError(err));
        }
      },
    });
  }
}
