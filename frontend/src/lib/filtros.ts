import type { CircuitoProperties } from "./api";
import type { FiltroCircuitos } from "../store/mapStore";

// En modo comparación `participacion_pct` ya significa swing (ver comentario en
// comparacion.py) — el filtro no necesita saberlo, solo compara contra el mismo campo que ya
// muestra el resto de la UI para participación.
export function circuitoPasaFiltro(props: CircuitoProperties, filtro: FiltroCircuitos): boolean {
  const busqueda = filtro.busqueda.trim().toLowerCase();
  if (busqueda && !props.circuito_id.toLowerCase().includes(busqueda)) return false;
  const filtraPorParticipacion = filtro.participacionMin != null || filtro.participacionMax != null;
  if (filtraPorParticipacion) {
    // Fuente parcial sin participación (ver CircuitoProperties): no podemos confirmar que
    // esté dentro del rango pedido, así que no matchea — mejor excluirlo que asumir que sí.
    if (props.participacion_pct == null) return false;
    if (filtro.participacionMin != null && props.participacion_pct < filtro.participacionMin) return false;
    if (filtro.participacionMax != null && props.participacion_pct > filtro.participacionMax) return false;
  }
  return true;
}
