import type { Candidato, CircuitosGeoJSON } from "../../lib/api";
import { partyColor, titleCase } from "../../lib/colors";
import { fmtNum, sumOrNull } from "../../lib/format";
import { CandidateAvatar } from "./CandidateAvatar";

interface Props {
  data: CircuitosGeoJSON;
  compareMode: boolean;
}

// Resumen ejecutivo siempre visible arriba del mapa. Vive embebido dentro del mismo marco que
// los controles (no es una tarjeta propia): una fila con divide-x, sin fondo ni sombra propios,
// para que se sienta parte de una sola superficie en vez de otra caja apilada.
export function KpiHeader({ data, compareMode }: Props) {
  const electores = sumOrNull(data.features.map((f) => f.properties.electores));
  const mesas = sumOrNull(data.features.map((f) => f.properties.mesas));

  let participacion: number | null = 0;
  let liderNombre = "?";
  let liderPct = 0;
  let liderCandidato: Candidato | null = null;
  let liderSwing: number | null = null;

  if (compareMode) {
    const totalElectores = electores || 1;
    participacion =
      data.features.reduce((a, f) => a + (f.properties.participacion_actual ?? 0) * (f.properties.electores ?? 0), 0) / totalElectores;
    const top = [...(data.resumen?.fuerzas ?? [])]
      .filter((f) => f.pct_actual != null)
      .sort((a, b) => b.pct_actual! - a.pct_actual!)[0];
    if (top) {
      liderNombre = top.fuerza;
      liderPct = top.pct_actual ?? 0;
      liderCandidato = top.candidato_actual;
      liderSwing = top.swing_pct;
    }
  } else {
    const votantes = sumOrNull(data.features.map((f) => f.properties.votantes));
    participacion = electores && votantes != null ? (votantes / electores) * 100 : null;

    const votosPorFuerza: Record<string, number> = {};
    const pctSumPorFuerza: Record<string, number> = {};
    const candidatoPorFuerza: Record<string, Candidato | null | undefined> = {};
    data.features.forEach((f) =>
      f.properties.detalle.forEach((d) => {
        votosPorFuerza[d.fuerza] = (votosPorFuerza[d.fuerza] ?? 0) + (d.votos ?? 0);
        pctSumPorFuerza[d.fuerza] = (pctSumPorFuerza[d.fuerza] ?? 0) + d.pct;
        candidatoPorFuerza[d.fuerza] = d.candidato;
      })
    );
    const totalVotos = Object.values(votosPorFuerza).reduce((a, b) => a + b, 0);
    // Sin conteo de votos (fuente parcial): no se puede rankear por votos reales, se aproxima
    // con el promedio simple de % entre circuitos (sin ponderar por electores, que tampoco
    // tenemos) — mejor una aproximación transparente que un "líder" en blanco.
    const top = totalVotos
      ? Object.entries(votosPorFuerza).sort((a, b) => b[1] - a[1])[0]
      : Object.entries(pctSumPorFuerza).sort((a, b) => b[1] - a[1])[0];
    if (top) {
      liderNombre = top[0];
      liderPct = totalVotos ? (top[1] / totalVotos) * 100 : top[1] / data.features.length;
      liderCandidato = candidatoPorFuerza[top[0]] ?? null;
    }
  }

  const cambios = compareMode ? data.features.filter((f) => f.properties.cambio_ganador).length : 0;

  return (
    <div className="flex flex-wrap items-center divide-x divide-line">
      <KpiItem icon={<UsersIcon />} label="Electores" value={fmtNum(electores)} />
      <KpiItem icon={<BallotIcon />} label="Mesas" value={fmtNum(mesas)} />
      <KpiItem icon={<PulseIcon />} label="Participación" value={participacion == null ? "—" : `${participacion.toFixed(1)}%`} />

      <div className="flex items-center gap-3 px-5 py-1 first:pl-0">
        <CandidateAvatar candidato={liderCandidato} size={34} ringColor={partyColor(liderNombre)} />
        <div className="min-w-0">
          <div className="truncate text-sm font-bold text-ink">{liderCandidato?.nombre ?? titleCase(liderNombre)}</div>
          <div className="truncate text-[11px] text-ink-muted">
            {liderPct.toFixed(1)}% lidera
            {compareMode && liderSwing != null ? ` · ${liderSwing > 0 ? "+" : ""}${liderSwing.toFixed(1)}pp` : ""}
          </div>
        </div>
      </div>

      {compareMode && <KpiItem icon={<SwapIcon />} label="Cambiaron de mano" value={String(cambios)} />}
    </div>
  );
}

function KpiItem({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="flex shrink-0 items-center gap-3 px-5 py-1 first:pl-0">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-brand-2">{icon}</span>
      <div>
        <div className="text-lg leading-none font-bold text-ink">{value}</div>
        <div className="mt-1 text-[11px] tracking-wide text-ink-muted uppercase">{label}</div>
      </div>
    </div>
  );
}

function UsersIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M9.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM20 21v-2a3.99 3.99 0 0 0-3-3.87M15 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}
function BallotIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 5h16v14H4V5Zm4 5 2.5 2.5L16 7" />
    </svg>
  );
}
function PulseIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12h4l2-7 4 14 2-7h6" />
    </svg>
  );
}
function SwapIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="m17 3 4 4-4 4M3 7h18M7 21l-4-4 4-4m-4 4h18" />
    </svg>
  );
}
