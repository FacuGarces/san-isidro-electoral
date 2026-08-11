import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CircuitosGeoJSON, type Eleccion } from "../../lib/api";
import { duoColor, metricValue, shade } from "../../lib/colors";
import { currentMetric, useMapStore } from "../../store/mapStore";
import { CandidateAvatar } from "./CandidateAvatar";
import { CandidatoSelect } from "./CandidatoSelect";
import { EleccionSelect } from "./EleccionSelect";
import { buildFuerzaRows, type Row } from "./MetricSelect";
import { MapView, type VersusConfig } from "./MapView";

interface Props {
  elecciones: Eleccion[];
}

// Elige un default interesante al entrar a Versus, cuando los 2 lados son la MISMA elección: si
// la fuerza líder tuvo interna, arranca comparando sus dos candidatos principales (p.ej. Lanús
// vs. Posse) — es exactamente el caso de uso que pidió el usuario. Si no hay interna, compara
// las 2 fuerzas más votadas.
function parPorDefecto(rows: Row[]): [string, string] {
  const primeraFuerzaIdx = rows.findIndex((r) => !r.indent);
  const hijo1 = rows[primeraFuerzaIdx + 1];
  const hijo2 = rows[primeraFuerzaIdx + 2];
  if (hijo1?.indent && hijo2?.indent) return [hijo1.key, hijo2.key];
  const topLevel = rows.filter((r) => !r.indent);
  return [topLevel[0]?.key ?? "", topLevel[1]?.key ?? ""];
}

// Default de un lado cuando los 2 lados son elecciones DISTINTAS: no hay "interna del líder"
// que tenga sentido comparar entre 2 elecciones separadas, así que cada lado arranca en su
// propia fuerza más votada.
function liderPorDefecto(rows: Row[]): string {
  return rows.find((r) => !r.indent)?.key ?? "";
}

