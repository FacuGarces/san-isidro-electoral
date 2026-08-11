import type { Metric } from "../store/mapStore";
import type { CircuitoProperties } from "./api";

export const PARTY_HEX: Record<string, string> = {
  "JUNTOS POR EL CAMBIO": "#F0B300",
  "LA LIBERTAD AVANZA": "#8B2FE0",
  "UNION POR LA PATRIA": "#1E88E5",
  "FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD": "#C0392B",
  "HACEMOS POR NUESTRO PAIS": "#5C7A99",
  // Fuerzas 2025 — DINE (nacional) y Junta Electoral PBA (provincial) nombran las mismas
  // marcas con variantes de string distintas ("ALIANZA X", "FTE." en vez de "FRENTE"), pero
  // `normalizar_nombre_fuerza` (backend) ya saca el prefijo "ALIANZA " antes de guardar
  // `nombre_normalizado` — el nombre que de verdad llega acá nunca lo trae. Las claves van sin
  // ese prefijo (si lo llevan, nunca hacen match y la fuerza cae en el gris de
  // PARTY_HEX_OTHER — pasaba con Somos Buenos Aires, Potencia y Provincias Unidas).
  "FUERZA PATRIA": "#1E88E5", // = "UNION POR LA PATRIA" arriba, normalizado a ese nombre
  "SOMOS BUENOS AIRES": "#E0529E",
  "POTENCIA": "#E67E22",
  "PROVINCIAS UNIDAS": "#0E8E7E",
  "FTE. DE IZQUIERDA Y DE TRABAJADORES - UNIDAD": "#C0392B", // = "FRENTE DE..." arriba
  "ACCION VECINAL SAN ISIDRO ES DISTINTO": "#4E9A32", // verde hoja, distinto del verde-agua de participación
  // Diputados/as Nacionales 2025 — JxC ya no se presentó como marca única a nivel nacional
  // (se dividió), "PROPUESTA FEDERAL PARA EL CAMBIO" es el sello PRO ese año. Color propio
  // (no reusa el amarillo de JUNTOS POR EL CAMBIO) porque, aunque tienen el mismo origen
  // partidario, son 2 marcas separadas en la boleta y no hay que sugerir continuidad 1:1.
  "PROPUESTA FEDERAL PARA EL CAMBIO": "#D98E04",
};
export const PARTY_HEX_OTHER = "#8A8496";

export function partyColor(name: string): string {
  return PARTY_HEX[name] ?? PARTY_HEX_OTHER;
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}
function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function rgbToHex([r, g, b]: number[]): string {
  return (
    "#" +
    [r, g, b]
      .map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0"))
      .join("")
  );
}
function mixRgb(a: number[], b: number[], t: number): number[] {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
}

export function partyRamp(baseHex: string, t: number, isDark: boolean): string {
  const base = hexToRgb(baseHex);
  const white = [255, 255, 255];
  const darkBg = [21, 12, 41];
  const lo = isDark ? mixRgb(base, darkBg, 0.72) : mixRgb(base, white, 0.87);
  const hi = isDark ? mixRgb(base, white, 0.22) : base;
  return rgbToHex(mixRgb(lo, hi, t));
}

export function participacionRamp(t: number, isDark: boolean): string {
  const lo = isDark ? [22, 45, 42] : [227, 245, 241];
  const hi = isDark ? [92, 222, 198] : [10, 110, 96];
  return rgbToHex(mixRgb(lo, hi, t));
}

// Escala divergente para modo comparación (swing en puntos porcentuales): neutro en 0,
// rojo hacia valores negativos (cae), verde hacia positivos (sube). `maxAbs` define el punto
// de saturación de color en ambas direcciones (normalmente el mayor |swing| observado).
export function swingColor(value: number, maxAbs: number, isDark: boolean): string {
  const neutral = isDark ? [37, 26, 61] : [255, 255, 255];
  const neg = isDark ? [237, 108, 106] : [193, 39, 45];
  const pos = isDark ? [92, 222, 198] : [16, 137, 95];
  const t = maxAbs > 0 ? Math.max(-1, Math.min(1, value / maxAbs)) : 0;
  const base = t < 0 ? neg : pos;
  return rgbToHex(mixRgb(neutral, base, Math.abs(t)));
}

// Escala divergente para el modo Versus (1 candidato contra otro, `VersusPanel.tsx`): a
// diferencia de `swingColor` (rojo/verde fijos, tienen un significado universal de "cae/sube"),
// acá cada polo usa el color REAL del candidato que lidera ese circuito — no hay un
// "cae"/"sube" genérico entre dos candidatos, hay "quién va ganando y con qué marca".
// Sombrea un hex hacia negro (amount < 0, más oscuro) o blanco (amount > 0, más claro) —
// usado en el modo Versus cuando los 2 candidatos elegidos son de la MISMA fuerza (una interna,
// p.ej. Lanús vs. Posse, ambos JUNTOS POR EL CAMBIO): sin esto los dos usarían el mismo hex de
// partido y el mapa/leyenda serían ilegibles — nunca inventar un color nuevo sin relación con la
// marca, solo variar el tono del mismo color de base.
export function shade(hex: string, amount: number): string {
  const base = hexToRgb(hex);
  const target = amount < 0 ? [0, 0, 0] : [255, 255, 255];
  return rgbToHex(mixRgb(base, target, Math.min(1, Math.abs(amount))));
}

