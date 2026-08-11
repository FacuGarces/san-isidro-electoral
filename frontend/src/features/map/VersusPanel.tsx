import { useEffect, useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { api, type CircuitosGeoJSON, type Eleccion } from "../../lib/api";
import { duoColor, metricValueVersus, shade } from "../../lib/colors";
import { currentMetric, useMapStore, type VersusEntry } from "../../store/mapStore";
import { CandidateAvatar } from "./CandidateAvatar";
import { CandidatoSelect } from "./CandidatoSelect";
import { EleccionSelect } from "./EleccionSelect";
import { buildFuerzaRows, type Row } from "./MetricSelect";
import { MapView, type VersusConfig } from "./MapView";

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

let nextEntryId = 0;
function newEntryId(): string {
  return `ve${nextEntryId++}`;
}

function sumParaCircuito(entries: VersusEntry[], dataById: Record<string, CircuitosGeoJSON | undefined>, circuitoId: string): number | null {
  let sum = 0;
  for (const e of entries) {
    const data = dataById[e.eleccionId];
    if (!data) return null;
    const feat = data.features.find((f) => f.properties.circuito_id === circuitoId);
    if (!feat) return null;
    sum += metricValueVersus(feat.properties, currentMetric(e.key));
  }
  return sum;
}

interface Props {
  elecciones: Eleccion[];
}

// Comparación cabeza a cabeza entre 2 lados, circuito por circuito — cada lado es la SUMA de 1
// o más candidatos/fuerzas (fuerza entera o lista puntual de una interna), cada uno de una
// elección propia (pueden ser todas la misma, o mezclarse — p.ej. "LLA Intendente PASO 2023" +
// "Ramón Lanús individual" para modelar un escenario de alianza, pedido explícito del usuario).
export function VersusPanel({ elecciones }: Props) {
  const actualId = useMapStore((s) => s.actualId);
  const versusA = useMapStore((s) => s.versusA);
  const versusB = useMapStore((s) => s.versusB);
  const setVersusA = useMapStore((s) => s.setVersusA);
  const setVersusB = useMapStore((s) => s.setVersusB);
  const activeCircuito = useMapStore((s) => s.activeCircuito);
  const setActiveCircuito = useMapStore((s) => s.setActiveCircuito);

  // Datos de la elección activa (ya en cache de React Query desde MapPage) — de acá sale el
  // default de cada lado cuando todavía no se personalizó nada.
  const { data: dataActual } = useQuery({ queryKey: ["circuitos", actualId], queryFn: () => api.circuitos(actualId), enabled: !!actualId });
  const rowsActual = useMemo(() => (dataActual ? buildFuerzaRows(dataActual) : []), [dataActual]);
  const [defaultKeyA, defaultKeyB] = useMemo(() => parPorDefecto(rowsActual), [rowsActual]);

  const effectiveA: VersusEntry[] = versusA.length ? versusA : [{ id: "default-a", eleccionId: actualId, key: defaultKeyA }];
  const effectiveB: VersusEntry[] = versusB.length ? versusB : [{ id: "default-b", eleccionId: actualId, key: defaultKeyB }];

  // Todas las elecciones involucradas en cualquiera de los 2 lados, sin duplicar fetches — si
  // los 2 lados (o varias entradas de un mismo lado) usan la misma elección, useQueries
  // dedupea por queryKey igual que cualquier useQuery.
  const eleccionIds = useMemo(
    () => [...new Set([...effectiveA, ...effectiveB].map((e) => e.eleccionId))],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(effectiveA), JSON.stringify(effectiveB)]
  );
  const queries = useQueries({
    queries: eleccionIds.map((id) => ({ queryKey: ["circuitos", id], queryFn: () => api.circuitos(id) })),
  });
  // Objeto plano, sin useMemo a propósito: el array de queries que devuelve useQueries cambia
  // de LARGO cuando se agrega/saca una elección (sumar/sacar una entrada de un lado) — usarlo
  // como dependencia de un hook (`...queries.map(...)`) viola las reglas de hooks de React (el
  // tamaño del array de deps tiene que ser constante entre renders) y rompía la app entera al
  // agregar la 2da elección. Recalcular esto en cada render es trivial (10 circuitos, no hay
  // costo real que amerite memoizarlo).
  const dataById: Record<string, CircuitosGeoJSON | undefined> = {};
  eleccionIds.forEach((id, i) => (dataById[id] = queries[i]?.data));

  const cargando = eleccionIds.some((id) => !dataById[id]);

  // Filas (para labels, colores, avatar) de cada entrada, resueltas contra los datos de SU
  // PROPIA elección — necesario para que CandidatoSelect y las etiquetas funcionen aunque las
  // entradas de un lado vengan de elecciones distintas entre sí.
  const rowsFor = (eleccionId: string): Row[] => (dataById[eleccionId] ? buildFuerzaRows(dataById[eleccionId]!) : []);

  // Corrige entradas con una `key` que ya no es válida para su elección (p.ej. el usuario
  // cambió la elección de una entrada y la lista/fuerza vieja no existe en la nueva) apenas
  // llegan los datos de esa elección — antes esto se intentaba adivinar en el momento del
  // cambio, sin datos todavía, y quedaba pegado en una key vacía para siempre (mostraba "?" y
  // 0.0% sin que nada lo arreglara). Solo toca entradas guardadas por el usuario (`versusA`/
  // `versusB` del store, no los defaults sintéticos, que se recalculan solos en cada render).
  useEffect(() => {
    const corregir = (entries: VersusEntry[]): VersusEntry[] | null => {
      let cambio = false;
      const next = entries.map((e) => {
        const rows = rowsFor(e.eleccionId);
        if (rows.length === 0 || rows.some((r) => r.key === e.key)) return e;
        cambio = true;
        return { ...e, key: rows.find((r) => !r.indent)?.key ?? rows[0].key };
      });
      return cambio ? next : null;
    };
    const nextA = corregir(versusA);
    if (nextA) setVersusA(nextA);
    const nextB = corregir(versusB);
    if (nextB) setVersusB(nextB);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataById]);

  let colorA = colorForEntries(effectiveA, dataById);
  let colorB = colorForEntries(effectiveB, dataById);
  if (colorA === colorB) {
    colorA = shade(colorA, 0.18);
    colorB = shade(colorB, -0.28);
  }
  const labelA = labelForEntries(effectiveA, dataById);
  const labelB = labelForEntries(effectiveB, dataById);

  const versus: VersusConfig = { colorA, colorB, labelA, labelB };

  // Base geométrica: los circuitos de la primera entrada del lado A (en la práctica siempre los
  // mismos 10 de San Isidro). Un circuito que no tenga dato en TODAS las entradas de los 2
  // lados (p.ej. una elección parcial que no cubre alguno) se cae del cruce, no rompe el mapa.
  const baseData = dataById[effectiveA[0].eleccionId];
  const merged = useMemo(() => {
    if (cargando || !baseData) return null;
    const features = baseData.features
      .map((f) => {
        const circuitoId = f.properties.circuito_id;
        const versus_a = sumParaCircuito(effectiveA, dataById, circuitoId);
        const versus_b = sumParaCircuito(effectiveB, dataById, circuitoId);
        if (versus_a == null || versus_b == null) return null;
        return { ...f, properties: { ...f.properties, versus_a, versus_b } };
      })
      .filter((f): f is NonNullable<typeof f> => f != null);
    return { ...baseData, features } as CircuitosGeoJSON;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cargando, baseData, JSON.stringify(effectiveA), JSON.stringify(effectiveB), dataById]);

  if (cargando || !merged) {
    return <div className="py-10 text-center text-sm text-ink-muted">Cargando…</div>;
  }

  const eleccionesInvolucradas = new Set([...effectiveA, ...effectiveB].map((e) => e.eleccionId));
  const esAlianza = effectiveA.length > 1 || effectiveB.length > 1;
  const cruzaElecciones = eleccionesInvolucradas.size > 1;

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
        <VersusLado
          entries={effectiveA}
          onChange={setVersusA}
          elecciones={elecciones}
          rowsFor={rowsFor}
          dataFor={(id) => dataById[id]}
          accentColor={colorA}
          actualId={actualId}
        />
        <span className="shrink-0 self-center pt-8 text-[11px] font-bold tracking-wide text-ink-faint sm:pt-16">VS</span>
        <VersusLado
          entries={effectiveB}
          onChange={setVersusB}
          elecciones={elecciones}
          rowsFor={rowsFor}
          dataFor={(id) => dataById[id]}
          accentColor={colorB}
          actualId={actualId}
        />
      </div>

      {(cruzaElecciones || esAlianza) && (
        <p className="mt-2 text-[11px] text-ink-faint">
          {esAlianza && "Sumando más de un candidato/fuerza por lado (escenario de alianza) — los votos de cada uno se suman circuito por circuito. "}
          {cruzaElecciones && 'Comparando elecciones distintas: los % de cada lado son sobre el total de su propia elección, no directamente comparables como "swing" — el mapa muestra qué lado saca más % en cada circuito.'}
        </p>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3">
        <ResumenLado label={labelA} pct={pctA} color={colorA} entries={effectiveA} rowsFor={rowsFor} circuitosGanados={circuitosA} />
        <ResumenLado label={labelB} pct={pctB} color={colorB} entries={effectiveB} rowsFor={rowsFor} circuitosGanados={circuitosB} align="right" />
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

function colorForEntries(entries: VersusEntry[], dataById: Record<string, CircuitosGeoJSON | undefined>): string {
  const data = dataById[entries[0].eleccionId];
  const row = data ? buildFuerzaRows(data).find((r) => r.key === entries[0].key) : undefined;
  return typeof row?.swatch === "string" ? row.swatch : "#8A8496";
}

function labelForEntries(entries: VersusEntry[], dataById: Record<string, CircuitosGeoJSON | undefined>): string {
  return entries
    .map((e) => {
      const data = dataById[e.eleccionId];
      const row = data ? buildFuerzaRows(data).find((r) => r.key === e.key) : undefined;
      return row?.label ?? "?";
    })
    .join(" + ");
}

// Un lado del Versus: 1+ filas de (elección, candidato/fuerza), con botón para sumar otra
// entrada y sacar las que sobren (mínimo 1). Cada fila es independiente — puede ser de una
// elección distinta a las demás filas del mismo lado, así se arman escenarios de alianza entre
// candidatos de elecciones distintas.
function VersusLado({
  entries,
  onChange,
  elecciones,
  rowsFor,
  dataFor,
  accentColor,
  actualId,
}: {
  entries: VersusEntry[];
  onChange: (entries: VersusEntry[]) => void;
  elecciones: Eleccion[];
  rowsFor: (eleccionId: string) => Row[];
  dataFor: (eleccionId: string) => CircuitosGeoJSON | undefined;
  accentColor: string;
  actualId: string;
}) {
  return (
    <div className="min-w-0 flex-1 space-y-2">
      {entries.map((entry, i) => {
        const data = dataFor(entry.eleccionId);
        return (
          <div key={entry.id} className="flex items-start gap-1.5">
            <div className="min-w-0 flex-1 space-y-2">
              <EleccionSelect
                elecciones={elecciones}
                value={entry.eleccionId}
                // No se toca `key` acá: muchas claves (fuerza plana, p.ej. "JUNTOS POR EL
                // CAMBIO") siguen siendo válidas en la elección nueva tal cual. Si no lo son
                // (una lista puntual de una interna que no existe en la otra elección, o el
                // nombre de fuerza no compitió ahí), el efecto de más abajo la corrige apenas
                // llegan los datos de la elección nueva — no hay que adivinar acá antes de
                // tener esos datos (eso era el bug: quedaba con key="" hasta que alguien la
                // tocara a mano, mostrando "?" y 0.0% para siempre).
                onChange={(id) => onChange(entries.map((e, j) => (j === i ? { ...e, eleccionId: id } : e)))}
              />
              {data && (
                <CandidatoSelect
                  data={data}
                  value={entry.key}
                  onChange={(key) => onChange(entries.map((e, j) => (j === i ? { ...e, key } : e)))}
                  accentColor={accentColor}
                />
              )}
            </div>
            {entries.length > 1 && (
              <button
                type="button"
                onClick={() => onChange(entries.filter((_, j) => j !== i))}
                title="Sacar de la suma"
                className="mt-2.5 flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-xl border border-line-strong text-ink-faint transition-colors hover:border-party-fit hover:text-party-fit"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            )}
          </div>
        );
      })}
      <button
        type="button"
        onClick={() => {
          const rows = rowsFor(actualId);
          const nuevaKey = rows.find((r) => !r.indent)?.key ?? "";
          onChange([...entries, { id: newEntryId(), eleccionId: actualId, key: nuevaKey }]);
        }}
        className="flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-xl border border-dashed border-line-strong py-2 text-[12px] font-semibold text-ink-faint transition-colors hover:border-brand-2 hover:text-brand"
      >
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
        </svg>
        Sumar otro candidato/fuerza
      </button>
    </div>
  );
}

function ResumenLado({
  label,
  pct,
  color,
  entries,
  rowsFor,
  circuitosGanados,
  align = "left",
}: {
  label: string;
  pct: number;
  color: string;
  entries: VersusEntry[];
  rowsFor: (eleccionId: string) => Row[];
  circuitosGanados: number;
  align?: "left" | "right";
}) {
  // Con 1 sola entrada mostramos su avatar de siempre; con varias (alianza) no hay "un"
  // candidato que mostrar, así que cae al punto de color nomás.
  const candidato = entries.length === 1 ? rowsFor(entries[0].eleccionId).find((r) => r.key === entries[0].key)?.candidato : undefined;
  return (
    <div className={"flex items-center gap-3 rounded-2xl border border-line-strong bg-surface-2 p-3 " + (align === "right" ? "flex-row-reverse text-right" : "")}>
      {candidato ? <CandidateAvatar candidato={candidato} size={40} ringColor={color} /> : <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: color }} />}
      <div className="min-w-0">
        <div className="truncate text-[13px] font-bold text-ink" title={label}>{label}</div>
        <div className="font-mono text-lg font-bold" style={{ color }}>{pct.toFixed(1)}%</div>
        <div className="text-[10.5px] text-ink-faint">ganó en {circuitosGanados} de 10 circuitos</div>
      </div>
    </div>
  );
}
