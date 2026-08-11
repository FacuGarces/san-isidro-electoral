"""Genera un GeoJSON (coordenadas reales, sin proyectar) con resultados de PASO 2023 para
usar con Leaflet + tiles de OpenStreetMap. A diferencia de build_map_paso2023.py (que genera
paths SVG para el Artifact), acá se conservan lon/lat originales.

Uso:
    PYTHONPATH=backend python3 scripts/build_leaflet_data.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.db import get_connection  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GEOJSON_PATH = ROOT / "data/raw/geo_source/circuitos_zip/circuitos-electorales-pba.geojson"
OUT_PATH = ROOT / "data/processed/san_isidro_paso2023_leaflet.geojson"


def normalize(raw: str) -> str:
    raw = raw.strip()
    return str(int(raw)) if raw.isdigit() else raw


def main():
    geo = json.loads(GEOJSON_PATH.read_text())
    features = [f for f in geo["features"] if f["properties"].get("departamen") == "San Isidro"]

    con = get_connection()
    totales = {
        row[0]: row
        for row in con.execute(
            """
            select circuito_id, mesas_totalizadas, electores, votantes, votos_positivos,
                   votos_blanco, votos_nulos, participacion_pct, ganador_fuerza_id,
                   diferencia_1ro_2do_pct
            from core.resultados_circuito_totales
            where eleccion_id = 'PASO2023'
            """
        ).fetchall()
    }
    detalle = {}
    for row in con.execute(
        """
        select rc.circuito_id, fp.nombre_normalizado, rc.votos, rc.votos_pct
        from core.resultados_circuito rc
        join core.fuerzas_politicas fp on fp.id = rc.fuerza_id
        where rc.eleccion_id = 'PASO2023'
        order by rc.circuito_id, rc.votos desc
        """
    ).fetchall():
        detalle.setdefault(row[0], []).append({"fuerza": row[1], "votos": row[2], "pct": row[3]})
    ganador_nombre = {
        row[0]: row[1]
        for row in con.execute("select id, nombre_normalizado from core.fuerzas_politicas").fetchall()
    }
    con.close()

    out_features = []
    for f in features:
        circuito_id = normalize(f["properties"]["circuito"])
        totals = totales.get(circuito_id)
        if not totals:
            continue
        out_features.append(
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "circuito_id": circuito_id,
                    "ganador": ganador_nombre.get(totals[8], "?"),
                    "mesas": totals[1],
                    "electores": totals[2],
                    "votantes": totals[3],
                    "positivos": totals[4],
                    "blanco": totals[5],
                    "nulos": totals[6],
                    "participacion_pct": totals[7],
                    "diferencia_pct": totals[9],
                    "detalle": detalle.get(circuito_id, []),
                },
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"type": "FeatureCollection", "features": out_features}, ensure_ascii=False))
    print(f"OK: {len(out_features)} circuitos -> {OUT_PATH}")


if __name__ == "__main__":
    main()
