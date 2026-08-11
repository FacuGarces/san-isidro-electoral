import { create } from "zustand";

export type MetricKind = "winner" | "pct" | "part" | "lista";

export interface Metric {
  key: string;
  label: string;
  fuerza: string | null;
  // Solo si kind === "lista": nombre de la lista/interna seleccionada (candidato individual
  // dentro de su fuerza, p.ej. Lanús o Posse dentro de JUNTOS POR EL CAMBIO).
  lista: string | null;
  kind: MetricKind;
}

// Métricas fijas (no dependen de qué fuerzas trajo la respuesta). Las métricas por fuerza
// política se arman dinámicas en MetricSelect.tsx a partir de los datos cargados — no
// hardcodear acá una lista corta de partidos, la app tiene que servir para cualquiera de los
// que compitieron, no solo los 3 más grandes.
export const METRICS_FIJAS: Metric[] = [
  { key: "ganador", label: "Ganador", fuerza: null, lista: null, kind: "winner" },
  { key: "part", label: "Participación", fuerza: null, lista: null, kind: "part" },
];

// Codifica/decodifica la clave de una métrica de "candidato individual dentro de una interna"
// — MetricSelect arma la clave con esta función al construir sus filas anidadas, colors.ts /
// currentMetric() la decodifican para saber qué fuerza + qué lista mostrar. `lista` es
// `ListaDetalle.nombre` (el nombre de fantasía de la lista, único por fuerza en una elección),
// no el lista_numero — el frontend nunca recibe el número, solo el nombre ya resuelto.
const LISTA_PREFIX = "lista:";
export function metricKeyForLista(fuerza: string, lista: string): string {
  return `${LISTA_PREFIX}${encodeURIComponent(fuerza)}:${encodeURIComponent(lista)}`;
}

// "comparar" (2 elecciones completas enfrentadas por swing) se sacó a pedido explícito del
// usuario — el modo "versus" (2 candidatos puntuales de UNA elección, cabeza a cabeza en el
// mapa) es lo que en la práctica quería decir con "comparar". El backend (`comparacion.py`,
// `api.comparacion()`) sigue andando por si se retoma, pero ya no hay UI que lo dispare.
export type Modo = "ver" | "versus";

// Orden de categorías pensado para un asesor de LLA armando 2027: primero lo que se juega en
// San Isidro (Intendente/a es lo que de verdad importa, Concejales va en la misma boleta,
// Senadores da la referencia seccional), Presidente/a al final como contexto nacional — se usa
// solo para AGRUPAR el selector de elecciones, no como filtro (ver EleccionSelect.tsx).
export const ORDEN_CATEGORIAS = ["Intendente/a", "Concejales", "Senadores Provinciales (1ra Sección)", "Presidente/a"];

// Filtro del panel "Circuitos": reduce qué circuitos aparecen en el ranking (y se atenúan en el
// mapa), no qué elección se pide al backend — vive junto al resto del estado de UI del mapa.
export interface FiltroCircuitos {
  busqueda: string;
  participacionMin: number | null;
  participacionMax: number | null;
}

export const FILTRO_VACIO: FiltroCircuitos = { busqueda: "", participacionMin: null, participacionMax: null };

export function filtroActivo(f: FiltroCircuitos): boolean {
  return f.busqueda.trim() !== "" || f.participacionMin != null || f.participacionMax != null;
}

// Un ítem de un lado del Versus: una fuerza o lista puntual (`key`, misma codificación que
// `metricKey`) DENTRO de una elección puntual (`eleccionId`) — cada lado puede sumar más de uno
// (p.ej. "LLA Intendente PASO 2023" + "Ramón Lanús individual") para modelar escenarios de
// alianzas, pedido explícito del usuario. `id` es solo para la key de React (agregar/sacar filas).
export interface VersusEntry {
  id: string;
  eleccionId: string;
  key: string;
}

interface MapState {
  modo: Modo;
  // Selección directa por id de elección — nada de categoría+etapa intermedias. El usuario
  // elige la elección por su nombre real en `EleccionSelect`, no arma la combinación a través
  // de filtros.
  actualId: string;
  metricKey: string;
  // Modo "versus" (VersusPanel.tsx): 2 lados comparados cabeza a cabeza circuito por circuito,
  // cada lado es la SUMA de 1+ entradas (`VersusEntry`) — normalmente 1 sola, pero se puede
  // agregar más para sumar fuerzas/candidatos de elecciones distintas (escenario de alianza).
  // Arrays vacíos ([]) significa "todavía no personalizado" — VersusPanel arma un default de 1
  // entrada razonable (interna del líder si tiene y ambos lados parten de la misma elección, si
  // no las 2 fuerzas más votadas) sin necesidad de guardar ese default acá.
  versusA: VersusEntry[];
  versusB: VersusEntry[];
  activeCircuito: string | null;
  filtro: FiltroCircuitos;
  setModo: (m: Modo) => void;
  setActualId: (id: string) => void;
  setMetricKey: (key: string) => void;
  setVersusA: (entries: VersusEntry[]) => void;
  setVersusB: (entries: VersusEntry[]) => void;
  setActiveCircuito: (id: string | null) => void;
  setFiltro: (f: Partial<FiltroCircuitos>) => void;
  limpiarFiltro: () => void;
}

export const useMapStore = create<MapState>((set) => ({
  modo: "ver",
  actualId: "GENERALES2023_INTENDENTE",
  metricKey: "ganador",
  versusA: [],
  versusB: [],
  activeCircuito: null,
  filtro: FILTRO_VACIO,
  setModo: (m) => set({ modo: m, activeCircuito: null }),
  setActualId: (id) => set({ actualId: id, activeCircuito: null, versusA: [], versusB: [] }),
  setMetricKey: (key) => set({ metricKey: key }),
  setVersusA: (entries) => set({ versusA: entries, activeCircuito: null }),
  setVersusB: (entries) => set({ versusB: entries, activeCircuito: null }),
  setActiveCircuito: (id) => set({ activeCircuito: id }),
  setFiltro: (f) => set((st) => ({ filtro: { ...st.filtro, ...f } })),
  limpiarFiltro: () => set({ filtro: FILTRO_VACIO }),
}));

export function currentMetric(key: string): Metric {
  const fija = METRICS_FIJAS.find((m) => m.key === key);
  if (fija) return fija;
  if (key.startsWith(LISTA_PREFIX)) {
    const resto = key.slice(LISTA_PREFIX.length);
    const sep = resto.indexOf(":");
    if (sep !== -1) {
      const fuerza = decodeURIComponent(resto.slice(0, sep));
      const lista = decodeURIComponent(resto.slice(sep + 1));
      return { key, label: lista, fuerza, lista, kind: "lista" };
    }
  }
  return { key, label: key, fuerza: key, lista: null, kind: "pct" };
}
