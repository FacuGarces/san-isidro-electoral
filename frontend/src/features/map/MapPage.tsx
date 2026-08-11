import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CircuitosGeoJSON } from "../../lib/api";
import { participacionRamp, partyColor, partyRamp, titleCase, PARTY_HEX, PARTY_HEX_OTHER } from "../../lib/colors";
import { nombreCargo } from "../../lib/format";
import { currentMetric, useMapStore } from "../../store/mapStore";
import { downloadCircuitosCsv, downloadCircuitosGeoJson } from "../../lib/export";
import { circuitoPasaFiltro } from "../../lib/filtros";
import { CircuitFilterBar } from "./CircuitFilterBar";
import { EleccionSelect } from "./EleccionSelect";
import { KpiHeader } from "./KpiHeader";
import { MapView } from "./MapView";
import { MetricSelect } from "./MetricSelect";
import { PillTabs } from "./PillTabs";
import { RankingList } from "./RankingList";
import { DetailPanel } from "./DetailPanel";
import { VersusPanel } from "./VersusPanel";

function isDarkMode(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function MapPage() {
  const modo = useMapStore((s) => s.modo);
  const actualId = useMapStore((s) => s.actualId);
  const metricKey = useMapStore((s) => s.metricKey);
  const setModo = useMapStore((s) => s.setModo);
  const setActualId = useMapStore((s) => s.setActualId);
  const setActiveCircuito = useMapStore((s) => s.setActiveCircuito);
  const filtro = useMapStore((s) => s.filtro);
  const metric = currentMetric(metricKey);

  const { data: elecciones } = useQuery({ queryKey: ["elecciones"], queryFn: api.elecciones });

  const eleccionActual = elecciones?.find((e) => e.id === actualId);

  const { data, isLoading, error } = useQuery({
    queryKey: ["circuitos", eleccionActual?.id],
    queryFn: () => api.circuitos(eleccionActual!.id),
    enabled: !!eleccionActual,
  });

  // El filtro del panel Circuitos reduce qué circuitos aparecen en el ranking/agregado — el
  // mapa sigue mostrando los 10 (nunca deja agujeros), solo atenúa los que no matchean (ver
  // `idsFiltrados` más abajo). Memoizado por [data, filtro]: activeCircuito cambia en cada
  // hover del mapa y no tiene que recalcular esto ni retriggerear el repintado de MapView.
  const filteredData: CircuitosGeoJSON | undefined = useMemo(
    () => data && { ...data, features: data.features.filter((f) => circuitoPasaFiltro(f.properties, filtro)) },
    [data, filtro]
  );
  const idsFiltrados = useMemo(() => (filteredData ? new Set(filteredData.features.map((f) => f.properties.circuito_id)) : null), [filteredData]);

  const dark = isDarkMode();
  const nombreActual = eleccionActual ? nombreCargo(eleccionActual.nombre) : "";

  // Si la elección activa tiene interna cargada (PASO con más de una lista por fuerza en algún
  // circuito), un aviso guía hacia "Ver en el mapa" en vez de depender de que el usuario
  // adivine que ahí aparecen los candidatos.
  const tieneInterna = !!data?.features.some((f) => f.properties.detalle.some((d) => d.listas.length > 1));

  const titulo = nombreActual || "San Isidro Electoral Intelligence";
  const subtitulo =
    modo === "versus"
      ? "Elegí 2 candidatos — de esta elección o de cualquier otra (una fuerza entera o un candidato puntual de su interna) — y mirá quién gana en cada circuito."
      : "Circuitos electorales de San Isidro, resultados oficiales de DINE (recuento provisorio), servidos por la API real.";

  return (
    <div className="mx-auto max-w-6xl px-6 py-10 lg:px-10 lg:py-12">
      <header className="mb-6 flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand text-white shadow-elevation-md">
          <BrandMark />
        </div>
        <div className="min-w-0">
          <div className="mb-1 inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px] font-semibold tracking-wide text-brand uppercase">
            San Isidro Electoral Intelligence
          </div>
          <h1 className="m-0 mb-1.5 text-[28px] leading-tight font-bold text-ink">{titulo}</h1>
          <p className="max-w-[65ch] text-sm text-ink-muted">{subtitulo}</p>
        </div>
      </header>

      {/* Un solo marco para todo lo que es "control + estado" (elección, KPIs): secciones
          internas separadas por divide-y, nunca tarjetas independientes apiladas — se lee como
          una sola superficie con zonas, no como cajas sueltas en un flex. */}
      <div className="mb-6 divide-y divide-line overflow-hidden rounded-3xl border border-line bg-surface shadow-elevation-md">
        <div className="p-5 sm:p-6">
          <PillTabs<"ver" | "versus">
            label="Modo"
            value={modo}
            onChange={setModo}
            options={[
              { value: "ver", label: "Ver resultados" },
              { value: "versus", label: "Versus" },
            ]}
          />

          <div className="mt-4">
            <EleccionSelect elecciones={elecciones ?? []} value={actualId} onChange={setActualId} />
          </div>
        </div>

        {!elecciones ? (
          <StateRow>Cargando…</StateRow>
        ) : !eleccionActual ? (
          <StateRow>Todavía no hay datos cargados para esa elección.</StateRow>
        ) : isLoading ? (
          <StateRow>Cargando resultados...</StateRow>
        ) : error || !data ? (
          <StateRow tone="error">No se pudo cargar el mapa. ¿Está corriendo el backend en :8000?</StateRow>
        ) : (
          modo !== "versus" && (
            <div className="bg-surface-2/40 px-5 py-4 sm:px-6">
              <KpiHeader data={data} compareMode={false} />
            </div>
          )
        )}
      </div>

      {modo === "versus" && (
        <div className="overflow-hidden rounded-3xl border border-line bg-surface p-5 shadow-elevation-md sm:p-6">
          <VersusPanel elecciones={elecciones ?? []} />
        </div>
      )}

      {/* Segundo marco integrado: mapa y ranking son columnas de UNA misma superficie
          (divide-x), no dos tarjetas separadas con su propio borde/sombra flotando una al
          lado de la otra. */}
      {data && modo !== "versus" && (
        <div className="grid grid-cols-1 overflow-hidden rounded-3xl border border-line bg-surface shadow-elevation-md lg:grid-cols-[1.6fr_1fr] lg:divide-x lg:divide-line">
          <div className="divide-y divide-line border-b border-line lg:border-b-0">
            <ColumnHeader title="Mapa" icon={<MapIcon />} />
            <div className="p-6">
              {tieneInterna && metric.kind !== "lista" && (
                <div className="mb-3 rounded-xl border border-brand-2/30 bg-surface-2 px-3 py-2 text-[11.5px] text-ink-muted">
                  Esta elección tiene interna — elegí un candidato en <span className="font-semibold text-brand">Ver en el mapa</span> para verlo individualmente.
                </div>
              )}
              <MetricSelect data={data} />
              <MapView data={data} onHover={setActiveCircuito} nombreBase="" idsFiltrados={idsFiltrados} />

              {metric.kind === "winner" ? <WinnerLegend data={data} /> : <GradientLegend metricKey={metricKey} dark={dark} />}
            </div>
          </div>

          <div className="divide-y divide-line">
            <ColumnHeader title="Circuitos" icon={<ListIcon />}>
              <ExportButtons data={data} filenameBase={slugify(`san-isidro_${nombreActual}`)} />
            </ColumnHeader>
            <div className="px-6 pb-6">
              <CircuitFilterBar compareMode={false} matchCount={filteredData!.features.length} totalCount={data.features.length} />
              <RankingList data={filteredData!} nombreBase="" nombreActual={nombreActual} />
              <DetailPanel data={data} filteredData={filteredData!} />
            </div>
          </div>
        </div>
      )}

      <footer className="mt-10 border-t border-line pt-5 text-[11.5px] leading-relaxed text-ink-faint">
        Fuente: Dirección Nacional Electoral (resultados por circuito, provisorio) + Poder Judicial de la Nación / datos
        abiertos PBA (geometría de circuitos) + OpenStreetMap (mapa base). Nivel de detalle: circuito, no mesa individual.
      </footer>
    </div>
  );
}

// Barra de título de una columna dentro del marco compartido de Mapa/Circuitos — ya no es el
// header de una tarjeta propia, es una zona interna de la misma superficie. `children` son
// acciones opcionales alineadas a la derecha (p.ej. exportar).
function ColumnHeader({ title, icon, children }: { title: string; icon: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 px-6 py-3.5">
      <span className="flex h-6 w-6 items-center justify-center text-brand-2">{icon}</span>
      <span className="text-[13px] font-bold tracking-wide text-ink uppercase">{title}</span>
      {children && <div className="ml-auto flex items-center gap-1.5">{children}</div>}
    </div>
  );
}

function slugify(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// Dos botones directos (CSV / GeoJSON) en vez de un dropdown "Exportar" — son solo 2 opciones
// mutuamente excluyentes, mismo criterio que se usa en el resto de la app (PillTabs) para no
// esconder detrás de un menú algo que se ve entero de una.
function ExportButtons({ data, filenameBase }: { data: CircuitosGeoJSON; filenameBase: string }) {
  return (
    <>
      <button
        type="button"
        title="Descargar como CSV (Excel, Sheets)"
        onClick={() => downloadCircuitosCsv(data, false, filenameBase)}
        className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-[11px] font-semibold text-ink-muted transition-colors hover:border-brand-2 hover:text-brand"
      >
        <DownloadIcon />
        CSV
      </button>
      <button
        type="button"
        title="Descargar como GeoJSON (SIG / mapas)"
        onClick={() => downloadCircuitosGeoJson(data, filenameBase)}
        className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-[11px] font-semibold text-ink-muted transition-colors hover:border-brand-2 hover:text-brand"
      >
        <DownloadIcon />
        GeoJSON
      </button>
    </>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v12m0 0-4-4m4 4 4-4M4 19h16" />
    </svg>
  );
}

function StateRow({ tone = "muted", children }: { tone?: "muted" | "error"; children: React.ReactNode }) {
  return (
    <div className={"px-5 py-8 text-center text-sm sm:px-6 " + (tone === "error" ? "text-party-fit" : "text-ink-muted")}>{children}</div>
  );
}

function BrandMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 2 3 7l9 5 9-5-9-5Zm-9 10 9 5 9-5M3 17l9 5 9-5" />
    </svg>
  );
}
function MapIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 20 3 17.5V5L9 7.5m0 12.5 6-2.5m-6 2.5V7.5m6 10 6 2.5V7.5L15 5m0 12.5V5m0 0L9 7.5" />
    </svg>
  );
}
function ListIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
    </svg>
  );
}

