import { useState } from "react";
import type { CircuitoProperties, CircuitosGeoJSON } from "../../lib/api";
import { PARTY_HEX, PARTY_HEX_OTHER, metricValue, metricValueTotal, partyColor, swingColor, titleCase } from "../../lib/colors";
import { fmtNum } from "../../lib/format";
import { currentMetric, useMapStore } from "../../store/mapStore";

function subtitulo(metricKey: string, compareMode: boolean, nombreBase: string, nombreActual: string): string {
  const metric = currentMetric(metricKey);
  if (metric.kind === "winner") {
    return compareMode
      ? `Ordenado por swing de la fuerza que ganó cada circuito: ${nombreBase} → ${nombreActual}`
      : "Ordenado por margen de victoria: diferencia en puntos porcentuales entre el 1° y el 2°";
  }
  if (metric.kind === "part") {
    return compareMode
      ? `Ordenado por swing de participación: ${nombreBase} → ${nombreActual}`
      : "Ordenado de mayor a menor % de participación (votantes / electores)";
  }
  const fuerzaLabel = titleCase(metric.fuerza ?? "");
  if (metric.kind === "lista") {
    return `Ordenado de mayor a menor % dentro de la interna de ${fuerzaLabel} — entre paréntesis, el % sobre el total de votos del circuito`;
  }
  return compareMode
    ? `Ordenado por swing de ${fuerzaLabel}: ${nombreBase} → ${nombreActual}`
    : `Ordenado de mayor a menor % de votos a ${fuerzaLabel} (sobre votos positivos)`;
}

interface Props {
  data: CircuitosGeoJSON;
  nombreBase: string;
  nombreActual: string;
}

export function RankingList({ data, nombreBase, nombreActual }: Props) {
  const metricKey = useMapStore((s) => s.metricKey);
  const activeCircuito = useMapStore((s) => s.activeCircuito);
  const setActiveCircuito = useMapStore((s) => s.setActiveCircuito);
  const compareMode = false; // "comparar" se sacó de la UI (CompareCandidatesBanner, que lo usaba, se borró) — queda el literal para no tocar la lógica de abajo por si se retoma
  const metric = currentMetric(metricKey);
  const [ordenarPorImpacto, setOrdenarPorImpacto] = useState(false);

  const valor = (f: CircuitoProperties) => (metric.kind === "winner" ? f.diferencia_pct : metricValue(f, metric));

  const feats = data.features.map((f) => f.properties);
  const sorted = [...feats].sort((a, b) =>
    compareMode && ordenarPorImpacto
      ? Math.abs(valor(b)) * (b.electores ?? 0) - Math.abs(valor(a)) * (a.electores ?? 0)
      : valor(b) - valor(a)
  );
  const values = sorted.map(valor);
  const maxV = Math.max(...values);
  const maxAbs = Math.max(...values.map((v) => Math.abs(v)), 0.01);

  return (
    <div>
      <div className="mb-0.5 flex items-center justify-between">
        <h2 className="text-xs font-semibold tracking-wide text-ink-faint uppercase">Ranking</h2>
        {compareMode && (
          <div className="flex gap-0.5 rounded-lg border border-line bg-surface-2/60 p-0.5 text-[11px]">
            <button
              type="button"
              onClick={() => setOrdenarPorImpacto(false)}
              className={
                "cursor-pointer rounded-md px-2 py-1 font-semibold transition-colors " +
                (!ordenarPorImpacto ? "bg-surface text-brand shadow-elevation-xs" : "text-ink-faint hover:text-ink")
              }
            >
              % swing
            </button>
            <button
              type="button"
              onClick={() => setOrdenarPorImpacto(true)}
              title="swing × electores — dónde el movimiento pesó más en votos reales, no solo en %"
              className={
                "cursor-pointer rounded-md px-2 py-1 font-semibold transition-colors " +
                (ordenarPorImpacto ? "bg-surface text-brand shadow-elevation-xs" : "text-ink-faint hover:text-ink")
              }
            >
              impacto
            </button>
          </div>
        )}
      </div>
      <p className="mb-4 text-xs text-ink-faint">{subtitulo(metricKey, compareMode, nombreBase, nombreActual)}</p>
      {sorted.length === 0 && <p className="rounded-xl bg-surface-2/60 px-3 py-4 text-center text-xs text-ink-faint">Ningún circuito coincide con el filtro.</p>}
      <div>
        {sorted.map((f, i) => {
          const v = valor(f);
          const barColor = compareMode
            ? swingColor(v, maxAbs, false)
            : metric.kind === "winner"
              ? partyColor(f.ganador)
              : metric.kind === "part"
                ? "var(--color-teal)"
                : (PARTY_HEX[metric.fuerza ?? ""] ?? PARTY_HEX_OTHER);
          const width = compareMode ? (Math.abs(v) / maxAbs) * 100 : (v / maxV) * 100;
          const label = compareMode ? `${v > 0 ? "+" : ""}${v.toFixed(1)}pp` : metric.kind === "winner" ? `+${v.toFixed(1)} pts` : `${v.toFixed(1)}%`;
          const pctTotal = metric.kind === "lista" ? metricValueTotal(f, metric) : null;
          return (
            <div
              key={f.circuito_id}
              onClick={() => setActiveCircuito(f.circuito_id)}
              onMouseEnter={() => setActiveCircuito(f.circuito_id)}
              className={
                "grid cursor-pointer grid-cols-[24px_1fr_auto] items-center gap-2.5 rounded-xl px-2 py-1.5 text-[13px] transition-colors duration-100 " +
                (f.circuito_id === activeCircuito ? "bg-surface-2 shadow-elevation-xs" : "hover:bg-surface-hover")
              }
            >
              <span className="font-mono text-[11px] text-ink-faint">{i + 1}</span>
              <span>
                Circuito {f.circuito_id}
                {compareMode && f.cambio_ganador && <span className="ml-1.5 text-[10px] text-party-fit">cambió de ganador</span>}
                {ordenarPorImpacto && <span className="ml-1.5 font-mono text-[10px] text-ink-faint">{fmtNum(f.electores)} electores</span>}
                <div className="mt-0.5 h-1.5 overflow-hidden rounded bg-line">
                  <div className="h-full rounded" style={{ width: `${width}%`, background: barColor }} />
                </div>
              </span>
              <span className="flex min-w-13 items-center justify-end gap-1 text-right font-mono font-semibold" style={compareMode ? { color: barColor } : undefined}>
                {compareMode && (
                  <svg viewBox="0 0 24 24" className="h-3 w-3 shrink-0" fill="none" stroke="currentColor" strokeWidth="3.5">
                    {v >= 0 ? (
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0-6 6m6-6 6 6" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m0 0 6-6m-6 6-6-6" />
                    )}
                  </svg>
                )}
                {label}
                {pctTotal != null && <span className="ml-1 font-normal text-ink-faint">({pctTotal.toFixed(1)}% total)</span>}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
