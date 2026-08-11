import { useEffect, useRef, useState } from "react";
import type { Candidato, CircuitosGeoJSON } from "../../lib/api";
import { PARTY_HEX, PARTY_HEX_OTHER, titleCase } from "../../lib/colors";
import { METRICS_FIJAS, metricKeyForLista, useMapStore } from "../../store/mapStore";
import { CandidateAvatar } from "./CandidateAvatar";
import { esClickEnPopover, PopoverPortal } from "./PopoverPortal";

interface Props {
  data: CircuitosGeoJSON;
}

export interface Row {
  key: string;
  label: string;
  swatch: "winner" | "part" | string; // "string" = hex de la fuerza
  // Fila de candidato individual dentro de una interna (hijo de una fuerza) — se indenta y
  // usa la foto/iniciales del candidato en vez del punto de color de la fuerza.
  candidato?: Candidato | null;
  indent?: boolean;
}

// Arma las filas "fuerza (+ sus listas anidadas, si tuvo interna)" a partir de los circuitos
// cargados — compartido entre `MetricSelect` (selector de una sola métrica) y `CandidatoSelect`
// (selector de UN candidato para el modo Versus, ver `VersusPanel.tsx`). Sacado a función propia
// para no duplicar esta lógica en los dos combobox.
export function buildFuerzaRows(data: CircuitosGeoJSON): Row[] {
  const mejorPct = new Map<string, number>();
  const listasPorFuerza = new Map<string, Map<string, { candidato: Candidato | null; bestPct: number }>>();
  data.features.forEach((f) =>
    f.properties.detalle.forEach((d) => {
      const v = d.pct_actual ?? d.pct;
      if (v > (mejorPct.get(d.fuerza) ?? -Infinity)) mejorPct.set(d.fuerza, v);
      if (d.listas.length > 1) {
        const porLista = listasPorFuerza.get(d.fuerza) ?? new Map<string, { candidato: Candidato | null; bestPct: number }>();
        d.listas.forEach((l) => {
          const lv = l.pct ?? -Infinity;
          const prev = porLista.get(l.nombre);
          if (!prev || lv > prev.bestPct) porLista.set(l.nombre, { candidato: l.candidato ?? null, bestPct: lv });
        });
        listasPorFuerza.set(d.fuerza, porLista);
      }
    })
  );
  const fuerzas = [...mejorPct.entries()].sort((a, b) => b[1] - a[1]).map(([fuerza]) => fuerza);

  const rows: Row[] = [];
  fuerzas.forEach((f) => {
    rows.push({ key: f, label: titleCase(f), swatch: PARTY_HEX[f] ?? PARTY_HEX_OTHER });
    const listas = listasPorFuerza.get(f);
    if (listas) {
      [...listas.entries()]
        .sort((a, b) => b[1].bestPct - a[1].bestPct)
        .forEach(([nombreLista, info]) => {
          rows.push({
            key: metricKeyForLista(f, nombreLista),
            label: info.candidato?.nombre ?? titleCase(nombreLista),
            swatch: PARTY_HEX[f] ?? PARTY_HEX_OTHER,
            candidato: info.candidato,
            indent: true,
          });
        });
    }
  });
  return rows;
}

const WINNER_ICON = (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 2 3 7l9 5 9-5-9-5Zm-9 10 9 5 9-5M3 17l9 5 9-5" />
  </svg>
);
const PART_ICON = (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9 9 0 1 0-9-9c0 2.5 1 4.5 2 6M12 21c-1-1.5-2-3.5-2-6a2 2 0 1 1 4 0c0 2.5-1 4.5-2 6Z" />
  </svg>
);

export function Swatch({ kind, candidato }: { kind: Row["swatch"]; candidato?: Candidato | null }) {
  if (candidato) return <CandidateAvatar candidato={candidato} size={22} />;
  if (kind === "winner") return <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-2 text-brand">{WINNER_ICON}</span>;
  if (kind === "part") return <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-2 text-teal-700" style={{ color: "var(--color-teal)" }}>{PART_ICON}</span>;
  return <span className="h-3 w-3 shrink-0 rounded-full ring-2 ring-white" style={{ background: kind, boxShadow: "0 0 0 1px var(--color-line-strong)" }} />;
}

