import { Component, effect, ElementRef, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { AyudaDestinoService } from '../../service/ayuda-destino.service';
import { Encabezado } from '../shared/encabezado/encabezado';

// 9 · Nosotros y preguntas frecuentes
@Component({
  selector: 'app-ayuda',
  imports: [Encabezado],
  template: `
    <div class="view">
      <app-encabezado eyebrow="Nosotros" titulo="Nosotros y preguntas frecuentes" subtitulo="Quiénes somos, cómo funciona la plataforma y respuestas a dudas comunes"/>
      <div class="card destino" id="quienes-somos" [class.resaltado]="resaltado() === 'quienes-somos'">
        <h2>Quiénes somos</h2>
        <p class="texto">WayraPredict es un proyecto desarrollado por Daniel Bustamante Cabrera y Kevin Ayquipa Villar, estudiantes de la carrera de Ingeniería de Sistemas de Información. Su nombre une <i>wayra</i>, que significa «aire» en quechua, con <i>predict</i>, por la predicción de la calidad del aire. Su objetivo es pasar de una gestión reactiva a una gestión anticipada de la calidad del aire, combinando datos públicos de vigilancia ambiental, un modelo de predicción y un asistente que explica los resultados a cualquier persona.</p>
        <div class="equipo">
          <div class="miembro"><div class="avatar">DB</div><div><b>Daniel Bustamante Cabrera</b><small>Scrum Master · Researcher-ML · QA</small></div></div>
          <div class="miembro"><div class="avatar">KA</div><div><b>Kevin Ayquipa Villar</b><small>Project Manager · Architecture Owner · Developer</small></div></div>
        </div>
      </div>

      <div class="como mt">
        <span class="eyebrow">Cómo funciona</span>
        <h2>Del dato medido a la alerta, en tres pasos</h2>
        <p class="sub-title">Lo que hace la plataforma cada vez que se actualiza para mostrarte cómo estará el aire en los próximos días.</p>
      </div>
      <div class="pasos">
        @for (p of pasos; track p.titulo; let i = $index) {
          <div class="card paso" [style.animation-delay.ms]="i * 90">
            <div class="paso__num">{{ i + 1 }}</div>
            <h2>{{ p.titulo }}</h2>
            <p class="sub-title">{{ p.texto }}</p>
          </div>
        }
      </div>

      <div class="card mt destino" id="preguntas" [class.resaltado]="resaltado() === 'preguntas'">
        <h2>Preguntas frecuentes</h2>
        <div class="faqs">
          @for (f of faqs; track f.p; let i = $index) {
            <div class="faq destino" [id]="f.id" [class.abierta]="abiertas().has(i)" [class.resaltado]="resaltado() === f.id">
              <button type="button" class="faq__p" (click)="alternar(i)" [attr.aria-expanded]="abiertas().has(i)" [attr.aria-controls]="'faq-' + i">
                <span>{{ f.p }}</span><i class="faq__signo" aria-hidden="true"></i>
              </button>
              <div class="faq__r" [id]="'faq-' + i" role="region"><div>@for (parrafo of f.r; track $index) { <p>{{ parrafo }}</p> }</div></div>
            </div>
          }
        </div>
      </div>
    </div>
  `,
  styles: [`
    .texto { margin-top: 8px; line-height: 1.7; max-width: 900px; }
    .equipo { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 18px; }
    .miembro { display: flex; align-items: center; gap: 12px; }
    .miembro .avatar { width: 42px; height: 42px; font-size: 13px; }
    .miembro b { display: block; color: var(--heading); }
    .miembro small { color: var(--body-subtle); font-size: 12px; }
    .como { margin-bottom: 12px; animation: aparecer .4s ease both; }
    .como .eyebrow { display: block; margin-bottom: 4px; }
    .como h2 { font-size: 18px; }
    .pasos { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
    .paso { animation: aparecer .4s ease both; }
    .paso__num { width: 30px; height: 30px; border-radius: var(--radius); background: var(--brand-softer); color: var(--fg-brand); border: 1px solid var(--brand-soft);
      display: grid; place-items: center; font-weight: 900; margin-bottom: 12px; }
    .faqs { margin-top: 8px; }
    .faq { border-top: 1px solid var(--border); }
    .faq__p { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 0; text-align: left;
      color: var(--heading); font-weight: 700; font-size: 14px; transition: color .15s; }
    .faq__p:hover { color: var(--fg-brand); }
    .faq__signo { position: relative; width: 14px; height: 14px; flex: none; }
    .faq__signo::before, .faq__signo::after { content: ''; position: absolute; left: 0; right: 0; top: 6px; height: 2px; border-radius: 1px;
      background: var(--fg-brand); transition: transform .3s cubic-bezier(.3, 1.3, .6, 1); }
    .faq__signo::after { transform: rotate(90deg); }
    .abierta .faq__signo::after { transform: rotate(0deg); }
    .faq__r { display: grid; grid-template-rows: 0fr; transition: grid-template-rows .35s cubic-bezier(.4, 0, .2, 1); }
    .faq__r > div { overflow: hidden; }
    .destino { scroll-margin-top: 24px; }
    .faq.resaltado { animation: resaltar 1.8s ease; border-radius: var(--radius); }
    .card.resaltado { animation: resaltar-card 1.8s ease; }
    @keyframes resaltar { 0%, 40% { background: var(--brand-softer); box-shadow: 0 0 0 8px var(--brand-softer); } 100% { background: transparent; box-shadow: 0 0 0 8px transparent; } }
    @keyframes resaltar-card { 0%, 40% { border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-soft); } 100% { box-shadow: 0 0 0 3px transparent; } }
    .faq__r p + p { margin-top: -6px; }
    .faq__r p { padding: 0 0 14px; line-height: 1.6; opacity: 0; transform: translateY(-6px); transition: opacity .3s ease, transform .3s ease; }
    .abierta .faq__r { grid-template-rows: 1fr; }
    .abierta .faq__r p { opacity: 1; transform: none; transition-delay: .08s; }
    @media (max-width: 900px) { .pasos { grid-template-columns: 1fr; } }
  `],
})
export class Ayuda implements OnInit {
  // Preguntas abiertas (la primera, al entrar)
  abiertas = signal(new Set<number>([0]));
  readonly faqs: { id: string; p: string; r: string[] }[] = [
    { id: 'que-es', p: '¿Qué es WayraPredict?', r: ['Es una plataforma web que anticipa la calidad del aire en zonas con actividad minero-industrial de Junín, Pasco y Moquegua, y la explica en lenguaje sencillo.'] },
    { id: 'proyecto', p: '¿En qué consiste el proyecto?', r: [
      'WayraPredict es una plataforma de vigilancia predictiva de la calidad del aire desarrollada por Daniel Bustamante Cabrera y Kevin Ayquipa Villar. Su fin es ayudar a las autoridades ambientales y de salud, y a la población que vive cerca de operaciones mineras y metalúrgicas, a anticiparse a los días de mala calidad del aire para tomar precauciones a tiempo, en lugar de enterarse cuando ya ocurrieron.',
      'Vigila tres estaciones del OEFA ubicadas cerca de operaciones minero-industriales: La Oroya (Junín), donde se pronostica el dióxido de azufre (SO₂) por la actividad de la fundición; Huaraucaca (Pasco) e Ilo-Pacocha (Moquegua), donde se pronostica el material particulado PM10.',
      'Cada día muestra la predicción de los próximos días, su categoría según el INCA, las alertas y recomendaciones, y permite que el personal de instituciones públicas verifique las predicciones pasadas.',
    ] },
    { id: 'modelo', p: '¿Cómo funciona el modelo de predicción?', r: [
      'Se usa un modelo híbrido Prophet-LSTM que estima el promedio diario del contaminante de 1 a 3 días hacia adelante.',
      'Prophet aprende la tendencia y los ciclos de la serie (por ejemplo, las diferencias entre días de la semana y entre épocas del año). Una red neuronal LSTM aprende de lo ocurrido en los días anteriores, incluida la meteorología de la estación (temperatura, humedad, viento y lluvia), y corrige lo que Prophet no explica. La predicción final combina ambos.',
      'Cada predicción se acompaña de un intervalo de incertidumbre. El modelo se evaluó con datos que no se usaron para entrenarlo, comparándolo con modelos más simples; su error (RMSE, MAE y R²) se muestra en la pantalla de cada estación.',
    ] },
    { id: 'inca', p: '¿Qué es el INCA?', r: [
      'Es el Índice de Calidad del Aire del Ministerio del Ambiente (MINAM). Se calcula dividiendo la concentración promedio de 24 horas entre el Estándar de Calidad Ambiental (ECA-Aire) de 24 horas y multiplicando por 100. Los ECA-Aire de 24 horas son 250 µg/m³ para el SO₂ y 100 µg/m³ para el PM10.',
      'Categorías: Buena (0 a 50), Moderada (51 a 100), Mala (más de 100, es decir, sobre el ECA-Aire) y Umbral de cuidado (sobre el Valor Umbral del Estado de Cuidado, VUEC). Cada categoría tiene recomendaciones para la población, que la plataforma muestra junto a la predicción.',
    ] },
    { id: 'datos', p: '¿De dónde vienen los datos?', r: ['De la red de vigilancia de la calidad del aire del OEFA. Cuando una estación no tiene un dato meteorológico, se completa con fuentes meteorológicas externas, y la plataforma indica el origen de cada valor.'] },
    { id: 'colores', p: '¿Qué significan los colores?', r: ['Siguen el INCA: verde (buena), amarillo (moderada), anaranjado (mala) y rojo (umbral de cuidado).'] },
    { id: 'confianza', p: '¿Qué tan confiables son las predicciones?', r: ['Son estimaciones de un modelo, no mediciones. Por eso cada predicción se muestra con un intervalo de incertidumbre, y la pantalla de cada estación muestra el error del modelo (RMSE, MAE y R²).'] },
    { id: 'cuenta', p: '¿Necesito una cuenta?', r: ['No. La ciudadanía puede consultar todo sin registrarse. Las cuentas son para personal de instituciones públicas (correo .gob.pe) y deben ser aprobadas por el equipo de WayraPredict.'] },
    { id: 'verificado', p: '¿Qué significa «Verificado por autoridad»?', r: ['Que un usuario institucional revisó ese día pasado en la plataforma y dejó constancia de su verificación.'] },
    { id: 'contacto', p: '¿Cómo me comunico con el equipo?', r: ['Escríbenos a wayrapredict@gmail.com.'] },
  ];
  resaltado = signal<string | null>(null);
  private host = inject(ElementRef<HTMLElement>);
  private route = inject(ActivatedRoute);

  constructor() {
    // Clic en un enlace del pie (también si ya estás en esta pantalla)
    const destino = inject(AyudaDestinoService).destino;
    effect(() => {
      const d = destino();
      if (d) this.ir(d.id);
    });
  }

  ngOnInit(): void {
    // Enlace directo (por ejemplo, abierto en otra pestaña): /ayuda?ir=inca
    const id = this.route.snapshot.queryParamMap.get('ir');
    if (id) this.ir(id);
  }

  // Abre solo esa pregunta (si lo es), la desplaza a la vista y la resalta un momento
  ir(id: string): void {
    const i = this.faqs.findIndex((f) => f.id === id);
    if (i >= 0) this.abiertas.set(new Set([i]));
    this.resaltado.set(null);
    setTimeout(() => {
      const el = this.host.nativeElement.querySelector('#' + id) as HTMLElement | null;
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: i >= 0 ? 'center' : 'start' });
      this.resaltado.set(id);
    }, 80);
  }

  alternar(i: number): void {
    this.abiertas.update((s) => {
      const n = new Set(s);
      if (n.has(i)) n.delete(i); else n.add(i);
      return n;
    });
  }
  readonly pasos = [
    { titulo: 'Datos', texto: 'Se cargan los registros de vigilancia de la calidad del aire y la meteorología de las estaciones.' },
    { titulo: 'Predicción', texto: 'El modelo híbrido Prophet-LSTM estima los promedios diarios de los próximos días con un intervalo de incertidumbre.' },
    { titulo: 'Semáforo y alertas', texto: 'Cada predicción se clasifica según el INCA; las de categoría Moderada o superior se muestran como alertas.' },
  ];
}
