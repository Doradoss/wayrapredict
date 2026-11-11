import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { LoginService } from '../service/login.service';

// Solo con sesión iniciada
export const authGuard: CanActivateFn = () => {
  const lService = inject(LoginService);
  const router = inject(Router);
  if (!lService.verificar()) {
    router.navigate(['/login']);
    return false;
  }
  return true;
};

// Raíz del sitio: con sesión va al dashboard; sin sesión, a "Iniciar sesión" (que ofrece consultar sin cuenta)
export const inicioGuard: CanActivateFn = () => {
  const lService = inject(LoginService);
  const router = inject(Router);
  return router.createUrlTree([lService.verificar() ? '/dashboard' : '/login']);
};

// Solo administradores (pantalla de Administración)
export const adminGuard: CanActivateFn = () => {
  const lService = inject(LoginService);
  const router = inject(Router);
  if (!lService.verificar()) {
    router.navigate(['/login']);
    return false;
  }
  if (!lService.esAdmin()) {
    router.navigate(['/dashboard']);
    return false;
  }
  return true;
};