// Combobox armado a mano (sin dependencia externa) para reemplazar el <select> nativo: el
// pedido explícito del usuario fue sacar las "cajitas que se ven muy IA" — un select de
// sistema operativo no deja mostrar el color de cada fuerza ni un estado de foco/hover propio.
export function MetricSelect({ data }: Props) {
  const metricKey = useMapStore((s) => s.metricKey);
  const setMetricKey = useMapStore((s) => s.setMetricKey);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const generales: Row[] = METRICS_FIJAS.map((m) => ({ key: m.key, label: m.label, swatch: m.kind }));
  const fuerzaRows: Row[] = buildFuerzaRows(data);
  const allRows = [...generales, ...fuerzaRows];
  const selected = allRows.find((r) => r.key === metricKey) ?? allRows[0];

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node) && !esClickEnPopover(e.target)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlight((h) => Math.min(h + 1, allRows.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlight((h) => Math.max(h - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const row = allRows[highlight];
        if (row) {
          setMetricKey(row.key);
          setOpen(false);
        }
      }
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, allRows, highlight, setMetricKey]);

  useEffect(() => {
    if (open) setHighlight(Math.max(allRows.findIndex((r) => r.key === metricKey), 0));
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (open) listRef.current?.children[highlight]?.scrollIntoView({ block: "nearest" });
  }, [highlight, open]);

  return (
    <div className="mb-4">
      <label className="mb-1.5 block text-[11px] font-semibold tracking-wide text-ink-faint uppercase">Ver en el mapa</label>
      <div ref={rootRef} className="relative w-full max-w-xs">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={
            "flex w-full cursor-pointer items-center gap-2.5 rounded-2xl border bg-surface py-2.5 pr-3 pl-2.5 text-left shadow-elevation-sm transition-all duration-150 " +
            (open ? "border-brand-2 shadow-elevation-md" : "border-line-strong hover:border-brand-2 hover:shadow-elevation-md")
          }
        >
          <Swatch kind={selected?.swatch ?? "winner"} candidato={selected?.candidato} />
          <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink">{selected?.label ?? "Ganador"}</span>
          <svg
            viewBox="0 0 24 24"
            className={"h-4 w-4 shrink-0 text-ink-faint transition-transform duration-150 " + (open ? "rotate-180" : "")}
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="m6 9 6 6 6-6" />
          </svg>
        </button>

        <PopoverPortal anchorRef={rootRef} open={open} minWidth={240}>
          <ul
            ref={listRef}
            role="listbox"
            className="max-h-72 w-full overflow-auto rounded-2xl border border-line bg-surface p-1.5 shadow-elevation-xl"
          >
            <li className="px-2.5 pt-1.5 pb-1 text-[10px] font-semibold tracking-wide text-ink-faint uppercase">General</li>
            {generales.map((row) => (
              <OptionRow key={row.key} row={row} active={row.key === metricKey} highlighted={allRows.indexOf(row) === highlight} onClick={() => { setMetricKey(row.key); setOpen(false); }} />
            ))}
            <li className="mx-2 my-1 border-t border-line" />
            <li className="px-2.5 pt-1 pb-1 text-[10px] font-semibold tracking-wide text-ink-faint uppercase">Fuerzas políticas</li>
            {fuerzaRows.map((row) => (
              <OptionRow key={row.key} row={row} active={row.key === metricKey} highlighted={allRows.indexOf(row) === highlight} onClick={() => { setMetricKey(row.key); setOpen(false); }} />
            ))}
          </ul>
        </PopoverPortal>
      </div>
    </div>
  );
}

export function OptionRow({ row, active, highlighted, onClick }: { row: Row; active: boolean; highlighted: boolean; onClick: () => void }) {
  return (
    <li
      role="option"
      aria-selected={active}
      onClick={onClick}
      className={
        "flex cursor-pointer items-center gap-2.5 rounded-xl py-2 text-[13px] font-medium transition-colors duration-100 " +
        (row.indent ? "pr-2.5 pl-7" : "px-2.5") +
        " " +
        (active ? "bg-surface-2 font-semibold text-brand" : highlighted ? "bg-surface-hover text-ink" : row.indent ? "text-ink-muted" : "text-ink")
      }
    >
      <Swatch kind={row.swatch} candidato={row.candidato} />
      <span className="min-w-0 flex-1 truncate">{row.label}</span>
      {active && (
        <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-brand" fill="none" stroke="currentColor" strokeWidth="3">
          <path strokeLinecap="round" strokeLinejoin="round" d="m5 13 4 4L19 7" />
        </svg>
      )}
    </li>
  );
}
