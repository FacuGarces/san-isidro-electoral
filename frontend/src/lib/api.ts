// En dev, "/api/v1" pasa por el proxy de Vite (vite.config.ts) hacia el backend local. En el
// build de producción para GitHub Pages, el frontend se sirve desde un origen distinto al
// backend (Render) — VITE_API_BASE (seteado en el workflow de deploy) apunta a la URL completa
// del backend en ese caso; si no está seteada, cae al comportamiento relativo de siempre.
const API_BASE = `${import.meta.env.VITE_API_BASE ?? ""}/api/v1`;

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export interface Eleccion {
  id: string;
  nombre: string;
  tipo: string;
  ambito: string;
  fecha: string;
  anio: number;
  categoria_nombre: string;
  fuente: string;
  eleccion_comparable_id: string | null;
}

export interface Candidato {
  nombre: string;
  foto: string | null;
}

export interface ListaDetalle {
  nombre: string;
  votos: number;
  pct: number | null; // % DENTRO de su fuerza (de la interna), no del total del circuito
  pct_total: number | null; // % sobre el total de votos positivos del circuito
  candidato?: Candidato | null;
}

export interface FuerzaDetalle {
  fuerza: string;
  votos: number | null; // null si la fuente solo trae % (ver CircuitoProperties)
  pct: number; // en modo comparación: swing en puntos porcentuales, no % absoluto
  listas: ListaDetalle[];
  candidato?: Candidato | null;
  pct_actual?: number; // solo en modo comparación
  pct_base?: number; // solo en modo comparación
}

export interface CircuitoProperties {
  circuito_id: string;
  ganador: string;
  // null cuando la fuente es parcial/no definitiva (p.ej. una app cuyo backend ya no está
  // online, transcripta a mano) — nunca asumir que estos vienen siempre completos.
  mesas: number | null;
  electores: number | null;
  votantes: number | null;
  positivos: number | null;
  blanco: number | null;
  nulos: number | null;
  participacion_pct: number | null; // en modo comparación: swing de participación
  diferencia_pct: number; // en modo comparación: swing de la fuerza ganadora actual
  detalle: FuerzaDetalle[];
  candidato_ganador?: Candidato | null;
  ganador_base?: string; // solo en modo comparación
  cambio_ganador?: boolean; // solo en modo comparación
  candidato_actual?: Candidato | null; // solo en modo comparación
  candidato_base?: Candidato | null; // solo en modo comparación
  participacion_actual?: number; // solo en modo comparación
  participacion_base?: number; // solo en modo comparación
  // Solo en modo Versus cross-elección (VersusPanel.tsx): valores ya resueltos de cada lado del
  // versus, precalculados antes de llegar a MapView porque A y B pueden venir de elecciones
  // (fetches) distintas — MapView ya no puede derivarlos de un único `properties` con
  // currentMetric(key).
  versus_a?: number;
  versus_b?: number;
}

export interface CandidatoPasoResumen {
  nombre: string; // nombre de la lista/interna (slogan)
  votos: number;
  pct_fuerza: number | null; // % dentro de la propia fuerza, no del total
  candidato: Candidato | null;
}

export interface FuerzaResumen {
  fuerza: string;
  pct_actual: number | null; // null si la fuerza no compitió en Generales
  pct_base: number | null; // null si no compitió en la PASO
  swing_pct: number | null;
  candidato_actual: Candidato | null;
  candidatos_base: CandidatoPasoResumen[]; // 1 o más — más de 1 = hubo interna
}

export interface ComparacionResumen {
  fuerzas: FuerzaResumen[];
}

export interface CircuitosGeoJSON {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: GeoJSON.Geometry;
    properties: CircuitoProperties;
  }>;
  resumen?: ComparacionResumen | null; // solo en modo comparación
}

export interface EstablecimientoFuerzaDetalle {
  fuerza: string;
  votos: number;
  pct: number | null;
  candidato?: Candidato | null;
}

export interface EstablecimientoProperties {
  establecimiento_id: string;
  nombre: string;
  direccion: string;
  validado: boolean;
  mesas: number;
  electores: number;
  circuito_id: string;
  // Voto por mesa (core.resultados_mesa) — null cuando la elección tiene el mapeo mesa→escuela
  // pero todavía no el voto agregado (ver docs/DATA_SOURCES.md, "Nivel mesa (escuela)").
  votantes: number | null;
  positivos: number | null;
  blanco: number | null;
  nulos: number | null;
  participacion_pct: number | null;
  ganador: string | null;
  candidato_ganador?: Candidato | null;
  detalle: EstablecimientoFuerzaDetalle[];
}

export interface EstablecimientosGeoJSON {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: EstablecimientoProperties;
  }>;
}

export const api = {
  elecciones: () => get<Eleccion[]>("/elecciones"),
  circuitos: (eleccionId: string) =>
    get<CircuitosGeoJSON>(`/mapa/circuitos?eleccion_id=${encodeURIComponent(eleccionId)}`),
  comparacion: (actualId: string, baseId: string) =>
    get<CircuitosGeoJSON>(`/mapa/comparacion?actual=${encodeURIComponent(actualId)}&base=${encodeURIComponent(baseId)}`),
  // Nivel mesa/escuela — hoy solo cargado para DIPUTADOS2025 (ver docs/DATA_SOURCES.md). La
  // mayoría de las elecciones devuelven una FeatureCollection vacía, no un 404: es una
  // respuesta válida ("esta elección no tiene nivel mesa"), no un error.
  establecimientos: (eleccionId: string) =>
    get<EstablecimientosGeoJSON>(`/mapa/establecimientos?eleccion_id=${encodeURIComponent(eleccionId)}`),
};
