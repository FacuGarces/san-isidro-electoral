"""ETL bronze -> core — mapeo mesa -> escuela (local de votación), San Isidro.

Lee el raw producido por importers/sources/dine/import_locales_votacion.py y puebla
core.establecimientos (una fila por escuela, con geocoding) + core.mesas (una fila por mesa,
apuntando a su establecimiento y circuito). Ver docs/DATA_SOURCES.md, sección "Nivel mesa
(escuela)".

core.establecimientos es compartido entre elecciones (la escuela es la misma), así que se
inserta con ON CONFLICT DO NOTHING — igual criterio que core.circuitos/core.municipios (ver
CLAUDE.md, "Gotcha" del upsert de geometría: DuckDB implementa UPDATE como delete+insert
internamente, lo que rompería la FK de core.mesas si ya hay mesas cargadas apuntando a un
establecimiento existente). core.mesas SÍ es por elección (mismo local puede tener mesas
distintas de una elección a otra) — DELETE+INSERT por eleccion_id, idempotente.

Uso:
    PYTHONPATH=. python3 etl/load_locales_votacion.py --eleccion-id DIPUTADOS2025
"""

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.core.db import apply_schema, get_connection


def latest_raw_file(eleccion_id: str) -> Path:
    base = settings.data_raw_dir / "dine" / eleccion_id
    runs = sorted(p for p in base.iterdir() if p.is_dir())
    if not runs:
        raise FileNotFoundError(f"No hay corridas de import_locales_votacion.py en {base}")
    return runs[-1] / "locales_votacion.json"


def load(raw_file: Path, eleccion_id: str) -> None:
    raw = json.loads(raw_file.read_text())
    escuelas = raw["escuelas"]

    con = get_connection()
    apply_schema(con)

    con.execute("BEGIN TRANSACTION")

    for escuela in escuelas:
        establecimiento_id = f"SI:{escuela['codigo']}"
        circuito_id = escuela["mesas"][0]["circuito_id"] if escuela["mesas"] else None
        lat, lon = escuela["lat"], escuela["lon"]
        con.execute(
            """
            INSERT INTO core.establecimientos
                (id, nombre, direccion, lat, lon, geom, fuente_geocoding, precision_geocoding, validado, circuito_id)
            VALUES (?, ?, ?, ?, ?, CASE WHEN ? IS NULL THEN NULL ELSE ST_Point(?, ?) END, 'nominatim', ?, FALSE, ?)
            ON CONFLICT (id) DO NOTHING
            """,
            [
                establecimiento_id,
                escuela["nombre"],
                f"{escuela['direccion']}, {escuela['localidad']}",
                lat,
                lon,
                lon,
                lon,
                lat,
                escuela["precision_geocoding"],
                circuito_id,
            ],
        )

    con.execute("DELETE FROM core.mesas WHERE eleccion_id = ?", [eleccion_id])
    mesas_insertadas = 0
    for escuela in escuelas:
        establecimiento_id = f"SI:{escuela['codigo']}"
        for mesa in escuela["mesas"]:
            con.execute(
                """
                INSERT INTO core.mesas
                    (id, eleccion_id, numero_mesa, establecimiento_id, circuito_id, electores_habilitados)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    f"{eleccion_id}:{mesa['numero_mesa']}",
                    eleccion_id,
                    mesa["numero_mesa"],
                    establecimiento_id,
                    mesa["circuito_id"],
                    mesa["electores"],
                ],
            )
            mesas_insertadas += 1

    con.execute("COMMIT")
    con.close()

    sin_geo = sum(1 for e in escuelas if e["lat"] is None)
    print(f"OK. {len(escuelas)} establecimientos ({sin_geo} sin geocodificar), {mesas_insertadas} mesas para eleccion_id={eleccion_id!r}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eleccion-id", required=True)
    parser.add_argument("--raw-file", type=Path, default=None, help="Path directo al locales_votacion.json (default: la corrida más reciente)")
    args = parser.parse_args()
    raw_file = args.raw_file or latest_raw_file(args.eleccion_id)
    load(raw_file, args.eleccion_id)
