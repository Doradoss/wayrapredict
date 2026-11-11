// GET /api/libre/categorias-inca: leyenda del semáforo
export interface CategoriaInca {
  idCategoria: number;
  nombre: string;
  colorHex: string;
  incaMin: number | null;
  incaMax: number | null;
  recomendacion: string;
}
