import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { LoginService } from '../service/login.service';

// Agrega "Authorization: Bearer <token>" a cada petición cuando hay sesión.
// Si un servicio protegido responde 401 (token vencido o cuenta revocada), cierra la sesión.
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const loginService = inject(LoginService);
  const token = loginService.token();
  const peticion =
    token && !req.url.endsWith('/authenticate') ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;
  return next(peticion).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && token && !req.url.includes('/api/libre/')) {
        loginService.logout();
      }
      return throwError(() => err);
    })
  );
};
