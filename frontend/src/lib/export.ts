import type { CircuitosGeoJSON } from "./api";

function csvCell(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return "";
  const s = String(value);
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// Formato largo (una fila por circuito × fuerza) — es el que mejor se lleva con tablas
// dinámicas de Excel/Sheets, en vez de una fila ancha con una columna por fuerza (que cambia
// de forma según cuántas fuerzas compitieron y rompe cualquier fórmula armada sobre el archivo).
// Delimitador ";" (no ",") porque Excel en configuración regional es-AR interpreta la coma como
// separador decimal del sistema operativo e ignora/rompe el ",", incluso con extensión .csv.
export function circuitosToCsv(data: CircuitosGeoJSON, compareMode: boolean): string {
  const delim = ";";
  const headers = compareMode
    ? ["circuito_id", "electores", "mesas", "participacion_swing_pp", "ganador_actual", "ganador_base", "cambio_ganador", "fuerza", "candidato", "pct_base", "pct_actual", "swing_pp"]
    : ["circuito_id", "electores", "mesas", "participacion_pct", "ganador", "diferencia_1ro_2do_pct", "fuerza", "candidato", "votos", "pct"];

  const rows: string[][] = [];
  for (const f of data.features) {
    const p = f.properties;
    for (const d of p.detalle) {
      const candidatoNombre = d.candidato?.nombre ?? "";
      rows.push(
        compareMode
          ? [p.circuito_id, String(p.electores), String(p.mesas), String(p.participacion_pct), p.ganador, p.ganador_base ?? "", p.cambio_ganador ? "si" : "no", d.fuerza, candidatoNombre, String(d.pct_base ?? ""), String(d.pct_actual ?? ""), String(d.pct)]
          : [p.circuito_id, String(p.electores), String(p.mesas), String(p.participacion_pct), p.ganador, String(p.diferencia_pct), d.fuerza, candidatoNombre, String(d.votos), String(d.pct)]
      );
    }
  }

  const lines = [headers, ...rows].map((r) => r.map(csvCell).join(delim));
  return "﻿" + lines.join("\r\n") + "\r\n";
}

function downloadBlob(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadCircuitosCsv(data: CircuitosGeoJSON, compareMode: boolean, filenameBase: string): void {
  downloadBlob(circuitosToCsv(data, compareMode), `${filenameBase}.csv`, "text/csv;charset=utf-8");
}

export function downloadCircuitosGeoJson(data: CircuitosGeoJSON, filenameBase: string): void {
  downloadBlob(JSON.stringify(data, null, 2), `${filenameBase}.geojson`, "application/geo+json");
}
