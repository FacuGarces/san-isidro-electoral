import { useEffect, useRef, useState } from "react";
import type { Eleccion } from "../../lib/api";
import { nombreCargo } from "../../lib/format";
import { ORDEN_CATEGORIAS } from "../../store/mapStore";
import { esClickEnPopover, PopoverPortal } from "./PopoverPortal";

interface Props {
  label?: string;
  elecciones: Eleccion[];
  value: string;
  onChange: (id: string) => void;
}

// Agrupa por AÑO (pedido explícito del usuario, antes agrupaba por categoría/cargo) y ordena
// cronológicamente dentro de cada grupo (PASO → General → Ballotage), con la prioridad de
// categoría (San Isidro primero) solo como desempate entre elecciones de la misma fecha.
function agrupar(elecciones: Eleccion[]): { anio: number; items: Eleccion[] }[] {
  const porAnio = new Map<number, Eleccion[]>();
  elecciones.forEach((e) => {
    const arr = porAnio.get(e.anio) ?? [];
    arr.push(e);
    porAnio.set(e.anio, arr);
  });
  const anios = [...porAnio.keys()].sort((a, b) => a - b);
  return anios.map((anio) => ({
    anio,
    items: [...(porAnio.get(anio) ?? [])].sort((a, b) => {
      const porFecha = a.fecha.localeCompare(b.fecha);
      if (porFecha !== 0) return porFecha;
      const ia = ORDEN_CATEGORIAS.indexOf(a.categoria_nombre);
      const ib = ORDEN_CATEGORIAS.indexOf(b.categoria_nombre);
      return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    }),
  }));
}

// Selector directo de UNA elección puntual, por su nombre real (p.ej. "PASO 2023 -
// Intendente", "Concejales 2025 - San Isidro (PARCIAL, no definitivo)") — reemplaza al viejo
// combo de Categoría+Etapa+escenario: el usuario elige la elección tal cual existe en la base,
// sin tener que reconstruirla a partir de dos selectores separados. Mismo patrón de combobox
// hecho a mano que `MetricSelect.tsx` (sin `<select>` nativo, con grupos y navegación por
// teclado). `nombreCargo()` saca el "/a" de género neutro ("Intendente/a" → "Intendente") solo
// para mostrar — el dato en `core.elecciones` se guarda como vino, esto es puramente de UI.
export function EleccionSelect({ label, elecciones, value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const grupos = agrupar(elecciones);
  const flat = grupos.flatMap((g) => g.items);
  const selected = flat.find((e) => e.id === value);

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
      {label && <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-ink-faint uppercase">{label}</div>}
      <div ref={rootRef} className="relative w-full">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={
            "flex w-full cursor-pointer items-center gap-2.5 rounded-2xl border bg-surface py-2.5 pr-3 pl-3.5 text-left shadow-elevation-sm transition-all duration-150 " +
            (open ? "border-brand-2 shadow-elevation-md" : "border-line-strong hover:border-brand-2 hover:shadow-elevation-md")
          }
        >
          <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink">{selected ? nombreCargo(selected.nombre) : "Elegir elección…"}</span>
          <svg viewBox="0 0 24 24" className={"h-4 w-4 shrink-0 text-ink-faint transition-transform duration-150 " + (open ? "rotate-180" : "")} fill="none" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="m6 9 6 6 6-6" />
          </svg>
        </button>

        <PopoverPortal anchorRef={rootRef} open={open} minWidth={304}>
          <ul role="listbox" className="max-h-80 w-full overflow-auto rounded-2xl border border-line bg-surface p-1.5 shadow-elevation-xl">
            {grupos.map((g) => (
              <li key={g.anio}>
                <div className="px-2.5 pt-2 pb-1 text-[10px] font-semibold tracking-wide text-ink-faint uppercase">{g.anio}</div>
                <ul>
                  {g.items.map((e) => (
                    <li
                      key={e.id}
                      role="option"
                      aria-selected={e.id === value}
                      onClick={() => {
                        onChange(e.id);
                        setOpen(false);
                      }}
                      className={
                        "flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] font-medium transition-colors duration-100 " +
                        (e.id === value ? "bg-surface-2 font-semibold text-brand" : "text-ink hover:bg-surface-hover")
                      }
                    >
                      <span className="min-w-0 flex-1 truncate">{nombreCargo(e.nombre)}</span>
                      {e.id === value && (
                        <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-brand" fill="none" stroke="currentColor" strokeWidth="3">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m5 13 4 4L19 7" />
                        </svg>
                      )}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </PopoverPortal>
      </div>
    </div>
  );
}
