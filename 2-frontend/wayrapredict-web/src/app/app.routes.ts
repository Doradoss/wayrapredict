import { Routes } from '@angular/router';
import { Admin } from './component/admin/admin';
import { Alertas } from './component/alertas/alertas';
import { Ayuda } from './component/ayuda/ayuda';
import { Dashboard } from './component/dashboard/dashboard';
import { EstacionDetalle } from './component/estacion/estacion-detalle';
import { AppLayout } from './component/layout/app-layout';
import { AuthLayout } from './component/layout/auth-layout';
import { Login } from './component/login/login';
import { Registro } from './component/registro/registro';
import { RegistroEnviado } from './component/registro/registro-enviado';
import { adminGuard, inicioGuard } from './guard/auth.guard';

// La raíz abre "Iniciar sesión" (como en la referencia), con el botón "Consultar sin cuenta"; si ya hay sesión,
// va al dashboard. Dashboard, estaciones, alertas y ayuda son públicos (no piden cuenta).
// Administración: solo el rol administrador. La verificación está en el detalle de estación (rol institucional).
export const routes: Routes = [
  { path: '', pathMatch: 'full', canActivate: [inicioGuard], children: [] },
  {
    path: '',
    component: AuthLayout,
    children: [
      { path: 'login', component: Login, title: 'Iniciar sesión · WayraPredict' },
      { path: 'registro', component: Registro, title: 'Solicitar cuenta · WayraPredict' },
      { path: 'registro-enviado', component: RegistroEnviado, title: 'Solicitud enviada · WayraPredict' },
    ],
  },
  {
    path: '',
    component: AppLayout,
    children: [
      { path: 'dashboard', component: Dashboard, title: 'Inicio · WayraPredict' },
      { path: 'estacion', component: EstacionDetalle, title: 'Estaciones · WayraPredict' },
      { path: 'estacion/:codigo', component: EstacionDetalle, title: 'Estación · WayraPredict' },
      { path: 'alertas', component: Alertas, title: 'Alertas · WayraPredict' },
      { path: 'admin', component: Admin, canActivate: [adminGuard], title: 'Administración · WayraPredict' },
      { path: 'ayuda', component: Ayuda, title: 'Ayuda · WayraPredict' },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
