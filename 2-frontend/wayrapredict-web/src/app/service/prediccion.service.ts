import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Alerta } from '../model/alerta';
import { Prediccion } from '../model/prediccion';

// Pronóstico, historial y alertas (públicos) y verificación (usuario institucional)
@Injectable({ providedIn: 'root' })
export class PrediccionService {
  private apiURL = `${environment.apiUrl}/api`;

  constructor(private http: HttpClient) {}

  getProximosDias(codigo: string): Observable<Prediccion[]> {
    return this.http.get<Prediccion[]>(`${this.apiURL}/libre/predicciones-proximos-dias/${codigo}`);
  }

  getHistorial(codigo: string, desde?: string, hasta?: string): Observable<Prediccion[]> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<Prediccion[]>(`${this.apiURL}/libre/predicciones-historial/${codigo}`, { params });
  }

  getAlertas(estacion?: string, estado?: string): Observable<Alerta[]> {
    let params = new HttpParams();
    if (estacion) params = params.set('estacion', estacion);
    if (estado) params = params.set('estado', estado);
    return this.http.get<Alerta[]>(`${this.apiURL}/libre/alertas`, { params });
  }

  verificar(idPrediccion: number): Observable<Prediccion> {
    return this.http.put<Prediccion>(`${this.apiURL}/institucional/verificar-prediccion/${idPrediccion}`, {});
  }
}
