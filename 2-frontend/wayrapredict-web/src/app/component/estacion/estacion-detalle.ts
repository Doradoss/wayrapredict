import { Component, computed, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Estacion } from '../../model/estacion';
import { MetricaModelo } from '../../model/metrica';
import { Prediccion } from '../../model/prediccion';
import { SerieDiaria } from '../../model/serie-diaria';
import { AsistenteService } from '../../service/asistente.service';
import { AvisoService } from '../../service/aviso.service';
import { EstacionService } from '../../service/estacion.service';
import { LoginService } from '../../service/login.service';
import { PrediccionService } from '../../service/prediccion.service';
import {
  claseCategoria, fechaHora, fechaLarga, gravedad, mensajeError, nombreContaminante, nombreOrigen, numero, relativo,
  sumarDias, unidad,
} from '../../util/formato';
import { GraficoSerie, PuntoObservado, PuntoPronostico } from '../shared/grafico-serie/grafico-serie';
import { Encabezado } from '../shared/encabezado/encabezado';

const DIAS_GRAFICO = 30;
const DIAS_HISTORIAL = 10;

// 5 · Detalle de estación: serie histórica, predicción, recomendaciones, verificación y desempeño del modelo
@Component({
  selector: 'app-estacion-detalle',
  imports: [Encabezado, GraficoSerie],
  templateUrl: './estacion-detalle.html',
  styleUrl: './estacion-detalle.css',
})
export class EstacionDetalle implements OnInit {
  estaciones = signal<Estacion[]>([]);
  codigo = signal('');
  serie = signal<SerieDiaria[]>([]);
  proximos = signal<Prediccion[]>([]);
  historial = signal<Prediccion[]>([]);
  metrica = signal<MetricaModelo | null>(null);
  departamento = signal('');
  error = signal('');
  verificando = signal<number | null>(null);

  cat = claseCategoria;
  cont = nombreContaminante;
  num = numero;
  rel = relativo;
  uni = unidad;
  origen = nombreOrigen;
  fh = fechaHora;
  fl = fechaLarga;

  departamentos = computed(() => [...new Set(this.estaciones().map((e) => e.departamento))]);
  estacionesDepto = computed(() => this.estaciones().filter((e) => !this.departamento() || e.departamento === this.departamento()));
  estacion = computed(() => this.estaciones().find((e) => e.codigo === this.codigo()) ?? null);

  observados = computed<PuntoObservado[]>(() =>
    this.serie().filter((d) => !d.posteriorAReferencia).map((d) => ({ fecha: d.fecha, valor: d.contaminante, origen: d.origenContaminante }))
  );
  pronostico = computed<PuntoPronostico[]>(() =>
    this.proximos().map((p) => ({ fecha: p.fechaObjetivo, valor: p.valor, inferior: p.limiteInferior, superior: p.limiteSuperior }))
  );

  // Día pronosticado con la categoría más grave; si todos son iguales, el más cercano (para las recomendaciones)
  diaCritico = computed(() => {
    const p = [...this.proximos()].sort(
      (a, b) => gravedad(b.categoriaInca) - gravedad(a.categoriaInca) || a.diasDesdeReferencia - b.diasDesdeReferencia
    );
    return p[0] ?? null;
  });
  // Una viñeta por oración de la recomendación del INCA
  recomendaciones = computed(() =>
    (this.diaCritico()?.recomendacion ?? '').split(/\.\s+/).map((t) => t.trim().replace(/\.$/, '')).filter((t) => t)
  );

  // Meteorología del día actual (o el último día con cada dato)
  meteo = computed(() => {
    const dias = this.serie().filter((d) => !d.posteriorAReferencia).reverse();
    const ultimo = <K extends keyof SerieDiaria>(campo: K, campoOrigen: K) => {
      const d = dias.find((x) => x[campo] !== null);
      return d ? { valor: d[campo] as number, origen: d[campoOrigen] as string, fecha: d.fecha } : null;
    };
    return [
      { nombre: 'Temperatura media', icono: '#i-temp', unidad: '°C', dato: ultimo('temperatura', 'origenTemperatura'), dec: 1 },
      { nombre: 'Humedad relativa', icono: '#i-drop', unidad: '%', dato: ultimo('humedadRelativa', 'origenHumedadRelativa'), dec: 0 },
      { nombre: 'Velocidad del viento', icono: '#i-wind', unidad: 'm/s', dato: ultimo('velocidadViento', 'origenVelocidadViento'), dec: 1 },
      { nombre: 'Precipitación', icono: '#i-rain', unidad: 'mm/día', dato: ultimo('precipitacion', 'origenPrecipitacion'), dec: 1 },
    ];
  });

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private estacionService: EstacionService,
    private prediccionService: PrediccionService,
    public loginService: LoginService,
    private aviso: AvisoService,
    private asistenteService: AsistenteService
  ) {}

  ngOnInit(): void {
    this.estacionService.getEstaciones().subscribe({
      next: (est) => {
        this.estaciones.set(est);
        this.route.paramMap.subscribe((pm) => {
          const c = pm.get('codigo');
          if (!c && est.length) {
            this.router.navigate(['/estacion', est[0].codigo], { replaceUrl: true });
            return;
          }
          if (c) this.cargar(c);
        });
      },
      error: (err) => this.error.set(mensajeError(err)),
    });
  }

  cambiarDepartamento(d: string): void {
    this.departamento.set(d);
    const primera = this.estacionesDepto()[0];
    if (primera && primera.codigo !== this.codigo()) this.irA(primera.codigo);
  }

  irA(codigo: string): void {
    this.router.navigate(['/estacion', codigo]);
  }

  private cargar(codigo: string): void {
    const e = this.estaciones().find((x) => x.codigo === codigo);
    if (!e) {
      this.error.set(`Estación no encontrada: ${codigo}`);
      return;
    }
    this.error.set('');
    this.codigo.set(codigo);
    this.asistenteService.estacionEnPantalla.set(codigo);   // contexto para el asistente
    this.departamento.set(e.departamento);
    const ref = e.fechaReferencia;
    this.estacionService.getSerieDiaria(codigo, sumarDias(ref, -(DIAS_GRAFICO - 1)), ref).subscribe({ next: (s) => this.serie.set(s), error: () => this.serie.set([]) });
    this.prediccionService.getProximosDias(codigo).subscribe({ next: (p) => this.proximos.set(p), error: () => this.proximos.set([]) });
    this.prediccionService.getHistorial(codigo, sumarDias(ref, -(DIAS_HISTORIAL - 1)), ref).subscribe({
      next: (h) => this.historial.set([...h].reverse()),
      error: () => this.historial.set([]),
    });
    this.estacionService.getMetricasVigente(codigo).subscribe({ next: (m) => this.metrica.set(m[0] ?? null), error: () => this.metrica.set(null) });
  }

  // Usuario institucional: marca la predicción como verificada
  verificar(p: Prediccion): void {
    this.verificando.set(p.idPrediccion);
    this.prediccionService.verificar(p.idPrediccion).subscribe({
      next: (r) => {
        this.historial.update((h) => h.map((x) => (x.idPrediccion === r.idPrediccion ? { ...x, ...r, observado: x.observado, categoriaObservada: x.categoriaObservada } : x)));
        this.verificando.set(null);
        this.aviso.mostrar('Predicción verificada');
      },
      error: (err) => {
        this.verificando.set(null);
        this.aviso.mostrar(mensajeError(err), true);
      },
    });
  }

  etiquetaDia(p: Prediccion): string {
    return p.diasDesdeReferencia === 1 ? 'mañana' : `+${p.diasDesdeReferencia} días`;
  }
}
