import { Component, computed, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { Alerta } from '../../model/alerta';
import { Estacion } from '../../model/estacion';
import { Prediccion } from '../../model/prediccion';
import { SerieDiaria } from '../../model/serie-diaria';
import { AsistenteService } from '../../service/asistente.service';
import { EstacionService } from '../../service/estacion.service';
import { PrediccionService } from '../../service/prediccion.service';
import {
  claseCategoria, fechaHora, fechaLarga, gravedad, mensajeError, nombreContaminante, numero, relativo, sumarDias, unidad,
} from '../../util/formato';
import { BarraDia, BarrasDias } from '../shared/barras-dias/barras-dias';
import { Desplegable, OpcionDesplegable } from '../shared/desplegable/desplegable';
import { Encabezado } from '../shared/encabezado/encabezado';
import { GraficoSerie, PuntoObservado, PuntoPronostico } from '../shared/grafico-serie/grafico-serie';

// 4 · Dashboard: indicadores, tarjetas de estaciones, alerta anticipada, gráfico y próximos días
@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, Encabezado, GraficoSerie, BarrasDias, Desplegable],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit {
  estaciones = signal<Estacion[]>([]);
  proximos = signal<Record<string, Prediccion[]>>({});
  alertas = signal<Alerta[]>([]);
  // Series de los últimos 14 días por estación (se piden una vez y se reutilizan al volver a una estación)
  series = signal<Record<string, SerieDiaria[]>>({});
  // seleccionada: la estación elegida (tarjeta resaltada). mostrada: la del gráfico y los próximos días, que solo
  // cambia cuando ya llegaron su serie y su pronóstico (así la animación no dibuja datos mezclados de dos estaciones)
  seleccionada = signal<string>('');
  mostrada = signal<string>('');
  cargando = signal(true);
  actualizando = computed(() => this.seleccionada() !== this.mostrada());
  error = signal('');
  filtroDepartamento = signal('');
  filtroContaminante = signal('');

  // utilidades para la plantilla
  cat = claseCategoria;
  cont = nombreContaminante;
  num = numero;
  rel = relativo;
  uni = unidad;
  fl = fechaLarga;

  departamentos = computed(() => [...new Set(this.estaciones().map((e) => e.departamento))]);
  contaminantes = computed(() => [...new Set(this.estaciones().map((e) => e.contaminante))]);
  opcionesDepartamento = computed<OpcionDesplegable[]>(() => [{ valor: '', texto: 'Todos' }, ...this.departamentos().map((d) => ({ valor: d, texto: d }))]);
  opcionesContaminante = computed<OpcionDesplegable[]>(() => [{ valor: '', texto: 'Todos' }, ...this.contaminantes().map((c) => ({ valor: c, texto: nombreContaminante(c) }))]);
  visibles = computed(() =>
    this.estaciones().filter(
      (e) => (!this.filtroDepartamento() || e.departamento === this.filtroDepartamento()) &&
             (!this.filtroContaminante() || e.contaminante === this.filtroContaminante())
    )
  );
  estacion = computed(() => this.estaciones().find((e) => e.codigo === this.mostrada()) ?? null);
  proximosSel = computed(() => this.proximos()[this.mostrada()] ?? []);
  ultimaActualizacion = computed(() => {
    const f = this.estaciones().map((e) => e.ultimaActualizacionPredicciones).filter((x): x is string => !!x).sort();
    return f.length ? fechaHora(f[f.length - 1]) : '—';
  });

  // Peor categoría prevista entre todas las estaciones (indicador)
  peorPrevista = computed(() => {
    const todas = Object.values(this.proximos()).flat();
    if (!todas.length) return null;
    return todas.reduce((a, b) => (gravedad(b.categoriaInca) > gravedad(a.categoriaInca) ? b : a)).categoriaInca;
  });

  // Alerta más grave entre las vigentes (la que se destaca arriba)
  alertaPrincipal = computed(() => {
    const v = [...this.alertas()].sort((a, b) => gravedad(b.categoriaInca) - gravedad(a.categoriaInca) || b.valorInca - a.valorInca);
    return v[0] ?? null;
  });

  observados = computed<PuntoObservado[]>(() =>
    (this.series()[this.mostrada()] ?? []).filter((d) => !d.posteriorAReferencia).map((d) => ({ fecha: d.fecha, valor: d.contaminante, origen: d.origenContaminante }))
  );
  pronostico = computed<PuntoPronostico[]>(() =>
    this.proximosSel().map((p) => ({ fecha: p.fechaObjetivo, valor: p.valor, inferior: p.limiteInferior, superior: p.limiteSuperior }))
  );

  // Barras: el día actual (medido) y los días pronosticados
  barras = computed<BarraDia[]>(() => {
    const e = this.estacion();
    if (!e) return [];
    const hoy: BarraDia = { etiqueta: 'Hoy', valor: e.ultimoValor, categoria: e.categoriaUltimoValor, observado: true,
      detalle: `Medido el ${fechaLarga(e.fechaReferencia)}` };
    return [hoy, ...this.proximosSel().map((p) => ({
      etiqueta: this.etiquetaDia(p), valor: p.valor, categoria: p.categoriaInca, observado: false,
      detalle: `${fechaLarga(p.fechaObjetivo)} · intervalo ${numero(p.limiteInferior, 0)} – ${numero(p.limiteSuperior, 0)}`,
    }))];
  });

  constructor(private estacionService: EstacionService, private prediccionService: PrediccionService,
              private asistenteService: AsistenteService) {}

  ngOnInit(): void {
    this.estacionService.getEstaciones().subscribe({
      next: (est) => {
        this.estaciones.set(est);
        if (est.length) this.seleccionar(est[0].codigo);
        est.slice(1).forEach((e) => this.pedirSerie(e));   // las demás se precargan: cambiar de estación es inmediato
        forkJoin(Object.fromEntries(est.map((e) => [e.codigo, this.prediccionService.getProximosDias(e.codigo)]))).subscribe({
          next: (p) => { this.proximos.set(p); this.cargando.set(false); this.mostrarSiEstaLista(); },
          error: (err) => { this.error.set(mensajeError(err)); this.cargando.set(false); this.mostrarSiEstaLista(); },
        });
      },
      error: (err) => { this.error.set(mensajeError(err)); this.cargando.set(false); },
    });
    this.prediccionService.getAlertas(undefined, 'vigente').subscribe({ next: (a) => this.alertas.set(a), error: () => this.alertas.set([]) });
  }

  // Filtros: el gráfico pasa a la primera estación visible del departamento o contaminante elegido
  cambiarDepartamento(d: string): void {
    this.filtroDepartamento.set(d);
    this.ajustarSeleccion(!!d);
  }

  cambiarContaminante(c: string): void {
    this.filtroContaminante.set(c);
    this.ajustarSeleccion(!!c);
  }

  private ajustarSeleccion(forzar: boolean): void {
    const v = this.visibles();
    if (!v.length) return;
    if (forzar || !v.some((e) => e.codigo === this.seleccionada())) this.seleccionar(v[0].codigo);
  }

  // Selecciona la estación del gráfico: últimos 14 días hasta el día actual
  seleccionar(codigo: string): void {
    if (codigo === this.seleccionada()) return;
    this.seleccionada.set(codigo);
    this.asistenteService.estacionEnPantalla.set(codigo);   // contexto para el asistente
    const e = this.estaciones().find((x) => x.codigo === codigo);
    if (!e) return;
    if (codigo in this.series()) this.mostrarSiEstaLista();
    else this.pedirSerie(e);
  }

  private pedirSerie(e: Estacion): void {
    this.estacionService.getSerieDiaria(e.codigo, sumarDias(e.fechaReferencia, -13), e.fechaReferencia).subscribe({
      next: (s) => { this.series.update((m) => ({ ...m, [e.codigo]: s })); this.mostrarSiEstaLista(); },
      error: () => { this.series.update((m) => ({ ...m, [e.codigo]: [] })); this.mostrarSiEstaLista(); },
    });
  }

  // Cambia el gráfico solo cuando la estación elegida tiene su serie y ya se cargaron los pronósticos
  private mostrarSiEstaLista(): void {
    const c = this.seleccionada();
    if (c && c in this.series() && !this.cargando()) this.mostrada.set(c);
  }

  etiquetaDia(p: Prediccion): string {
    return p.diasDesdeReferencia === 1 ? 'Mañana' : `+${p.diasDesdeReferencia} d`;
  }

  // Ancho de la barra INCA (0–150 → 0–100 %)
  anchoInca(v: number | null | undefined): number {
    return Math.min(100, Math.max(3, ((v ?? 0) / 150) * 100));
  }
}
