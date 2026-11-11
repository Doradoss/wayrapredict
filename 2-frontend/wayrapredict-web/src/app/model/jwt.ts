// POST /authenticate
export class JwtRequest {
  correo: string = '';
  password: string = '';
}

export interface JwtResponse {
  jwttoken: string;
  correo: string;
  rol: string;
  nombre: string;
  validezMs: number;
}
