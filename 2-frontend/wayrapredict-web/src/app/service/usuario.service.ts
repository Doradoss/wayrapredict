import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Ejecucion } from '../model/ejecucion';
import { SolicitudCuenta, Usuario } from '../model/usuario';

// Cuentas: solicitud (pública), perfil (con sesión) y administración (solo administradores)
@Injectable({ providedIn: 'root' })
export class UsuarioService {
  private apiURL = `${environment.apiUrl}/api`;

  constructor(private http: HttpClient) {}

  solicitarCuenta(solicitud: SolicitudCuenta): Observable<Usuario> {
    return this.http.post<Usuario>(`${this.apiURL}/libre/solicitar-cuenta`, solicitud);
  }

  getPerfil(): Observable<Usuario> {
    return this.http.get<Usuario>(`${this.apiURL}/cuenta/mi-perfil`);
  }

  getUsuarios(estado?: string): Observable<Usuario[]> {
    const params = estado ? new HttpParams().set('estado', estado) : undefined;
    return this.http.get<Usuario[]>(`${this.apiURL}/admin/usuarios`, { params });
  }

  aprobar(id: number): Observable<Usuario> {
    return this.http.put<Usuario>(`${this.apiURL}/admin/aprobar-usuario/${id}`, {});
  }

  rechazar(id: number): Observable<Usuario> {
    return this.http.put<Usuario>(`${this.apiURL}/admin/rechazar-usuario/${id}`, {});
  }

  cambiarRol(id: number, rol: string): Observable<Usuario> {
    return this.http.put<Usuario>(`${this.apiURL}/admin/cambiar-rol/${id}`, { rol });
  }

  getEjecuciones(): Observable<Ejecucion[]> {
    return this.http.get<Ejecucion[]>(`${this.apiURL}/admin/ejecuciones`);
  }
}
