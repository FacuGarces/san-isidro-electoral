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

interface MapState {
  modo: Modo;
  // Selección directa por id de elección — nada de categoría+etapa intermedias. El usuario
  // elige la elección por su nombre real en `EleccionSelect`, no arma la combinación a través
  // de filtros.
  actualId: string;
  metricKey: string;
  // Modo "versus" (VersusPanel.tsx): 2 candidatos (fuerza o lista puntual, mismas claves que
  // `metricKey`) comparados cabeza a cabeza circuito por circuito. Cada lado puede venir de una
  // elección DISTINTA — `versusAEleccionId`/`versusBEleccionId` (`null` = usa `actualId`, el
  // caso más común: comparar 2 candidatos de la elección que ya se está mirando). `versusAKey`/
  // `versusBKey` son relativos a la elección de SU PROPIO lado, no a `actualId`. Todo `null`
  // hasta que el usuario elige — VersusPanel arranca con un default razonable (interna del
  // líder si tiene y ambos lados son la misma elección, si no las 2 fuerzas más votadas) sin
  // necesidad de guardar ese default acá.
  versusAEleccionId: string | null;
  versusBEleccionId: string | null;
  versusAKey: string | null;
  versusBKey: string | null;
  activeCircuito: string | null;
  filtro: FiltroCircuitos;
  setModo: (m: Modo) => void;
  setActualId: (id: string) => void;
  setMetricKey: (key: string) => void;
  setVersusAEleccionId: (id: string | null) => void;
  setVersusBEleccionId: (id: string | null) => void;
  setVersusAKey: (key: string) => void;
  setVersusBKey: (key: string) => void;
  setActiveCircuito: (id: string | null) => void;
  setFiltro: (f: Partial<FiltroCircuitos>) => void;
  limpiarFiltro: () => void;
}

export const useMapStore = create<MapState>((set) => ({
  modo: "ver",
  actualId: "GENERALES2023_INTENDENTE",
  metricKey: "ganador",
  versusAEleccionId: null,
  versusBEleccionId: null,
  versusAKey: null,
  versusBKey: null,
  activeCircuito: null,
  filtro: FILTRO_VACIO,
  setModo: (m) => set({ modo: m, activeCircuito: null }),
  setActualId: (id) =>
    set({ actualId: id, activeCircuito: null, versusAEleccionId: null, versusBEleccionId: null, versusAKey: null, versusBKey: null }),
  setMetricKey: (key) => set({ metricKey: key }),
  // Cambiar la elección de un lado invalida la clave de candidato de ESE lado (una fuerza/lista
  // de la elección vieja no es válida para la nueva) pero no toca el otro lado.
  setVersusAEleccionId: (id) => set({ versusAEleccionId: id, versusAKey: null, activeCircuito: null }),
  setVersusBEleccionId: (id) => set({ versusBEleccionId: id, versusBKey: null, activeCircuito: null }),
  setVersusAKey: (key) => set({ versusAKey: key, activeCircuito: null }),
  setVersusBKey: (key) => set({ versusBKey: key, activeCircuito: null }),
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
