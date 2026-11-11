import { Component, effect, HostListener, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { Usuario } from '../../model/usuario';
import { LoginService } from '../../service/login.service';
import { PrediccionService } from '../../service/prediccion.service';
import { AyudaDestinoService } from '../../service/ayuda-destino.service';
import { TemaService } from '../../service/tema.service';
import { UsuarioService } from '../../service/usuario.service';
import { nombreRol } from '../../util/formato';
import { ChatAsistente } from '../shared/chat-asistente/chat-asistente';

// Layout de la aplicación (como ejemplo-diseño-1.html): barra lateral con el logo, la navegación,
// la leyenda INCA y abajo el tema y "Cerrar sesión"; barra superior con pestañas y, a la derecha, alertas,
// avatar y "Salir" (o "Iniciar sesión" para la ciudadanía).
@Component({
  selector: 'app-layout',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ChatAsistente],
  template: `
    <div class="app">
      <aside class="sidebar" [class.open]="menuAbierto()" id="barra-lateral">
        <div class="marca">
          <img class="logo logo--claro" src="simbolo-claro.svg" alt="" aria-hidden="true"><img class="logo logo--oscuro" src="simbolo-oscuro.svg" alt="" aria-hidden="true">
          <b>WayraPredict</b>
          <button type="button" class="icon-btn sidebar-cerrar" (click)="menuAbierto.set(false)" aria-label="Cerrar menú">
            <svg class="ico" aria-hidden="true"><use href="#i-close"/></svg>
          </button>
        </div>

        <div class="nav-titulo">Menú</div>
        <nav class="nav" aria-label="Navegación principal">
          <a routerLink="/dashboard" routerLinkActive="active"><svg class="ico" aria-hidden="true"><use href="#i-home"/></svg>Inicio</a>
          <a routerLink="/estacion" routerLinkActive="active"><svg class="ico" aria-hidden="true"><use href="#i-pin"/></svg>Estaciones</a>
          <a routerLink="/alertas" routerLinkActive="active"><svg class="ico" aria-hidden="true"><use href="#i-bell"/></svg>Alertas
            @if (vigentes() > 0) { <span class="badge-n badge-n--alerta">{{ vigentes() }}</span> }
          </a>
          @if (loginService.esAdmin()) {
            <a routerLink="/admin" routerLinkActive="active"><svg class="ico" aria-hidden="true"><use href="#i-shield"/></svg>Administración</a>
          }
          <a routerLink="/ayuda" routerLinkActive="active"><svg class="ico" aria-hidden="true"><use href="#i-info"/></svg>Nosotros y ayuda</a>
        </nav>

        <div class="nav-titulo">Índice INCA</div>
        <div class="leyenda-inca" title="INCA = concentración ÷ ECA-Aire de 24 h × 100">
          <div><i class="b-buena"></i><span><b>Buena</b><small>INCA 0 – 50</small></span></div>
          <div><i class="b-moderada"></i><span><b>Moderada</b><small>INCA 51 – 100</small></span></div>
          <div><i class="b-mala"></i><span><b>Mala</b><small>Sobre el ECA-Aire</small></span></div>
          <div><i class="b-cuidado"></i><span><b>Umbral de cuidado</b><small>Sobre el VUEC</small></span></div>
        </div>

        <div class="bottom">
          <nav class="nav">
            <a (click)="tema.alternar()" role="button" tabindex="0" (keydown.enter)="tema.alternar()">
              <svg class="ico" aria-hidden="true"><use [attr.href]="tema.tema() === 'oscuro' ? '#i-sun' : '#i-moon'"/></svg>
              {{ tema.tema() === 'oscuro' ? 'Modo claro' : 'Modo noche' }}
            </a>
            @if (loginService.autenticado()) {
              <a class="danger" (click)="loginService.logout()" role="button" tabindex="0" (keydown.enter)="loginService.logout()">
                <svg class="ico" aria-hidden="true"><use href="#i-logout"/></svg>Cerrar sesión
              </a>
            } @else {
              <a routerLink="/registro"><svg class="ico" aria-hidden="true"><use href="#i-user"/></svg>Solicitar cuenta institucional</a>
            }
          </nav>
        </div>
      </aside>

      @if (menuAbierto()) { <div class="velo" (click)="menuAbierto.set(false)" aria-hidden="true"></div> }

      <div class="main">
        <header class="topbar">
          <button type="button" class="icon-btn menu-toggle" (click)="menuAbierto.set(!menuAbierto())" aria-label="Abrir menú"
                  aria-controls="barra-lateral" [attr.aria-expanded]="menuAbierto()">
            <svg class="ico" aria-hidden="true"><use href="#i-menu"/></svg>
          </button>
          <nav class="tabs" aria-label="Secciones">
            <a routerLink="/dashboard" routerLinkActive="active"><svg class="ico ico--18" aria-hidden="true"><use href="#i-home"/></svg><span class="lbl-hide">Inicio</span></a>
            <a routerLink="/estacion" routerLinkActive="active"><svg class="ico ico--18" aria-hidden="true"><use href="#i-chart"/></svg><span class="lbl-hide">Estaciones</span></a>
            <a routerLink="/alertas" routerLinkActive="active"><svg class="ico ico--18" aria-hidden="true"><use href="#i-bell"/></svg><span class="lbl-hide">Alertas</span></a>
            @if (loginService.esAdmin()) {
              <a routerLink="/admin" routerLinkActive="active"><svg class="ico ico--18" aria-hidden="true"><use href="#i-shield"/></svg><span class="lbl-hide">Administración</span></a>
            }
          </nav>
          <div class="top-right">
            <button type="button" class="icon-btn tema-btn" (click)="tema.alternar()" [attr.aria-label]="tema.tema() === 'oscuro' ? 'Cambiar a modo claro' : 'Cambiar a modo noche'"
                    [title]="tema.tema() === 'oscuro' ? 'Modo claro' : 'Modo noche'">
              <svg class="ico" aria-hidden="true"><use [attr.href]="tema.tema() === 'oscuro' ? '#i-sun' : '#i-moon'"/></svg>
            </button>
            <a class="icon-btn" routerLink="/alertas" aria-label="Alertas vigentes" title="Alertas vigentes">
              <svg class="ico" aria-hidden="true"><use href="#i-bell"/></svg>
              @if (vigentes() > 0) { <span class="dot-n">{{ vigentes() }}</span> }
            </a>
            @if (loginService.usuario(); as u) {
              <div class="perfil" tabindex="0" aria-label="Datos de tu cuenta">
                <div class="avatar avatar--sm">{{ iniciales(u.nombre) }}</div>
                <div class="perfil__tarjeta" role="tooltip">
                  <div class="perfil__cab">
                    <div class="avatar">{{ iniciales(u.nombre) }}</div>
                    <div class="perfil__nombre"><b>{{ u.nombre }}</b><small>{{ u.correo }}</small></div>
                  </div>
                  <dl class="perfil__datos">
                    <div><dt>Rol</dt><dd><span class="tag tag--marca">{{ rol(u.rol) }}</span></dd></div>
                    @if (perfil()?.institucion) { <div><dt>Institución</dt><dd>{{ perfil()!.institucion }}</dd></div> }
                    @if (perfil()?.cargo) { <div><dt>Cargo</dt><dd>{{ perfil()!.cargo }}</dd></div> }
                  </dl>
                  <button type="button" class="btn btn--sm peligro perfil__salir" (click)="loginService.logout()">
                    <svg class="ico" aria-hidden="true"><use href="#i-logout"/></svg>Cerrar sesión</button>
                </div>
              </div>
              <a class="link-btn" (click)="loginService.logout()" role="button" tabindex="0" (keydown.enter)="loginService.logout()" title="Cerrar sesión">
                <svg class="ico" aria-hidden="true"><use href="#i-logout"/></svg><span class="lbl">Salir</span>
              </a>
            } @else {
              <a class="btn primary" routerLink="/login" title="Iniciar sesión"><svg class="ico" aria-hidden="true"><use href="#i-login"/></svg><span class="lbl">Iniciar sesión</span></a>
            }
          </div>
        </header>

        <div class="content">
          <router-outlet/>
          <footer class="pie">
            <div class="pie__columnas">
              <div class="pie__acerca">
                <div class="marca marca--pie">
                  <img class="logo logo--claro" src="simbolo-claro.svg" alt="" aria-hidden="true"><img class="logo logo--oscuro" src="simbolo-oscuro.svg" alt="" aria-hidden="true">
                  <div><b>WayraPredict</b><small>Vigilancia predictiva del aire</small></div>
                </div>
                <p>Vigilancia predictiva de la calidad del aire en zonas con actividad minero-industrial del Perú.</p>
              </div>
              <div class="pie__col">
                <span class="nav-titulo">Nosotros</span>
                <a routerLink="/ayuda" [queryParams]="{ ir: 'quienes-somos' }" (click)="ayudaDestino.pedir('quienes-somos')">Quiénes somos</a>
                <a routerLink="/ayuda" [queryParams]="{ ir: 'proyecto' }" (click)="ayudaDestino.pedir('proyecto')">El proyecto</a>
                <a routerLink="/ayuda" [queryParams]="{ ir: 'modelo' }" (click)="ayudaDestino.pedir('modelo')">Cómo funciona el modelo</a>
              </div>
              <div class="pie__col">
                <span class="nav-titulo">Ayuda</span>
                <a routerLink="/ayuda" [queryParams]="{ ir: 'preguntas' }" (click)="ayudaDestino.pedir('preguntas')">Preguntas frecuentes</a>
                <a routerLink="/ayuda" [queryParams]="{ ir: 'inca' }" (click)="ayudaDestino.pedir('inca')">¿Qué es el INCA?</a>
              </div>
              <div class="pie__col">
                <span class="nav-titulo">Contacto</span>
                <a class="pie__correo" href="mailto:wayrapredict@gmail.com"><svg class="ico" aria-hidden="true"><use href="#i-mail"/></svg>wayrapredict@gmail.com</a>
                <small class="muted">Consultas sobre la plataforma y solicitudes de información</small>
              </div>
            </div>
            <div class="pie__base">
              <span>© 2026 WayraPredict · Datos de vigilancia: OEFA, Plataforma Nacional de Datos Abiertos</span>
              <span>Ley N.° 29733 de protección de datos personales</span>
            </div>
          </footer>
        </div>
      </div>
    </div>
    <app-chat-asistente/>
  `,

})
export class AppLayout {
  vigentes = signal(0);
  perfil = signal<Usuario | null>(null);
  menuAbierto = signal(false);
  rol = nombreRol;

  constructor(
    public loginService: LoginService,
    public tema: TemaService,
    public ayudaDestino: AyudaDestinoService,
    prediccionService: PrediccionService,
    usuarioService: UsuarioService,
    router: Router
  ) {
    prediccionService.getAlertas(undefined, 'vigente').subscribe({ next: (a) => this.vigentes.set(a.length), error: () => this.vigentes.set(0) });
    // Institución del usuario (solo con sesión)
    effect(() => {
      if (this.loginService.autenticado()) {
        usuarioService.getPerfil().subscribe({ next: (p) => this.perfil.set(p), error: () => this.perfil.set(null) });
      } else {
        this.perfil.set(null);
      }
    });
    // En el celular, el menú se cierra al navegar
    router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => this.menuAbierto.set(false));
  }

  @HostListener('document:keydown.escape')
  cerrarMenu(): void {
    this.menuAbierto.set(false);
  }

  iniciales(nombre: string): string {
    return nombre.split(/\s+/).filter((p) => p).slice(0, 2).map((p) => p.charAt(0).toUpperCase()).join('');
  }
}
