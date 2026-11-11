import { HttpClient } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { JwtRequest, JwtResponse } from '../model/jwt';

export const ROL_ADMIN = 'administrador';
export const ROL_INSTITUCIONAL = 'usuario_institucional';

interface Sesion {
  token: string;
  correo: string;
  rol: string;
  nombre: string;
  expira: number; // milisegundos (época)
}

// Sesión del usuario: el token JWT se guarda en sessionStorage (se borra al cerrar el navegador)
@Injectable({ providedIn: 'root' })
export class LoginService {
  private apiURL = `${environment.apiUrl}/authenticate`;
  private sesion = signal<Sesion | null>(this.leerSesion());

  readonly usuario = this.sesion.asReadonly();
  readonly autenticado = computed(() => this.sesion() !== null);
  readonly esAdmin = computed(() => this.sesion()?.rol === ROL_ADMIN);
  readonly esInstitucional = computed(() => this.sesion()?.rol === ROL_INSTITUCIONAL);

  constructor(private http: HttpClient, private router: Router) {}

  login(request: JwtRequest): Observable<JwtResponse> {
    return this.http.post<JwtResponse>(this.apiURL, request).pipe(
      tap((r) => {
        const s: Sesion = { token: r.jwttoken, correo: r.correo, rol: r.rol, nombre: r.nombre, expira: Date.now() + r.validezMs };
        sessionStorage.setItem('sesion', JSON.stringify(s));
        this.sesion.set(s);
      })
    );
  }

  logout(irAlLogin = true): void {
    sessionStorage.removeItem('sesion');
    this.sesion.set(null);
    if (irAlLogin) this.router.navigate(['/login']);
  }

  // Token vigente o null (si venció, se cierra la sesión)
  token(): string | null {
    const s = this.sesion();
    if (s && Date.now() >= s.expira) {
      this.logout(false);
      return null;
    }
    return s?.token ?? null;
  }

  verificar(): boolean {
    return this.token() !== null;
  }

  private leerSesion(): Sesion | null {
    try {
      const s = JSON.parse(sessionStorage.getItem('sesion') ?? 'null') as Sesion | null;
      return s && Date.now() < s.expira ? s : null;
    } catch {
      return null;
    }
  }
}