export function duoColor(value: number, maxAbs: number, colorPos: string, colorNeg: string, isDark: boolean): string {
  const neutral = isDark ? [37, 26, 61] : [255, 255, 255];
  const t = maxAbs > 0 ? Math.max(-1, Math.min(1, value / maxAbs)) : 0;
  const base = hexToRgb(t < 0 ? colorNeg : colorPos);
  return rgbToHex(mixRgb(neutral, base, Math.abs(t)));
}

export function metricValue(props: CircuitoProperties, metric: Metric): number {
  // ?? 0 a propósito: esto alimenta cálculos numéricos (color, orden, ancho de barra), no
  // texto — si no hay participación (fuente parcial, ver CircuitoProperties) el circuito
  // simplemente cae en la punta baja de la escala, no rompe el cálculo. El "—" en pantalla
  // se maneja aparte, donde se formatea el valor para mostrar.
  if (metric.kind === "part") return props.participacion_pct ?? 0;
  if (metric.kind === "winner") return props.diferencia_pct;
  const row = props.detalle.find((d) => d.fuerza === metric.fuerza);
  if (metric.kind === "lista") {
    // % del candidato DENTRO de su propia fuerza (votos_pct_fuerza), no del total de votos —
    // por eso nunca se compara en la misma escala que un metric.kind "pct" común.
    const lista = row?.listas.find((l) => l.nombre === metric.lista);
    return lista?.pct ?? 0;
  }
  return row ? row.pct : 0;
}

// Complemento de metricValue() para metric.kind === "lista": el % del candidato sobre el TOTAL
// de votos positivos del circuito (no de su interna) — pedido explícito del usuario para que,
// al elegir un candidato de una interna PASO, se vea también cuánto sacó a nivel distrito, no
// solo dentro de su propia fuerza. metricValue() sigue devolviendo el % de interna (es el que
// ordena/colorea el ranking y el mapa) — este es puramente informativo, para texto.
export function metricValueTotal(props: CircuitoProperties, metric: Metric): number | null {
  if (metric.kind !== "lista") return null;
  const row = props.detalle.find((d) => d.fuerza === metric.fuerza);
  const lista = row?.listas.find((l) => l.nombre === metric.lista);
  return lista?.pct_total ?? null;
}

export function fillColorFor(
  props: CircuitoProperties,
  metric: Metric,
  min: number,
  max: number,
  isDark: boolean,
  compareMode = false
): string {
  if (metric.kind === "winner") return partyColor(props.ganador);
  const v = metricValue(props, metric);
  if (compareMode) {
    const maxAbs = Math.max(Math.abs(min), Math.abs(max), 0.01);
    return swingColor(v, maxAbs, isDark);
  }
  const t = max > min ? (v - min) / (max - min) : 0.5;
  if (metric.kind === "part") return participacionRamp(t, isDark);
  return partyRamp(PARTY_HEX[metric.fuerza ?? ""] ?? PARTY_HEX_OTHER, t, isDark);
}

// Color de borde en foco/hover: refleja la vista activa, no siempre el ganador —
// si no, en distritos donde un partido barrió todos los circuitos el borde queda
// pegado en ese color sin importar qué se esté mirando.
export function borderColorFor(props: CircuitoProperties, metric: Metric, isDark: boolean, compareMode = false): string {
  if (metric.kind === "winner") return partyColor(props.ganador);
  if (compareMode) {
    const v = metricValue(props, metric);
    return swingColor(v, Math.max(Math.abs(v), 0.01), isDark);
  }
  if (metric.kind === "part") return participacionRamp(1, isDark);
  return partyRamp(PARTY_HEX[metric.fuerza ?? ""] ?? PARTY_HEX_OTHER, 1, isDark);
}

export type ClasificacionCircuito = "bastion" | "competitivo" | "hostil";

// Umbrales para priorizar recursos de campaña sobre el % de UNA fuerza en un circuito: ya
// asegurado (no vale la pena invertir más ahí), en disputa (mueve el resultado si se invierte)
// o de baja prioridad relativa. Ajustables — son razonables para una elección de 3-4 fuerzas
// competitivas como San Isidro 2023, no una fórmula estadística cerrada.
export function clasificarCircuito(pctFuerza: number): ClasificacionCircuito {
  if (pctFuerza >= 45) return "bastion";
  if (pctFuerza >= 30) return "competitivo";
  return "hostil";
}

export function clasificacionLabel(c: ClasificacionCircuito): string {
  return { bastion: "Bastión", competitivo: "Competitivo", hostil: "Hostil" }[c];
}

export function clasificacionColor(c: ClasificacionCircuito): string {
  return { bastion: "var(--color-teal)", competitivo: "#C9971E", hostil: "var(--color-party-fit)" }[c];
}

export function titleCase(s: string): string {
  return s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}