// Comparación cabeza a cabeza entre 2 candidatos (fuerzas enteras o listas puntuales de una
// interna), circuito por circuito — cada lado puede ser de la MISMA elección o de 2 elecciones
// distintas (p.ej. "LLA Intendente PASO 2023" vs. "LLA Concejales 2025"), pedido explícito del
// usuario para no atarse a comparar dentro de una sola elección.
export function VersusPanel({ elecciones }: Props) {
  const actualId = useMapStore((s) => s.actualId);
  const versusAEleccionId = useMapStore((s) => s.versusAEleccionId);
  const versusBEleccionId = useMapStore((s) => s.versusBEleccionId);
  const versusAKey = useMapStore((s) => s.versusAKey);
  const versusBKey = useMapStore((s) => s.versusBKey);
  const setVersusAEleccionId = useMapStore((s) => s.setVersusAEleccionId);
  const setVersusBEleccionId = useMapStore((s) => s.setVersusBEleccionId);
  const setVersusAKey = useMapStore((s) => s.setVersusAKey);
  const setVersusBKey = useMapStore((s) => s.setVersusBKey);
  const activeCircuito = useMapStore((s) => s.activeCircuito);
  const setActiveCircuito = useMapStore((s) => s.setActiveCircuito);

  const eleccionAId = versusAEleccionId ?? actualId;
  const eleccionBId = versusBEleccionId ?? actualId;
  const mismaEleccion = eleccionAId === eleccionBId;

  // React Query dedupea por queryKey — si `eleccionAId` es la elección que ya trajo `data`
  // (el caso más común: comparar 2 candidatos de la elección que se está mirando), esto no
  // dispara un fetch nuevo, reusa la cache que ya llenó `MapPage`.
  const { data: dataA } = useQuery({
    queryKey: ["circuitos", eleccionAId],
    queryFn: () => api.circuitos(eleccionAId),
    enabled: !!eleccionAId,
  });
  const { data: dataB } = useQuery({
    queryKey: ["circuitos", eleccionBId],
    queryFn: () => api.circuitos(eleccionBId),
    enabled: !!eleccionBId,
  });

  const rowsA = useMemo(() => (dataA ? buildFuerzaRows(dataA) : []), [dataA]);
  const rowsB = useMemo(() => (dataB ? buildFuerzaRows(dataB) : []), [dataB]);

  const defaultA = useMemo(() => (mismaEleccion ? parPorDefecto(rowsA)[0] : liderPorDefecto(rowsA)), [rowsA, mismaEleccion]);
  const defaultB = useMemo(() => (mismaEleccion ? parPorDefecto(rowsB)[1] : liderPorDefecto(rowsB)), [rowsB, mismaEleccion]);

  const keyA = versusAKey ?? defaultA;
  const keyB = versusBKey ?? defaultB;
  const rowA = rowsA.find((r) => r.key === keyA);
  const rowB = rowsB.find((r) => r.key === keyB);

  const metricA = currentMetric(keyA);
  const metricB = currentMetric(keyB);

  let colorA = typeof rowA?.swatch === "string" ? rowA.swatch : "#8A8496";
  let colorB = typeof rowB?.swatch === "string" ? rowB.swatch : "#8A8496";
  // Misma fuerza (interna) → mismo hex de base. Se distinguen aclarando/oscureciendo uno,
  // nunca inventando un color sin relación con la marca.
  if (colorA === colorB) {
    colorA = shade(colorA, 0.18);
    colorB = shade(colorB, -0.28);
  }

  const versus: VersusConfig = {
    colorA,
    colorB,
    labelA: rowA?.label ?? "A",
    labelB: rowB?.label ?? "B",
  };

  // A y B pueden venir de fetches distintos (elecciones distintas) — se cruzan por
  // `circuito_id`. En la práctica siempre son los mismos 10 circuitos de San Isidro, pero el
  // cruce por id (no por índice) lo hace correcto igual si algún día no coinciden del todo.
  const merged = useMemo(() => {
    if (!dataA || !dataB) return null;
    const porIdB = new Map(dataB.features.map((f) => [f.properties.circuito_id, f]));
    const features = dataA.features
      .filter((f) => porIdB.has(f.properties.circuito_id))
      .map((f) => {
        const fb = porIdB.get(f.properties.circuito_id)!;
        return {
          ...f,
          properties: {
            ...f.properties,
            versus_a: metricValue(f.properties, metricA),
            versus_b: metricValue(fb.properties, metricB),
          },
        };
      });
    return { ...dataA, features } as CircuitosGeoJSON;
  }, [dataA, dataB, metricA, metricB]);

  if (!dataA || !dataB || !merged) {
    return <div className="py-10 text-center text-sm text-ink-muted">Cargando…</div>;
  }

  const pctA = merged.features.reduce((acc, f) => acc + (f.properties.versus_a ?? 0), 0) / (merged.features.length || 1);
  const pctB = merged.features.reduce((acc, f) => acc + (f.properties.versus_b ?? 0), 0) / (merged.features.length || 1);
  const circuitosA = merged.features.filter((f) => (f.properties.versus_a ?? 0) >= (f.properties.versus_b ?? 0)).length;
  const circuitosB = merged.features.length - circuitosA;

  const sorted = [...merged.features].sort(
    (x, y) =>
      Math.abs((y.properties.versus_a ?? 0) - (y.properties.versus_b ?? 0)) - Math.abs((x.properties.versus_a ?? 0) - (x.properties.versus_b ?? 0))
  );
  const maxAbs = Math.max(...sorted.map((f) => Math.abs((f.properties.versus_a ?? 0) - (f.properties.versus_b ?? 0))), 0.01);

  return (
    <div>
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-start">
        <div className="min-w-0 flex-1 space-y-2">
          <EleccionSelect elecciones={elecciones} value={eleccionAId} onChange={setVersusAEleccionId} />
          <CandidatoSelect data={dataA} value={keyA} onChange={setVersusAKey} accentColor={colorA} />
        </div>
        <span className="shrink-0 self-center pt-8 text-[11px] font-bold tracking-wide text-ink-faint sm:pt-16">VS</span>
        <div className="min-w-0 flex-1 space-y-2">
          <EleccionSelect elecciones={elecciones} value={eleccionBId} onChange={setVersusBEleccionId} />
          <CandidatoSelect data={dataB} value={keyB} onChange={setVersusBKey} accentColor={colorB} />
        </div>
      </div>

      {!mismaEleccion && (
        <p className="mt-2 text-[11px] text-ink-faint">
          Comparando elecciones distintas: los % de cada lado son sobre el total de su propia elección, no directamente comparables como
          "swing" — el mapa muestra qué lado saca más % en cada circuito.
        </p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3">
        <ResumenCandidato label={versus.labelA} pct={pctA} color={colorA} candidato={rowA?.candidato} circuitosGanados={circuitosA} />
        <ResumenCandidato label={versus.labelB} pct={pctB} color={colorB} candidato={rowB?.candidato} circuitosGanados={circuitosB} align="right" />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div>
          <MapView data={merged} onHover={setActiveCircuito} nombreBase="" versus={versus} />
          <div className="mt-3 flex items-center gap-2.5">
            <span className="truncate text-xs font-semibold" style={{ color: colorA, maxWidth: "8rem" }}>{versus.labelA}</span>
            <div className="h-2.5 flex-1 rounded-md border border-line-strong" style={{ background: `linear-gradient(90deg, ${colorA}, #fff, ${colorB})` }} />
            <span className="truncate text-xs font-semibold" style={{ color: colorB, maxWidth: "8rem" }}>{versus.labelB}</span>
          </div>
        </div>

        <div>
          <h3 className="mb-0.5 text-xs font-semibold tracking-wide text-ink-faint uppercase">Circuitos</h3>
          <p className="mb-3 text-xs text-ink-faint">Ordenados por margen entre {versus.labelA} y {versus.labelB}</p>
          {sorted.map((f) => {
            const a = f.properties.versus_a ?? 0;
            const b = f.properties.versus_b ?? 0;
            const diff = a - b;
            // El color diluido (duoColor, mezclado con blanco cerca del empate) sirve para la
            // barra, pero NUNCA como color de texto — cerca de 0 se vuelve gris clarito sobre
            // fondo blanco y deja de leerse. El texto siempre usa el color sólido del candidato
            // que va ganando ese circuito (colorA/colorB a pleno), nunca la versión atenuada.
            const barColor = duoColor(diff, maxAbs, colorA, colorB, false);
            const textColor = diff >= 0 ? colorA : colorB;
            return (
              <div
                key={f.properties.circuito_id}
                onMouseEnter={() => setActiveCircuito(f.properties.circuito_id)}
                onMouseLeave={() => setActiveCircuito(null)}
                className={
                  "grid cursor-pointer grid-cols-[auto_1fr_auto] items-center gap-2.5 rounded-xl px-2 py-1.5 text-[13px] transition-colors duration-100 " +
                  (f.properties.circuito_id === activeCircuito ? "bg-surface-2 shadow-elevation-xs" : "hover:bg-surface-hover")
                }
              >
                <span className="w-16 shrink-0 text-ink-muted">Circ. {f.properties.circuito_id}</span>
                <span className="h-1.5 overflow-hidden rounded bg-line">
                  <span
                    className="block h-full rounded"
                    style={{ width: `${Math.min(100, (Math.abs(diff) / maxAbs) * 100)}%`, background: barColor, marginLeft: diff < 0 ? "auto" : 0 }}
                  />
                </span>
                <span className="font-mono text-xs font-semibold" style={{ color: textColor }}>{a.toFixed(1)}% / {b.toFixed(1)}%</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ResumenCandidato({
  label,
  pct,
  color,
  candidato,
  circuitosGanados,
  align = "left",
}: {
  label: string;
  pct: number;
  color: string;
  candidato?: { nombre: string; foto: string | null } | null;
  circuitosGanados: number;
  align?: "left" | "right";
}) {
  return (
    <div className={"flex items-center gap-3 rounded-2xl border border-line-strong bg-surface-2 p-3 " + (align === "right" ? "flex-row-reverse text-right" : "")}>
      {candidato ? <CandidateAvatar candidato={candidato} size={40} ringColor={color} /> : <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: color }} />}
      <div className="min-w-0">
        <div className="truncate text-[13px] font-bold text-ink">{label}</div>
        <div className="font-mono text-lg font-bold" style={{ color }}>{pct.toFixed(1)}%</div>
        <div className="text-[10.5px] text-ink-faint">ganó en {circuitosGanados} de 10 circuitos</div>
      </div>
    </div>
  );
}
