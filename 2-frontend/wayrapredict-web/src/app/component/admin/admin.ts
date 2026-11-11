import { Component, computed, OnInit, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { Ejecucion } from '../../model/ejecucion';
import { Usuario } from '../../model/usuario';
import { AvisoService } from '../../service/aviso.service';
import { LoginService, ROL_ADMIN, ROL_INSTITUCIONAL } from '../../service/login.service';
import { UsuarioService } from '../../service/usuario.service';
import { fechaHora, mensajeError, nombreRol, numero } from '../../util/formato';
import { Encabezado } from '../shared/encabezado/encabezado';

// 8 · Administración (solo rol administrador): solicitudes de cuenta, roles y ejecuciones del proceso
@Component({
  selector: 'app-admin',
  imports: [Encabezado],
  templateUrl: './admin.html',
})
export class Admin implements OnInit {
  usuarios = signal<Usuario[]>([]);
  ejecuciones = signal<Ejecucion[]>([]);
  busqueda = signal('');
  cargando = signal(true);
  ocupado = signal<number | null>(null);
  error = signal('');

  rol = nombreRol;
  fh = fechaHora;
  num = numero;

  pendientes = computed(() => this.usuarios().filter((u) => u.estado === 'pendiente').length);
  activos = computed(() => this.usuarios().filter((u) => u.estado === 'aprobado').length);
  filtrados = computed(() => {
    const q = this.busqueda().trim().toLowerCase();
    const orden: Record<string, number> = { pendiente: 0, aprobado: 1, rechazado: 2 };
    return this.usuarios()
      .filter((u) => !q || `${u.nombres} ${u.apellidos} ${u.correo} ${u.institucion ?? ''}`.toLowerCase().includes(q))
      .sort((a, b) => orden[a.estado] - orden[b.estado] || a.apellidos.localeCompare(b.apellidos));
  });
  ultimasEjecuciones = computed(() => [...this.ejecuciones()].sort((a, b) => (b.fechaFin ?? '').localeCompare(a.fechaFin ?? '') || b.idEjecucion - a.idEjecucion).slice(0, 6));

  constructor(private usuarioService: UsuarioService, private loginService: LoginService, private aviso: AvisoService) {}

  ngOnInit(): void {
    this.cargarUsuarios();
    this.usuarioService.getEjecuciones().subscribe({ next: (e) => this.ejecuciones.set(e), error: () => this.ejecuciones.set([]) });
  }

  private cargarUsuarios(): void {
    this.usuarioService.getUsuarios().subscribe({
      next: (u) => { this.usuarios.set(u); this.cargando.set(false); },
      error: (err) => { this.error.set(mensajeError(err)); this.cargando.set(false); },
    });
  }

  esYo(u: Usuario): boolean {
    return u.correo.toLowerCase() === this.loginService.usuario()?.correo.toLowerCase();
  }

  aprobar(u: Usuario): void {
    this.ejecutar(u, this.usuarioService.aprobar(u.idUsuario), `Cuenta de ${u.nombres} aprobada`);
  }

  rechazar(u: Usuario): void {
    const texto = u.estado === 'aprobado'
      ? `¿Revocar el acceso de ${u.nombres} ${u.apellidos}? Ya no podrá iniciar sesión.`
      : `¿Rechazar la solicitud de ${u.nombres} ${u.apellidos}?`;
    if (!confirm(texto)) return;
    this.ejecutar(u, this.usuarioService.rechazar(u.idUsuario), u.estado === 'aprobado' ? 'Acceso revocado' : 'Solicitud rechazada');
  }

  cambiarRol(u: Usuario): void {
    const nuevo = u.rol === ROL_ADMIN ? ROL_INSTITUCIONAL : ROL_ADMIN;
    if (!confirm(`¿Cambiar el rol de ${u.nombres} ${u.apellidos} a «${nombreRol(nuevo)}»?`)) return;
    this.ejecutar(u, this.usuarioService.cambiarRol(u.idUsuario, nuevo), `Rol cambiado a ${nombreRol(nuevo)}`);
  }

  private ejecutar(u: Usuario, accion: Observable<Usuario>, ok: string): void {
    this.ocupado.set(u.idUsuario);
    accion.subscribe({
      next: (r) => {
        this.usuarios.update((lista) => lista.map((x) => (x.idUsuario === r.idUsuario ? r : x)));
        this.ocupado.set(null);
        this.aviso.mostrar(ok);
      },
      error: (err) => {
        this.ocupado.set(null);
        this.aviso.mostrar(mensajeError(err), true);
      },
    });
  }

  // Nombre de cada ejecución según lo que registró
  nombreEjecucion(e: Ejecucion): string {
    if (e.predicciones > 0 && e.mediciones > 0) return 'Carga de datos y predicciones';
    if (e.predicciones > 0) return `Generación de predicciones (${numero(e.predicciones)})`;
    if (e.mediciones > 0) return `Carga de mediciones (${numero(e.mediciones)})`;
    return `Ejecución ${e.idEjecucion}`;
  }
}
