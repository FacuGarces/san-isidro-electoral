import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { CircuitosGeoJSON, CircuitoProperties } from "../../lib/api";
import { borderColorFor, clasificacionColor, clasificacionLabel, clasificarCircuito, duoColor, fillColorFor, metricValue, partyColor, titleCase } from "../../lib/colors";
import { resolveFotoUrl } from "../../lib/format";
import { currentMetric, useMapStore, type Metric } from "../../store/mapStore";

// Ya no lleva `keyA`/`keyB`: A y B pueden venir de elecciones (fetches) distintas, así que el
// valor de cada lado se resuelve ANTES de llegar acá (VersusPanel.tsx los escribe como
// `properties.versus_a`/`versus_b` en cada feature) — MapView solo pinta, no vuelve a resolver
// `currentMetric(key)` contra un único `data`.
export interface VersusConfig {
  colorA: string;
  colorB: string;
  labelA: string;
  labelB: string;
}

const SOURCE_ID = "circuitos";
const FILL_LAYER_ID = "circuitos-fill";
const LINE_LAYER_ID = "circuitos-line";
// Capa separada, agregada DESPUÉS de las otras dos — en MapLibre el orden de agregado es
// el orden de dibujado, así que esta queda siempre arriba. Así el borde del circuito con
// foco nunca se tapa con el vecino (el bug de z-index que había antes).
const HIGHLIGHT_LAYER_ID = "circuitos-highlight";

