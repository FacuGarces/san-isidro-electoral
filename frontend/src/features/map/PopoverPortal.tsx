import { useLayoutEffect, useState, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

interface Rect {
  top: number;
  left: number;
  width: number;
}

interface Props {
  anchorRef: RefObject<HTMLElement | null>;
  open: boolean;
  children: ReactNode;
  minWidth?: number;
}

// Los combobox hechos a mano (MetricSelect, EleccionSelect) abren un popover con
// `position: absolute` — eso se corta apenas el ancestro más cercano tiene `overflow-hidden`
// (que este layout usa a propósito para los bordes redondeados de cada marco, ver
// "integración estructural" en CLAUDE.md). Portal a `document.body` con `position: fixed`
// siguiendo el rect del botón evita el corte sin tener que sacarle `overflow-hidden` a los
// marcos — el bug real que reportó el usuario ("el dropdown está roto" en el selector de
// elecciones, arriba de todo en un marco bajito) era exactamente este.
export function PopoverPortal({ anchorRef, open, children, minWidth }: Props) {
  const [rect, setRect] = useState<Rect | null>(null);

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) {
      setRect(null);
      return;
    }
    function update() {
      const r = anchorRef.current?.getBoundingClientRect();
      if (r) setRect({ top: r.bottom + 6, left: r.left, width: r.width });
    }
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open, anchorRef]);

  if (!open || !rect) return null;

  return createPortal(
    <div data-popover-portal style={{ position: "fixed", top: rect.top, left: rect.left, width: Math.max(rect.width, minWidth ?? 0), zIndex: 100 }}>
      {children}
    </div>,
    document.body
  );
}

// El click-afuera-cierra de cada combobox chequea `rootRef.contains(target)` — pero el popover
// ahora vive fuera de `rootRef` en el DOM (está en document.body vía portal), así que un click
// DENTRO del popover se leería como "afuera" y lo cerraría antes de que el onClick de la opción
// llegue a disparar. Esta función se usa en el listener de mousedown de cada combobox además del
// chequeo de rootRef.
export function esClickEnPopover(target: EventTarget | null): boolean {
  return target instanceof Element && !!target.closest("[data-popover-portal]");
}
