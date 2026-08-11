import type { Candidato, CircuitosGeoJSON, FuerzaDetalle } from "../../lib/api";
import { partyColor, titleCase } from "../../lib/colors";
import { fmtNum, sumOrNull } from "../../lib/format";
import { useMapStore } from "../../store/mapStore";
import { CandidateAvatar } from "./CandidateAvatar";

function aggregateAll(data: CircuitosGeoJSON): FuerzaDetalle[] {
  const agg: Record<string, number> = {};
  const pctSum: Record<string, number> = {};
  const nCircuitos: Record<string, number> = {};
  const aggListas: Record<string, Record<string, { votos: number; candidato?: Candidato | null }>> = {};
  const candidatoByFuerza: Record<string, Candidato | null | undefined> = {};
  data.features.forEach((f) =>
    f.properties.detalle.forEach((d) => {
      agg[d.fuerza] = (agg[d.fuerza] ?? 0) + (d.votos ?? 0);
      pctSum[d.fuerza] = (pctSum[d.fuerza] ?? 0) + d.pct;
      nCircuitos[d.fuerza] = (nCircuitos[d.fuerza] ?? 0) + 1;
      candidatoByFuerza[d.fuerza] = d.candidato;
      const listas = (aggListas[d.fuerza] ??= {});
      d.listas.forEach((l) => {
        const entry = (listas[l.nombre] ??= { votos: 0, candidato: l.candidato });
        entry.votos += l.votos;
      });
    })
  );
  const total = Object.values(agg).reduce((a, b) => a + b, 0);
  // Sin conteo de votos (fuente parcial, ver CircuitoProperties): "votos" queda en 0 para
  // todas por igual, así que el % no puede salir de ahí — se aproxima con el promedio simple
  // de % entre circuitos en su lugar.
  return Object.entries(agg)
    .map(([fuerza, votos]) => ({
      fuerza,
      votos: total ? votos : null,
      pct: total ? (votos / total) * 100 : pctSum[fuerza] / nCircuitos[fuerza],
      candidato: candidatoByFuerza[fuerza],
      listas: Object.entries(aggListas[fuerza] ?? {})
        .map(([nombre, entry]) => ({
          nombre,
          votos: entry.votos,
          pct: votos ? (entry.votos / votos) * 100 : null,
          // % sobre el total agregado de San Isidro (todas las fuerzas), no solo de su interna —
          // mismo criterio que `pct_total` a nivel de un circuito puntual (ver api.ts).
          pct_total: total ? (entry.votos / total) * 100 : null,
          candidato: entry.candidato,
        }))
        .sort((a, b) => b.votos - a.votos),
    }))
    .sort((a, b) => (b.votos ?? b.pct) - (a.votos ?? a.pct));
}

// En modo comparación no hay "votos" reales que sumar (el endpoint de swing no los expone,
// no son comparables 1:1 entre PASO y General). El agregado de San Isidro se arma como
// promedio de swing ponderado por electores de cada circuito, que es lo que corresponde
// cuando lo que se agrega son puntos porcentuales, no conteos. Se ordena por % actual (no por
// swing) para que quede consistente con la vista de un circuito individual — si no, la fuerza
// ganadora puede quedar afuera del top 8 por tener el mayor swing negativo (perdió más porque
// partía de más arriba).
function aggregateAllCompare(data: CircuitosGeoJSON): FuerzaDetalle[] {
  const swingSum: Record<string, number> = {};
  const actualSum: Record<string, number> = {};
  const weightByFuerza: Record<string, number> = {};
  const candidatoByFuerza: Record<string, Candidato | null | undefined> = {};
  data.features.forEach((f) => {
    const peso = f.properties.electores || 0;
    f.properties.detalle.forEach((d) => {
      swingSum[d.fuerza] = (swingSum[d.fuerza] ?? 0) + d.pct * peso;
      actualSum[d.fuerza] = (actualSum[d.fuerza] ?? 0) + (d.pct_actual ?? 0) * peso;
      weightByFuerza[d.fuerza] = (weightByFuerza[d.fuerza] ?? 0) + peso;
      candidatoByFuerza[d.fuerza] = d.candidato;
    });
  });
  return Object.entries(swingSum)
    .map(([fuerza, sum]) => ({
      fuerza,
      votos: 0,
      pct: weightByFuerza[fuerza] ? sum / weightByFuerza[fuerza] : 0,
      pct_actual: weightByFuerza[fuerza] ? actualSum[fuerza] / weightByFuerza[fuerza] : 0,
      candidato: candidatoByFuerza[fuerza],
      listas: [],
    }))
    .sort((a, b) => (b.pct_actual ?? 0) - (a.pct_actual ?? 0));
}

interface Props {
  data: CircuitosGeoJSON;
  // Cuando hay un filtro activo en el panel Circuitos, el agregado ("San Isidro, N circuitos")
  // tiene que reflejar solo los que matchean — pero el circuito puntual (activeCircuito, que se
  // puede setear desde un hover en el mapa aunque esté fuera del filtro) siempre se busca en
  // `data` completo, nunca en el filtrado, para que el hover no deje de responder.
  filteredData?: CircuitosGeoJSON;
}

