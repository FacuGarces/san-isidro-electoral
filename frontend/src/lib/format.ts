// Suma tolerante a null: si TODOS los valores vienen sin dato (fuente parcial, ver
// CircuitoProperties en lib/api.ts) devuelve null en vez de un 0 engañoso — el que llama
// decide cómo mostrar "sin dato" (normalmente "—").
export function sumOrNull(values: (number | null)[]): number | null {
  if (values.every((v) => v == null)) return null;
  return values.reduce((a: number, v) => a + (v ?? 0), 0);
}

export function fmtNum(v: number | null): string {
  return v == null ? "—" : v.toLocaleString("es-AR");
}

// El género neutro "/a" en nombres de cargo ("Intendente/a", "Presidente/a") viene así en
// `core.categorias`/`core.elecciones.nombre` — pedido explícito del usuario: no mostrarlo en la
// UI. Reemplazo literal (no un regex genérico de "/a") porque son los únicos 2 cargos con ese
// sufijo en este dataset — agregar acá si se carga una categoría nueva con el mismo patrón.
export function nombreCargo(s: string): string {
  return s.replace(/Intendente\/a/g, "Intendente").replace(/Presidente\/a/g, "Presidente");
}

// El backend devuelve las fotos de candidatos como ruta absoluta desde la raíz ("/candidatos/
// lanus.jpg", ver backend/app/core/candidatos.py) porque ahí no sabe bajo qué subpath se va a
// servir el frontend. En dev (BASE_URL="/") no cambia nada; en el build de GitHub Pages
// (proyecto, no user site) BASE_URL es "/<repo>/", así que hay que anteponerlo o la imagen
// rompe en producción aunque funcione en local.
export function resolveFotoUrl(foto: string): string {
  return import.meta.env.BASE_URL.replace(/\/$/, "") + foto;
}
