"""Genera un JSON con geometrías proyectadas (SVG) + resultados por circuito de San Isidro
para PASO 2023, para armar una visualización rápida. Uso puntual (no es parte del pipeline
ETL formal) mientras no exista el frontend real (React + MapLibre, ver ARCHITECTURE.md).

Uso:
    PYTHONPATH=backend python3 scripts/build_map_paso2023.py
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.db import get_connection  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GEOJSON_PATH = ROOT / "data/raw/geo_source/circuitos_zip/circuitos-electorales-pba.geojson"
OUT_PATH = ROOT / "data/processed/san_isidro_paso2023_mapa.json"

# Colores reales de las fuerzas (no la paleta de marca de la app, que es solo para el chrome
# de UI) -- un mapa de resultados necesita colores partidarios distinguibles.
COLOR_MAP = {
    "JUNTOS POR EL CAMBIO": "#FFD400",
    "LA LIBERTAD AVANZA": "#7B2FF7",
    "UNION POR LA PATRIA": "#4DA6FF",
    "FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD": "#D1272E",
}
DEFAULT_COLOR = "#9AA0A6"


def normalize_circuito_id(raw: str) -> str:
    raw = raw.strip()
    if raw.isdigit():
        return str(int(raw))
    return raw


def project(lon, lat, bounds, width, height, pad):
    min_lon, max_lon, min_lat, max_lat = bounds
    lat_mid = (min_lat + max_lat) / 2
    aspect = math.cos(math.radians(lat_mid))
    x = (lon - min_lon) * aspect
    y = max_lat - lat  # flip so north is up
    x_range = (max_lon - min_lon) * aspect
    y_range = max_lat - min_lat
    scale = min((width - 2 * pad) / x_range, (height - 2 * pad) / y_range)
    return (
        pad + x * scale,
        pad + y * scale,
    )


def ring_to_path(ring, bounds, width, height, pad):
    pts = [project(lon, lat, bounds, width, height, pad) for lon, lat in ring]
    d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f} " + " ".join(f"L {x:.2f} {y:.2f}" for x, y in pts[1:]) + " Z"
    return d


def main():
    geo = json.loads(GEOJSON_PATH.read_text())
    features = [f for f in geo["features"] if f["properties"].get("departamen") == "San Isidro"]

    all_coords = []
    for f in features:
        polys = f["geometry"]["coordinates"]
        for poly in polys:
            for ring in poly:
                all_coords.extend(ring)
    lons = [c[0] for c in all_coords]
    lats = [c[1] for c in all_coords]
    bounds = (min(lons), max(lons), min(lats), max(lats))

    width, height, pad = 900, 900, 20

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
        raw = f["properties"]["circuito"].strip()
        # Solo los códigos puramente numéricos vienen sin ceros a la izquierda en la DB
        # (890, no 0890). El código con sufijo de letra (0892A) se guardó tal cual.
        circuito_id = str(int(raw)) if raw.isdigit() else raw
        totals = totales.get(circuito_id)
        if not totals:
            print(f"AVISO: sin resultados para circuito {circuito_id} (raw {f['properties']['circuito']})")
            continue

        polys = f["geometry"]["coordinates"]
        paths = []
        for poly in polys:
            for ring in poly:
                paths.append(ring_to_path(ring, bounds, width, height, pad))

        winner_id = totals[8]
        out_features.append(
            {
                "circuito_id": circuito_id,
                "paths": paths,
                "ganador": ganador_nombre.get(winner_id, "?"),
                "color": COLOR_MAP.get(ganador_nombre.get(winner_id, ""), DEFAULT_COLOR),
                "mesas": totals[1],
                "electores": totals[2],
                "votantes": totals[3],
                "positivos": totals[4],
                "blanco": totals[5],
                "nulos": totals[6],
                "participacion_pct": totals[7],
                "diferencia_pct": totals[9],
                "detalle": detalle.get(circuito_id, []),
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"width": width, "height": height, "features": out_features}, ensure_ascii=False, indent=2))
    print(f"OK: {len(out_features)} circuitos -> {OUT_PATH}")


if __name__ == "__main__":
    main()
