import { Component, signal } from '@angular/core';
import { FormsModule, NgForm } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { SolicitudCuenta } from '../../model/usuario';
import { UsuarioService } from '../../service/usuario.service';
import { mensajeError } from '../../util/formato';

// 2 · Solicitar cuenta institucional (queda pendiente hasta que un administrador la apruebe)
@Component({
  selector: 'app-registro',
  imports: [FormsModule, RouterLink],
  template: `
    <form class="form-auth form-auth--ancho" #f="ngForm" (ngSubmit)="enviar(f)">
      <div><span class="eyebrow">Registro</span><h2>Solicitar cuenta institucional</h2></div>
      <div class="aviso aviso--info"><svg class="ico ico--20" aria-hidden="true"><use href="#i-info"/></svg><span>El registro es solo para personal de instituciones. Tu cuenta podrá usarse cuando el equipo de WayraPredict apruebe la solicitud.</span></div>
      @if (error()) {
        <div class="aviso aviso--error"><svg class="ico ico--20" aria-hidden="true"><use href="#i-warning"/></svg><span>{{ error() }}</span></div>
      }
      <div class="grid-campos">
        <label class="campo">Nombres<input class="input" type="text" name="nombres" [(ngModel)]="s.nombres" required maxlength="80" placeholder="Nombres"></label>
        <label class="campo">Apellidos<input class="input" type="text" name="apellidos" [(ngModel)]="s.apellidos" required maxlength="80" placeholder="Apellidos"></label>
      </div>
      <label class="campo">Correo institucional
        <input class="input" type="email" name="correo" [(ngModel)]="s.correo" required maxlength="150" placeholder="nombre@entidad.gob.pe">
        @if (intentado() && !correoValido()) {
          <small class="error">Debe ser un correo institucional que termine en .gob.pe</small>
        } @else {
          <small>Debe terminar en .gob.pe</small>
        }
      </label>
      <div class="grid-campos">
        <label class="campo">Institución
          <select class="input" name="institucion" [(ngModel)]="s.institucion" required>
            <option value="" disabled>Selecciona tu institución</option>
            @for (i of instituciones; track i) { <option [value]="i">{{ i }}</option> }
          </select>
        </label>
        <label class="campo">Cargo o área<input class="input" type="text" name="cargo" [(ngModel)]="s.cargo" maxlength="100" placeholder="Ej.: especialista ambiental"></label>
      </div>
      <div class="grid-campos">
        <label class="campo">Contraseña
          <input class="input" type="password" name="password" [(ngModel)]="s.password" required minlength="8" maxlength="72" placeholder="Mínimo 8 caracteres" autocomplete="new-password">
          @if (intentado() && s.password.length < 8) { <small class="error">Mínimo 8 caracteres</small> }
        </label>
        <label class="campo">Confirmar contraseña
          <input class="input" type="password" name="confirmacion" [(ngModel)]="confirmacion" required placeholder="Repite la contraseña" autocomplete="new-password">
          @if (intentado() && confirmacion !== s.password) { <small class="error">Las contraseñas no coinciden</small> }
        </label>
      </div>
      <label class="check"><input type="checkbox" name="acepta" [(ngModel)]="s.aceptaTratamientoDatos">Acepto el tratamiento de mis datos personales conforme a la Ley N.° 29733, únicamente para la gestión de mi cuenta.</label>
      @if (intentado() && !s.aceptaTratamientoDatos) { <small class="error">Debes aceptar el tratamiento de datos personales.</small> }
      <button type="submit" class="btn primary block" [disabled]="enviando()">{{ enviando() ? 'Enviando…' : 'Enviar solicitud' }}</button>
      <span class="form-auth__cambio">¿Ya tienes una cuenta aprobada? <a routerLink="/login">Inicia sesión</a></span>
    </form>
  `,
})
export class Registro {
  readonly instituciones = ['OEFA', 'MINAM', 'SENAMHI', 'DIRESA / GERESA', 'Gobierno regional', 'Municipalidad', 'Otra entidad pública'];
  s: SolicitudCuenta = { nombres: '', apellidos: '', correo: '', password: '', institucion: '', cargo: '', aceptaTratamientoDatos: false };
  confirmacion = '';
  intentado = signal(false);
  enviando = signal(false);
  error = signal('');

  constructor(private usuarioService: UsuarioService, private router: Router) {}

  correoValido(): boolean {
    return /^[^@\s]+@([a-z0-9-]+\.)*gob\.pe$/i.test(this.s.correo.trim());
  }

  enviar(f: NgForm): void {
    this.intentado.set(true);
    this.error.set('');
    const ok = f.valid && this.correoValido() && this.s.password.length >= 8 && this.confirmacion === this.s.password && this.s.aceptaTratamientoDatos;
    if (!ok) {
      this.error.set('Revisa los campos marcados.');
      return;
    }
    this.enviando.set(true);
    this.usuarioService.solicitarCuenta({ ...this.s, correo: this.s.correo.trim() }).subscribe({
      next: () => this.router.navigate(['/registro-enviado']),
      error: (err) => {
        this.enviando.set(false);
        this.error.set(err.status === 409 ? 'Ya existe una cuenta con ese correo.' : mensajeError(err));
      },
    });
  }
}