function isDarkMode(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

function boundsFor(data: CircuitosGeoJSON): maplibregl.LngLatBounds {
  const bounds = new maplibregl.LngLatBounds();
  data.features.forEach((f) => {
    const coords = f.geometry.type === "MultiPolygon" ? f.geometry.coordinates.flat(2) : (f.geometry as GeoJSON.Polygon).coordinates.flat(1);
    (coords as [number, number][]).forEach((c) => bounds.extend(c));
  });
  return bounds;
}

// Bounds un poco más generosos que los de encuadre, para que map.setMaxBounds no corte los
// circuitos justo en el borde cuando se hace zoom. El pan sigue deshabilitado igual.
function padBounds(bounds: maplibregl.LngLatBounds, factor: number): maplibregl.LngLatBounds {
  const sw = bounds.getSouthWest();
  const ne = bounds.getNorthEast();
  const latPad = (ne.lat - sw.lat) * factor;
  const lngPad = (ne.lng - sw.lng) * factor;
  return new maplibregl.LngLatBounds([sw.lng - lngPad, sw.lat - latPad], [ne.lng + lngPad, ne.lat + latPad]);
}

// Control custom: vuelve a la vista original de San Isidro (equivalente a "Home").
class ResetViewControl implements maplibregl.IControl {
  private container: HTMLDivElement;
  private bounds: maplibregl.LngLatBounds;
  constructor(bounds: maplibregl.LngLatBounds) {
    this.bounds = bounds;
    this.container = document.createElement("div");
    this.container.className = "maplibregl-ctrl maplibregl-ctrl-group";
  }
  onAdd(map: MapLibreMap) {
    const button = document.createElement("button");
    button.type = "button";
    button.title = "Volver a la vista de San Isidro";
    button.setAttribute("aria-label", "Volver a la vista de San Isidro");
    button.className = "maplibregl-ctrl-icon";
    button.style.fontSize = "15px";
    button.style.lineHeight = "29px";
    button.textContent = "⌂";
    button.onclick = () => map.fitBounds(this.bounds, { padding: 24 });
    this.container.appendChild(button);
    return this.container;
  }
  onRemove() {
    this.container.remove();
  }
}

function computeFills(data: CircuitosGeoJSON, metricKey: string, compareMode: boolean, idsFiltrados: Set<string> | null, versus?: VersusConfig | null) {
  const dark = isDarkMode();

  if (versus) {
    const values = data.features.map((f) => (f.properties.versus_a ?? 0) - (f.properties.versus_b ?? 0));
    const maxAbs = Math.max(...values.map((v) => Math.abs(v)), 0.01);
    return {
      ...data,
      features: data.features.map((f, i) => ({
        ...f,
        properties: {
          ...f.properties,
          computed_fill: duoColor(values[i], maxAbs, versus.colorA, versus.colorB, dark),
          fuera_de_filtro: idsFiltrados != null && !idsFiltrados.has(f.properties.circuito_id),
        },
      })),
    };
  }

  const metric = currentMetric(metricKey);
  const values = data.features.map((f) => metricValue(f.properties, metric));
  const min = Math.min(...values);
  const max = Math.max(...values);
  return {
    ...data,
    features: data.features.map((f) => ({
      ...f,
      properties: {
        ...f.properties,
        computed_fill: fillColorFor(f.properties, metric, min, max, dark, compareMode),
        // Cuando hay un filtro activo (buscador / rango de participación en el panel
        // Circuitos), el circuito que no matchea se atenúa en vez de desaparecer — así el mapa
        // nunca queda con agujeros, solo baja de opacidad para no llamar la atención.
        fuera_de_filtro: idsFiltrados != null && !idsFiltrados.has(f.properties.circuito_id),
      },
    })),
  };
}

function popupHtmlVersus(props: CircuitoProperties, versus: VersusConfig): string {
  const a = props.versus_a ?? 0;
  const b = props.versus_b ?? 0;
  const gana = a >= b ? versus.labelA : versus.labelB;
  const ganaColor = a >= b ? versus.colorA : versus.colorB;
  return `
    <div style="font-family:Montserrat,sans-serif;min-width:170px">
      <div style="font-weight:700;margin-bottom:4px;">Circuito ${props.circuito_id}</div>
      <div style="display:flex;justify-content:space-between;gap:12px;font-size:12.5px;margin-bottom:2px;">
        <span style="color:${versus.colorA}">${titleCase(versus.labelA)}</span><strong>${a.toFixed(1)}%</strong>
      </div>
      <div style="display:flex;justify-content:space-between;gap:12px;font-size:12.5px;margin-bottom:6px;">
        <span style="color:${versus.colorB}">${titleCase(versus.labelB)}</span><strong>${b.toFixed(1)}%</strong>
      </div>
      <div style="display:inline-block;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:9999px;color:#fff;background:${ganaColor}">
        Gana ${titleCase(gana)}
      </div>
    </div>
  `;
}

function popupHtml(props: CircuitoProperties, compareMode: boolean, metric: Metric, nombreBase: string): string {
  const signed = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;
  const foto = !compareMode && props.candidato_ganador?.foto ? props.candidato_ganador.foto : null;
  const ganadorNombre = !compareMode && props.candidato_ganador ? props.candidato_ganador.nombre : titleCase(props.ganador);
  const ganadorRow = compareMode
    ? `<div style="display:flex;justify-content:space-between;gap:12px;font-size:12.5px;margin-bottom:2px;">
        <span style="color:#6B6180">Ganador</span><strong>${titleCase(props.ganador)}${props.cambio_ganador ? ` (antes ${titleCase(props.ganador_base ?? "?")})` : ""}</strong>
      </div>`
    : `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        ${foto ? `<img src="${resolveFotoUrl(foto)}" style="width:28px;height:28px;border-radius:9999px;object-fit:cover;border:2px solid ${partyColor(props.ganador)}" />` : ""}
        <div>
          <div style="font-weight:700;font-size:12.5px;">${ganadorNombre}</div>
          <div style="font-size:11px;color:#6B6180">${titleCase(props.ganador)}</div>
        </div>
      </div>`;
  const participacionLabel = compareMode ? `Particip. (Δ vs. ${nombreBase})` : "Participación";
  const participacionValue =
    props.participacion_pct == null ? "—" : compareMode ? `${signed(props.participacion_pct)} pp` : `${props.participacion_pct.toFixed(1)}%`;

  // Badge de bastión/competitivo/hostil — solo tiene sentido con un % absoluto de una fuerza
  // puntual (no en "Ganador"/"Participación" ni sobre un swing, que no es un share).
  let clasificacionRow = "";
  if (!compareMode && metric.kind === "pct") {
    const v = metricValue(props, metric);
    const c = clasificarCircuito(v);
    clasificacionRow = `
      <div style="margin-top:6px;display:inline-block;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:9999px;color:#fff;background:${clasificacionColor(c)}">
        ${clasificacionLabel(c)}
      </div>`;
  }

  return `
    <div style="font-family:Montserrat,sans-serif;min-width:160px">
      <div style="font-weight:700;margin-bottom:4px;">Circuito ${props.circuito_id}</div>
      ${ganadorRow}
      <div style="display:flex;justify-content:space-between;gap:12px;font-size:12.5px;margin-bottom:2px;">
        <span style="color:#6B6180">Electores</span><strong>${props.electores == null ? "—" : props.electores.toLocaleString("es-AR")}</strong>
      </div>
      <div style="display:flex;justify-content:space-between;gap:12px;font-size:12.5px;">
        <span style="color:#6B6180">${participacionLabel}</span><strong>${participacionValue}</strong>
      </div>
      ${clasificacionRow}
    </div>
  `;
}

interface Props {
  data: CircuitosGeoJSON;
  onHover: (circuitoId: string | null) => void;
  nombreBase: string;
  idsFiltrados?: Set<string> | null;
  // Modo Versus (VersusPanel.tsx): cuando está presente, el mapa entero colorea por
  // `metricValue(A) - metricValue(B)` con `duoColor` en vez de la métrica única del store —
  // reemplaza tanto el relleno como el popup, el resto (zoom, bounds, hover) es igual.
  versus?: VersusConfig | null;
}

export function MapView({ data, onHover, nombreBase, idsFiltrados = null, versus = null }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const metricKey = useMapStore((s) => s.metricKey);
  const compareMode = false; // "comparar" se sacó de la UI (CompareCandidatesBanner, que lo usaba, se borró) — queda el literal para no tocar la lógica de abajo por si se retoma
  const activeCircuito = useMapStore((s) => s.activeCircuito);
  const setActiveCircuito = useMapStore((s) => s.setActiveCircuito);
  // El popup se arma dentro de un listener registrado una sola vez (ver abajo), así que no
  // puede cerrar sobre `metricKey`/`versus` directamente sin quedar desactualizado si cambian
  // sin que `data` cambie de identidad. Se leen siempre del ref.
  const metricRef = useRef(currentMetric(metricKey));
  const versusRef = useRef(versus);
  useEffect(() => {
    metricRef.current = currentMetric(metricKey);
  }, [metricKey]);
  useEffect(() => {
    versusRef.current = versus;
  }, [versus]);

  // Init del mapa (una sola vez)
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png", "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> colaboradores',
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: [-58.531, -34.4835],
      zoom: 12,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    mapRef.current = map;

    // Mapa fijo en San Isidro: no tiene sentido poder arrastrarlo fuera de la zona. Se deja
    // solo el zoom (scroll, doble click, pellizco) y un botón para volver a la vista original.
    map.dragPan.disable();
    map.dragRotate.disable();
    map.touchPitch.disable();
    map.keyboard.disable();
    map.touchZoomRotate.disableRotation();

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
    popupRef.current = popup;

    map.on("load", () => {
      map.addSource(SOURCE_ID, { type: "geojson", data: computeFills(data, metricKey, compareMode, idsFiltrados, versus) });

      map.addLayer({
        id: FILL_LAYER_ID,
        type: "fill",
        source: SOURCE_ID,
        paint: { "fill-color": ["get", "computed_fill"], "fill-opacity": ["case", ["get", "fuera_de_filtro"], 0.12, 0.72] },
      });
      // Borde fino y neutro para TODOS los circuitos, siempre visible (separa las formas).
      map.addLayer({
        id: LINE_LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        paint: { "line-color": "#ffffff", "line-width": 1.3 },
      });
      // Borde grueso solo del circuito activo, en capa propia arriba de todo.
      map.addLayer({
        id: HIGHLIGHT_LAYER_ID,
        type: "line",
        source: SOURCE_ID,
        paint: { "line-color": "#ffffff", "line-width": 3.5 },
        filter: ["==", ["get", "circuito_id"], ""],
      });

      const bounds = boundsFor(data);
      map.fitBounds(bounds, { padding: 24, animate: false });
      // No se puede alejar más que el encuadre original de San Isidro (evita mostrar zona
      // "de la nada" fuera del municipio) ni arrastrar la vista fuera de esos límites.
      const camera = map.cameraForBounds(bounds, { padding: 24 });
      if (camera && typeof camera.zoom === "number") {
        map.setMinZoom(camera.zoom - 0.05);
      }
      map.setMaxBounds(padBounds(bounds, 0.2));
      map.addControl(new ResetViewControl(bounds), "top-left");

      let hoveredId: string | null = null;
      map.on("mousemove", FILL_LAYER_ID, (e) => {
        const f = e.features?.[0];
        const id = f?.properties?.circuito_id as string | undefined;
        if (!id) return;
        if (id !== hoveredId) {
          hoveredId = id;
          setActiveCircuito(id);
          onHover(id);
        }
        const props = f!.properties as unknown as CircuitoProperties;
        const html = versusRef.current ? popupHtmlVersus(props, versusRef.current) : popupHtml(props, compareMode, metricRef.current, nombreBase);
        popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", FILL_LAYER_ID, () => {
        hoveredId = null;
        setActiveCircuito(null);
        onHover(null);
        popup.remove();
        map.getCanvas().style.cursor = "";
      });
    });

    return () => {
      popup.remove();
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  // Repintar rellenos cuando cambia la métrica, el versus, o el filtro del panel Circuitos
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    if (!source) return;
    source.setData(computeFills(data, metricKey, compareMode, idsFiltrados, versus) as GeoJSON.FeatureCollection);
  }, [data, metricKey, compareMode, idsFiltrados, versus]);

  // Actualizar el resaltado (filtro + color) cuando cambia el circuito activo, la métrica o el versus
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer(HIGHLIGHT_LAYER_ID)) return;
    const dark = isDarkMode();
    if (!activeCircuito) {
      map.setFilter(HIGHLIGHT_LAYER_ID, ["==", ["get", "circuito_id"], ""]);
      return;
    }
    const feature = data.features.find((f) => f.properties.circuito_id === activeCircuito);
    if (!feature) return;
    map.setFilter(HIGHLIGHT_LAYER_ID, ["==", ["get", "circuito_id"], activeCircuito]);
    if (versus) {
      const v = (feature.properties.versus_a ?? 0) - (feature.properties.versus_b ?? 0);
      map.setPaintProperty(HIGHLIGHT_LAYER_ID, "line-color", v >= 0 ? versus.colorA : versus.colorB);
    } else {
      map.setPaintProperty(HIGHLIGHT_LAYER_ID, "line-color", borderColorFor(feature.properties, currentMetric(metricKey), dark, compareMode));
    }
  }, [data, metricKey, activeCircuito, compareMode, versus]);

  return <div ref={containerRef} className="h-[560px] w-full rounded-xl border border-line-strong" />;
}
