import { Component, computed, OnInit, signal } from '@angular/core';
import { Alerta } from '../../model/alerta';
import { PrediccionService } from '../../service/prediccion.service';
import { EstacionService } from '../../service/estacion.service';
import { claseCategoria, fechaLarga, gravedad, mensajeError, nombreContaminante, numero, relativo } from '../../util/formato';
import { Encabezado } from '../shared/encabezado/encabezado';

// 6 · Alertas: predicciones de categoría Moderada o superior (vigentes y finalizadas)
@Component({
  selector: 'app-alertas',
  imports: [Encabezado],
  template: `
    <div class="view">
      <app-encabezado eyebrow="Alertas" titulo="Alertas de calidad del aire" subtitulo="Predicciones que alcanzan la categoría Moderada o superior del INCA">
        <div class="filtros">
          <label class="selector"><span>Departamento</span>
            <select [value]="fDepartamento()" (change)="fDepartamento.set($any($event.target).value)">
              <option value="">Todos</option>
              @for (d of departamentos(); track d) { <option [value]="d">{{ d }}</option> }
            </select>
          </label>
          <label class="selector"><span>Contaminante</span>
            <select [value]="fContaminante()" (change)="fContaminante.set($any($event.target).value)">
              <option value="">Todos</option><option value="SO2">SO₂</option><option value="PM10">PM10</option>
            </select>
          </label>
          <label class="selector"><span>Categoría INCA</span>
            <select [value]="fCategoria()" (change)="fCategoria.set($any($event.target).value)">
              <option value="">Moderada o superior</option><option value="Moderada">Moderada</option><option value="Mala">Mala</option><option value="Umbral de cuidado">Umbral de cuidado</option>
            </select>
          </label>
          <label class="selector"><span>Estado</span>
            <select [value]="fEstado()" (change)="fEstado.set($any($event.target).value)">
              <option value="">Vigentes y finalizadas</option><option value="vigente">Vigentes</option><option value="finalizada">Finalizadas</option>
            </select>
          </label>
        </div>
      </app-encabezado>

      <div class="card">
        <div class="kpis">
          <div class="kpi"><label>Alertas vigentes</label><strong>{{ vigentes().length }}</strong></div>
          <div class="kpi"><label>Con superación prevista del ECA-Aire</label><strong>{{ conEca() }}</strong></div>
          <div class="kpi"><label>Estaciones con alerta</label><strong>{{ estacionesConAlerta() }}<small>de {{ totalEstaciones() }}</small></strong></div>
          <div class="kpi"><label>Alertas registradas</label><strong>{{ alertas().length }}</strong></div>
        </div>
      </div>

      @if (error()) {
        <div class="aviso aviso--error mt"><svg class="ico ico--20" aria-hidden="true"><use href="#i-warning"/></svg><span>{{ error() }}</span></div>
      }

      <div class="card card--tabla mt">
        <div class="card__head">
          <div><h2>Registro de alertas</h2><p class="sub-title">{{ filtradas().length }} {{ filtradas().length === 1 ? 'alerta' : 'alertas' }} con los filtros elegidos</p></div>
        </div>
        <div style="overflow-x: auto">
          <table class="tabla">
            <thead><tr>
              <th scope="col">Estado</th><th scope="col">Fecha prevista</th><th scope="col">Estación</th>
              <th scope="col">Contaminante</th><th scope="col" class="num">Valor previsto</th><th scope="col">Categoría INCA</th><th scope="col">ECA-Aire 24 h</th>
            </tr></thead>
            <tbody>
              @for (a of filtradas(); track a.idPrediccion; let i = $index) {
                <tr [style.animation-delay.ms]="i * 40">
                  <td><span class="tag" [class.tag--marca]="a.estado === 'vigente'" [class.tag--neutro]="a.estado !== 'vigente'">{{ a.estado === 'vigente' ? 'Vigente' : 'Finalizada' }}</span></td>
                  <td class="fuerte">{{ rel(a.diasDesdeReferencia) }} <span class="meta">&nbsp;· {{ fl(a.fechaObjetivo) }}</span></td>
                  <td>{{ a.estacionNombre }} <span class="meta">&nbsp;· {{ a.departamento }}</span></td>
                  <td class="fuerte">{{ cont(a.contaminante) }}</td>
                  <td class="num">{{ num(a.valor, 0) }} µg/m³</td>
                  <td><span [class]="'tag tag--' + cat(a.categoriaInca)">{{ a.categoriaInca }}</span></td>
                  <td class="meta">{{ a.superaEca ? 'Supera el ECA-Aire' : '—' }}</td>
                </tr>
              } @empty {
                <tr><td colspan="7" class="vacio">{{ cargando() ? 'Cargando alertas…' : 'No hay alertas para los filtros elegidos.' }}</td></tr>
              }
            </tbody>
          </table>
        </div>
      </div>
      <p class="nota mt">Las alertas se generan a partir de las predicciones registradas por el proceso de predicción. «Vigente»: fecha prevista posterior al día actual de la estación.</p>
    </div>
  `,
})
export class Alertas implements OnInit {
  alertas = signal<Alerta[]>([]);
  totalEstaciones = signal(0);
  cargando = signal(true);
  error = signal('');
  fDepartamento = signal('');
  fContaminante = signal('');
  fCategoria = signal('');
  fEstado = signal('');

  cat = claseCategoria;
  cont = nombreContaminante;
  num = numero;
  rel = relativo;
  fl = fechaLarga;

  departamentos = computed(() => [...new Set(this.alertas().map((a) => a.departamento))]);
  vigentes = computed(() => this.alertas().filter((a) => a.estado === 'vigente'));
  conEca = computed(() => this.vigentes().filter((a) => a.superaEca).length);
  estacionesConAlerta = computed(() => new Set(this.vigentes().map((a) => a.estacion)).size);
  filtradas = computed(() =>
    this.alertas()
      .filter((a) => (!this.fDepartamento() || a.departamento === this.fDepartamento()) &&
                     (!this.fContaminante() || a.contaminante === this.fContaminante()) &&
                     (!this.fCategoria() || a.categoriaInca === this.fCategoria()) &&
                     (!this.fEstado() || a.estado === this.fEstado()))
      .sort((x, y) => (x.estado === y.estado ? 0 : x.estado === 'vigente' ? -1 : 1) ||
                      y.fechaObjetivo.localeCompare(x.fechaObjetivo) || gravedad(y.categoriaInca) - gravedad(x.categoriaInca))
  );

  constructor(private prediccionService: PrediccionService, private estacionService: EstacionService) {}

  ngOnInit(): void {
    this.prediccionService.getAlertas().subscribe({
      next: (a) => { this.alertas.set(a); this.cargando.set(false); },
      error: (err) => { this.error.set(mensajeError(err)); this.cargando.set(false); },
    });
    this.estacionService.getEstaciones().subscribe({ next: (e) => this.totalEstaciones.set(e.length) });
  }
}
