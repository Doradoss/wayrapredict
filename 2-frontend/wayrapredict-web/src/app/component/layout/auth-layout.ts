import { Component, computed, inject } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map } from 'rxjs';
import { TemaService } from '../../service/tema.service';

// Layout de acceso (iniciar sesión, solicitar cuenta, solicitud enviada): panel de marca a la izquierda y formulario
@Component({
  selector: 'app-auth-layout',
  imports: [RouterOutlet, RouterLink],
  template: `
    <div class="auth">
      <aside class="auth__panel">
        <div class="marca marca--auth">
          <img class="logo logo--fijo" src="simbolo-oscuro.svg" alt="" aria-hidden="true">
          <div><b>WayraPredict</b><small>Vigilancia predictiva del aire</small></div>
        </div>
        <div class="auth__pitch">
          @if (esLogin()) {
            <h1>Anticipa la calidad del aire de tu zona</h1>
            <p>Predicciones diarias de SO₂ y material particulado en Junín, Pasco y Moquegua, explicadas en lenguaje sencillo.</p>
          } @else {
            <h1>Cuentas para instituciones</h1>
            <p>La ciudadanía puede consultar el dashboard, las alertas y el asistente sin registrarse. Las cuentas son para personal de entidades públicas y deben ser aprobadas por el equipo de WayraPredict.</p>
          }
          <!-- Curva decorativa animada -->
          <svg class="auth__curva" viewBox="0 0 400 120" aria-hidden="true">
            <path d="M0 95 C40 90 60 60 100 66 S160 100 200 70 S270 20 310 40 S370 70 400 30" pathLength="1"/>
          </svg>
        </div>
        <div class="auth__leyenda">
          <span class="nav-titulo">Categorías del Índice de Calidad del Aire (INCA)</span>
          <div class="auth__barra"><i class="b-buena"></i><i class="b-moderada"></i><i class="b-mala"></i><i class="b-cuidado"></i></div>
          <div class="auth__items"><span>Buena</span><span>Moderada</span><span>Mala</span><span>Umbral de cuidado</span></div>
        </div>
      </aside>
      <section class="auth__main">
        <div class="auth__top">
          <button type="button" class="icon-btn" (click)="tema.alternar()" [attr.aria-label]="tema.tema() === 'oscuro' ? 'Cambiar a modo claro' : 'Cambiar a modo noche'"
                  [title]="tema.tema() === 'oscuro' ? 'Modo claro' : 'Modo noche'">
            <svg class="ico" aria-hidden="true"><use [attr.href]="tema.tema() === 'oscuro' ? '#i-sun' : '#i-moon'"/></svg>
          </button>
          <a class="link-btn" routerLink="/dashboard">Ir al dashboard<svg class="ico" style="transform: rotate(-90deg)" aria-hidden="true"><use href="#i-chevron"/></svg></a>
        </div>
        <div class="auth__form"><router-outlet/></div>
        <div class="auth__links"><a routerLink="/ayuda" [queryParams]="{ ir: 'quienes-somos' }">Nosotros</a><a routerLink="/ayuda" [queryParams]="{ ir: 'preguntas' }">Preguntas frecuentes</a><a href="mailto:wayrapredict@gmail.com">wayrapredict@gmail.com</a></div>
      </section>
    </div>
  `,
  styles: [`
    .auth { display: grid; grid-template-columns: minmax(380px, 520px) 1fr; min-height: 100vh; }
    .auth__panel { background: linear-gradient(160deg, #0f766e 0%, #115e59 55%, #0c4a6e 100%); color: #e6fffb; padding: 36px 40px;
      display: flex; flex-direction: column; justify-content: space-between; gap: 32px; position: relative; overflow: hidden; }
    .marca--auth { padding: 0; }
    .marca--auth .logo { width: 44px; height: 44px; }
    .marca--auth b { color: #fff; }
    .marca--auth small { color: #b8ece4; }
    .auth__pitch h1 { color: #fff; font-size: 34px; max-width: 420px; }
    .auth__pitch p { margin-top: 12px; color: #c9f1ea; font-size: 15px; line-height: 1.6; max-width: 420px; }
    .auth__curva { margin-top: 28px; width: 100%; max-width: 420px; }
    .auth__curva path { fill: none; stroke: #5eead4; stroke-width: 3; stroke-linecap: round; stroke-dasharray: 1; stroke-dashoffset: 1;
      animation: trazar-auth 1.8s cubic-bezier(.4, 0, .2, 1) .2s forwards; }
    @keyframes trazar-auth { to { stroke-dashoffset: 0; } }
    .auth__leyenda .nav-titulo { padding: 0 0 8px; color: #b8ece4; }
    .auth__barra { display: flex; gap: 4px; }
    .auth__barra i { flex: 1; height: 6px; border-radius: 3px; animation: crecer .8s ease both; }
    .auth__barra i:nth-child(2) { animation-delay: .1s; } .auth__barra i:nth-child(3) { animation-delay: .2s; } .auth__barra i:nth-child(4) { animation-delay: .3s; }
    .auth__items { display: flex; margin-top: 6px; font-size: 11px; color: #c9f1ea; }
    .auth__items span { flex: 1; }
    .auth__main { background: var(--bg-base); display: flex; flex-direction: column; padding: 20px 32px; min-width: 0; }
    .auth__top { display: flex; justify-content: space-between; align-items: center; }
    .auth__form { flex: 1; display: grid; place-items: center; padding: 24px 0; animation: aparecer .4s ease both; }
    .auth__links { display: flex; gap: 20px; justify-content: center; font-size: 12px; }
    @media (max-width: 900px) {
      .auth { grid-template-columns: 1fr; }
      .auth__panel { padding: 24px 20px; gap: 16px; }
      .auth__pitch h1 { font-size: 24px; }
      .auth__curva, .auth__leyenda { display: none; }
      .auth__main { padding: 16px; }
    }
  `],
})
export class AuthLayout {
  tema = inject(TemaService);
  private router = inject(Router);
  private url = toSignal(
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd), map(() => this.router.url)),
    { initialValue: this.router.url }
  );
  esLogin = computed(() => this.url().startsWith('/login'));
}
