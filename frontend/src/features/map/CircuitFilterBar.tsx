import { filtroActivo, useMapStore } from "../../store/mapStore";

interface Props {
  compareMode: boolean;
  matchCount: number;
  totalCount: number;
}

// Filtro del panel Circuitos: buscador por número de circuito + rango de participación. Reduce
// qué circuitos aparecen en el ranking/agregado y se atenúan en el mapa (ver `idsFiltrados` en
// MapView) — nunca oculta el circuito del todo, así el mapa no queda con agujeros.
export function CircuitFilterBar({ compareMode, matchCount, totalCount }: Props) {
  const filtro = useMapStore((s) => s.filtro);
  const setFiltro = useMapStore((s) => s.setFiltro);
  const limpiarFiltro = useMapStore((s) => s.limpiarFiltro);
  const activo = filtroActivo(filtro);
  const labelParticipacion = compareMode ? "swing particip. (pp)" : "participación (%)";

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2.5">
      <div className="relative min-w-[8.5rem] flex-1">
        <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
        <input
          type="text"
          inputMode="numeric"
          value={filtro.busqueda}
          onChange={(e) => setFiltro({ busqueda: e.target.value })}
          placeholder="Buscar circuito…"
          aria-label="Buscar circuito"
          className="w-full rounded-xl border border-line bg-surface py-1.5 pr-2.5 pl-8 text-[12.5px] text-ink shadow-elevation-xs transition-colors outline-none placeholder:text-ink-faint focus:border-brand-2"
        />
      </div>

      <div className="flex shrink-0 items-center gap-1.5 text-[11px] text-ink-faint">
        <span className="whitespace-nowrap">{labelParticipacion}</span>
        <input
          type="number"
          step="0.1"
          value={filtro.participacionMin ?? ""}
          onChange={(e) => setFiltro({ participacionMin: e.target.value === "" ? null : Number(e.target.value) })}
          placeholder="min"
          aria-label={`${labelParticipacion} mínima`}
          className="w-14 rounded-lg border border-line bg-surface px-1.5 py-1 text-center text-[12px] text-ink shadow-elevation-xs outline-none focus:border-brand-2"
        />
        <span>–</span>
        <input
          type="number"
          step="0.1"
          value={filtro.participacionMax ?? ""}
          onChange={(e) => setFiltro({ participacionMax: e.target.value === "" ? null : Number(e.target.value) })}
          placeholder="max"
          aria-label={`${labelParticipacion} máxima`}
          className="w-14 rounded-lg border border-line bg-surface px-1.5 py-1 text-center text-[12px] text-ink shadow-elevation-xs outline-none focus:border-brand-2"
        />
      </div>

      {activo && (
        <button type="button" onClick={limpiarFiltro} className="shrink-0 cursor-pointer text-[11px] font-semibold text-brand hover:underline">
          Limpiar ({matchCount}/{totalCount})
        </button>
      )}
    </div>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="7" />
      <path strokeLinecap="round" d="m20 20-3.5-3.5" />
    </svg>
  );
}
