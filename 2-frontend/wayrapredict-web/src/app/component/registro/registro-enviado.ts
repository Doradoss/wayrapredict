import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

// 3 · Solicitud enviada (pendiente de aprobación)
@Component({
  selector: 'app-registro-enviado',
  imports: [RouterLink],
  template: `
    <div class="form-auth">
      <div class="icono-estado"><svg class="ico ico--20" aria-hidden="true"><use href="#i-check"/></svg></div>
      <div>
        <h2>Solicitud enviada</h2>
        <p class="sub-title">Recibimos tu solicitud de cuenta institucional. El equipo de WayraPredict la revisará antes de habilitar tu acceso.</p>
      </div>
      <div class="pasos-lista">
        <div class="paso-item"><span>1</span><div><b>Revisión de la solicitud</b><small>Se verifica el correo institucional y la institución indicada.</small></div></div>
        <div class="paso-item"><span>2</span><div><b>Aprobación de la cuenta</b><small>El administrador aprueba o rechaza la solicitud.</small></div></div>
        <div class="paso-item"><span>3</span><div><b>Inicio de sesión</b><small>Cuando la cuenta esté aprobada, podrás ingresar con tu correo y contraseña.</small></div></div>
      </div>
      <p class="nota">Si intentas ingresar antes de la aprobación, verás este aviso:</p>
      <div class="aviso aviso--advertencia"><svg class="ico ico--20" aria-hidden="true"><use href="#i-info"/></svg><span>Tu cuenta aún está pendiente de aprobación. Podrás iniciar sesión cuando el equipo de WayraPredict la habilite.</span></div>
      <a class="btn block" routerLink="/dashboard">Ir al dashboard</a>
    </div>
  `,
})
export class RegistroEnviado {}