function WinnerLegend({ data }: { data: CircuitosGeoJSON }) {
  const counts: Record<string, number> = {};
  data.features.forEach((f) => {
    counts[f.properties.ganador] = (counts[f.properties.ganador] ?? 0) + 1;
  });
  return (
    <div className="mt-3">
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {Object.entries(counts).map(([nombre, n]) => (
          <span key={nombre} className="inline-flex items-center gap-1.5 text-xs text-ink-muted">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: partyColor(nombre) }} />
            {titleCase(nombre)} <span className="font-mono">({n})</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function GradientLegend({ metricKey, dark }: { metricKey: string; dark: boolean }) {
  const metric = currentMetric(metricKey);
  const grad =
    metric.kind === "part"
      ? `linear-gradient(90deg, ${participacionRamp(0, dark)}, ${participacionRamp(1, dark)})`
      : `linear-gradient(90deg, ${partyRamp(PARTY_HEX[metric.fuerza ?? ""] ?? PARTY_HEX_OTHER, 0, dark)}, ${partyRamp(PARTY_HEX[metric.fuerza ?? ""] ?? PARTY_HEX_OTHER, 1, dark)})`;
  return (
    <div className="mt-3">
      <div className="flex items-center gap-2.5">
        <span className="font-mono text-xs text-ink-muted">min</span>
        <div className="h-2.5 flex-1 rounded-md border border-line-strong" style={{ background: grad }} />
        <span className="font-mono text-xs text-ink-muted">max</span>
      </div>
      {metric.kind === "lista" && (
        <div className="mt-1 text-center text-[11px] text-ink-faint">% dentro de la interna de {titleCase(metric.fuerza ?? "")}, no del total de votos</div>
      )}
    </div>
  );
}
