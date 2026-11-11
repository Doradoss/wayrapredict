// Usuario de la plataforma (perfil y administración)
export interface Usuario {
  idUsuario: number;
  nombres: string;
  apellidos: string;
  correo: string;
  institucion: string | null;
  cargo: string | null;
  rol: string;              // administrador | usuario_institucional
  estado: string;           // pendiente | aprobado | rechazado
  fechaRegistro: string;
  aprobadoPor: string | null;
  fechaAprobacion: string | null;
}

// POST /api/libre/solicitar-cuenta
export interface SolicitudCuenta {
  nombres: string;
  apellidos: string;
  correo: string;
  password: string;
  institucion: string;
  cargo: string;
  aceptaTratamientoDatos: boolean;
}