export function DetailPanel({ data, filteredData = data }: Props) {
  const activeCircuito = useMapStore((s) => s.activeCircuito);
  const compareMode = false; // "comparar" se sacó de la UI (CompareCandidatesBanner, que lo usaba, se borró) — queda el literal para no tocar la lógica de abajo por si se retoma

  const feature = activeCircuito ? data.features.find((f) => f.properties.circuito_id === activeCircuito) : null;
  const props = feature?.properties;
  const agregado = filteredData;

  const detalle = props ? props.detalle : compareMode ? aggregateAllCompare(agregado) : aggregateAll(agregado);
  const mesasVal = props ? props.mesas : sumOrNull(agregado.features.map((f) => f.properties.mesas));
  const electoresVal = props ? props.electores : sumOrNull(agregado.features.map((f) => f.properties.electores));
  const participacionVal: number | null = props
    ? props.participacion_pct
    : compareMode
      ? (() => {
          const totalElectores = agregado.features.reduce((a, f) => a + (f.properties.electores ?? 0), 0);
          const sum = agregado.features.reduce((a, f) => a + (f.properties.participacion_pct ?? 0) * (f.properties.electores ?? 0), 0);
          return totalElectores ? sum / totalElectores : 0;
        })()
      : (() => {
          const votantes = sumOrNull(agregado.features.map((f) => f.properties.votantes));
          const totalElectores = sumOrNull(agregado.features.map((f) => f.properties.electores));
          return totalElectores && votantes != null ? (votantes / totalElectores) * 100 : null;
        })();

  const signed = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;

  return (
    <div className="mt-6 border-t border-line pt-5">
      <div className="text-[15px] font-bold text-ink">{props ? `Circuito ${props.circuito_id}` : `San Isidro (${agregado.features.length} circuitos)`}</div>
      <div className="mb-3 flex items-center gap-2 text-xs text-ink-muted">
        {props?.candidato_ganador && !compareMode && <CandidateAvatar candidato={props.candidato_ganador} size={20} ringColor={partyColor(props.ganador)} />}
        <span>
          {props
            ? compareMode
              ? `Ganó ${titleCase(props.ganador)}${props.cambio_ganador ? ` (antes ${titleCase(props.ganador_base ?? "?")})` : ""} · swing ${signed(props.diferencia_pct)}pp`
              : `Ganó ${titleCase(props.ganador)} · +${props.diferencia_pct.toFixed(1)} pts sobre el segundo`
            : compareMode
              ? "Promedio ponderado por electores"
              : "Total del partido"}
        </span>
      </div>
      <div className="my-3 grid grid-cols-3 gap-2">
        <Stat value={fmtNum(electoresVal)} label="Electores" />
        <Stat value={fmtNum(mesasVal)} label="Mesas" />
        <Stat
          value={participacionVal == null ? "—" : compareMode ? `${signed(participacionVal)}pp` : `${participacionVal.toFixed(1)}%`}
          label={compareMode ? "Particip. Δ" : "Particip."}
        />
      </div>
      <div>
        {detalle.slice(0, 8).map((d) => (
          <div key={d.fuerza}>
            <div className={"grid items-center gap-2 py-1 text-xs " + (compareMode ? "grid-cols-[22px_1fr_auto]" : "grid-cols-[22px_1fr_auto_auto]")}>
              {d.candidato ? (
                <CandidateAvatar candidato={d.candidato} size={22} ringColor={partyColor(d.fuerza)} />
              ) : (
                <span className="h-2 w-2 rounded-full" style={{ background: partyColor(d.fuerza) }} />
              )}
              <span className="truncate" title={d.candidato ? `${d.candidato.nombre} — ${titleCase(d.fuerza)}` : titleCase(d.fuerza)}>
                {d.candidato ? d.candidato.nombre : titleCase(d.fuerza)}
              </span>
              {!compareMode && <span className="text-ink-muted">{fmtNum(d.votos)}</span>}
              <span
                className="flex min-w-12 items-center justify-end gap-1 text-right font-mono font-bold"
                style={compareMode ? { color: d.pct < 0 ? "var(--color-party-fit)" : "var(--color-teal)" } : undefined}
              >
                {compareMode && <SwingIcon up={d.pct >= 0} />}
                {compareMode ? `${signed(d.pct)}pp` : `${d.pct.toFixed(1)}%`}
              </span>
            </div>
            {d.listas.length > 1 && (
              <div className="mb-1 ml-[30px] border-l border-line pl-2.5">
                {d.listas.map((l) => (
                  <div key={l.nombre} className="grid grid-cols-[18px_1fr_auto_auto] items-center gap-2 py-1 text-[11px] text-ink-muted">
                    {l.candidato ? (
                      <CandidateAvatar candidato={l.candidato} size={18} />
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-line-strong" />
                    )}
                    <span className="truncate" title={l.candidato ? `${l.candidato.nombre} — ${titleCase(l.nombre)}` : titleCase(l.nombre)}>
                      {l.candidato ? l.candidato.nombre : titleCase(l.nombre)}
                    </span>
                    <span>{l.votos.toLocaleString("es-AR")}</span>
                    <span className="min-w-9 text-right font-mono" title="% dentro de la interna de su fuerza / % sobre el total de votos del distrito">
                      {l.pct?.toFixed(1) ?? "—"}%
                      <span className="ml-1 text-ink-faint">({l.pct_total?.toFixed(1) ?? "—"}% total)</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SwingIcon({ up }: { up: boolean }) {
  return (
    <svg viewBox="0 0 24 24" className="h-3 w-3 shrink-0" fill="none" stroke="currentColor" strokeWidth="3.5">
      {up ? (
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0-6 6m6-6 6 6" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m0 0 6-6m-6 6-6-6" />
      )}
    </svg>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-2 px-2.5 py-2">
      <div className="text-sm font-bold text-ink">{value}</div>
      <div className="text-[10px] tracking-wide text-ink-muted uppercase">{label}</div>
    </div>
  );
}
