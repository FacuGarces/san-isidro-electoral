import { useEffect, useRef, useState } from "react";
import type { CircuitosGeoJSON } from "../../lib/api";
import { buildFuerzaRows, OptionRow, Swatch, type Row } from "./MetricSelect";
import { esClickEnPopover, PopoverPortal } from "./PopoverPortal";

interface Props {
  data: CircuitosGeoJSON;
  value: string;
  onChange: (key: string) => void;
  accentColor?: string;
}

// Selector de UN candidato (fuerza entera o lista/interna puntual) para el modo Versus — mismo
// combobox que `MetricSelect` pero sin las opciones "Ganador"/"Participación" (acá siempre se
// elige un candidato concreto de un lado del versus, nunca una métrica genérica).
export function CandidatoSelect({ data, value, onChange, accentColor }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const rows: Row[] = buildFuerzaRows(data);
  const selected = rows.find((r) => r.key === value) ?? rows[0];

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node) && !esClickEnPopover(e.target)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="min-w-0 flex-1">
      <div ref={rootRef} className="relative w-full">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
          style={accentColor ? { borderColor: open ? accentColor : undefined } : undefined}
          className={
            "flex w-full cursor-pointer items-center gap-2.5 rounded-2xl border bg-surface py-2.5 pr-3 pl-2.5 text-left shadow-elevation-sm transition-all duration-150 " +
            (open ? "shadow-elevation-md" : "border-line-strong hover:border-brand-2 hover:shadow-elevation-md")
          }
        >
          <Swatch kind={selected?.swatch ?? "winner"} candidato={selected?.candidato} />
          <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink">{selected?.label ?? "Elegir…"}</span>
          <svg viewBox="0 0 24 24" className={"h-4 w-4 shrink-0 text-ink-faint transition-transform duration-150 " + (open ? "rotate-180" : "")} fill="none" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="m6 9 6 6 6-6" />
          </svg>
        </button>

        <PopoverPortal anchorRef={rootRef} open={open} minWidth={240}>
          <ul role="listbox" className="max-h-72 w-full overflow-auto rounded-2xl border border-line bg-surface p-1.5 shadow-elevation-xl">
            {rows.map((row) => (
              <OptionRow key={row.key} row={row} active={row.key === value} highlighted={false} onClick={() => { onChange(row.key); setOpen(false); }} />
            ))}
          </ul>
        </PopoverPortal>
      </div>
    </div>
  );
}
