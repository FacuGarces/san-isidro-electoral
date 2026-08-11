"""Agrega a cada circuito una lista aproximada de calles que lo delimitan, usando
geocodificación inversa (Nominatim/OpenStreetMap, gratuito, sin API key) sobre puntos
extremos del polígono. Uso puntual para la vista de mapa real (Leaflet); no forma parte
del pipeline ETL. Respeta el límite de 1 request/segundo de Nominatim.

Uso:
    python3 scripts/enrich_calles.py
"""

import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
IN_PATH = ROOT / "data/processed/san_isidro_paso2023_leaflet.geojson"
OUT_PATH = IN_PATH  # enriquece en el mismo archivo

HEADERS = {"User-Agent": "san-isidro-electoral-intelligence/0.1 (proyecto personal, uso no comercial)"}


def extreme_points(coords_flat):
    n = min(coords_flat, key=lambda c: c[1])   # más al sur
    s = max(coords_flat, key=lambda c: c[1])   # más al norte
    e = max(coords_flat, key=lambda c: c[0])   # más al este
    w = min(coords_flat, key=lambda c: c[0])   # más al oeste
    return [n, s, e, w]


def reverse_geocode(lon, lat):
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lon": lon, "lat": lat, "format": "jsonv2", "zoom": 17},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        road = data.get("address", {}).get("road")
        return road
    except Exception as exc:
        print("  error geocodificando", lon, lat, exc)
        return None


def main():
    data = json.loads(IN_PATH.read_text())
    for feature in data["features"]:
        flat = []
        for poly in feature["geometry"]["coordinates"]:
            for ring in poly:
                flat.extend(ring)
        points = extreme_points(flat)
        calles = []
        for lon, lat in points:
            road = reverse_geocode(lon, lat)
            if road and road not in calles:
                calles.append(road)
            time.sleep(1.1)
        feature["properties"]["calles_aprox"] = calles
        print(feature["properties"]["circuito_id"], "->", calles)

    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False))
    print("OK, enriquecido:", OUT_PATH)


if __name__ == "__main__":
    main()
