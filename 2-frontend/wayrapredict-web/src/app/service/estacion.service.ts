import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, shareReplay } from 'rxjs';
import { environment } from '../../environments/environment';
import { CategoriaInca } from '../model/categoria-inca';
import { Estacion } from '../model/estacion';
import { MetricaModelo } from '../model/metrica';
import { SerieDiaria } from '../model/serie-diaria';

// Servicios públicos de estaciones, mediciones, métricas y leyenda del INCA
@Injectable({ providedIn: 'root' })
export class EstacionService {
  private apiURL = `${environment.apiUrl}/api/libre`;
  private categorias$?: Observable<CategoriaInca[]>;

  constructor(private http: HttpClient) {}

  getEstaciones(): Observable<Estacion[]> {
    return this.http.get<Estacion[]>(`${this.apiURL}/estaciones`);
  }

  getSerieDiaria(codigo: string, desde?: string, hasta?: string): Observable<SerieDiaria[]> {
    let params = new HttpParams();
    if (desde) params = params.set('desde', desde);
    if (hasta) params = params.set('hasta', hasta);
    return this.http.get<SerieDiaria[]>(`${this.apiURL}/serie-diaria/${codigo}`, { params });
  }

  getMetricasVigente(estacion?: string): Observable<MetricaModelo[]> {
    const params = estacion ? new HttpParams().set('estacion', estacion) : undefined;
    return this.http.get<MetricaModelo[]>(`${this.apiURL}/metricas-modelo-vigente`, { params });
  }

  // La leyenda no cambia: se pide una sola vez
  getCategorias(): Observable<CategoriaInca[]> {
    this.categorias$ ??= this.http.get<CategoriaInca[]>(`${this.apiURL}/categorias-inca`).pipe(shareReplay(1));
    return this.categorias$;
  }
}
