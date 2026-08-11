"""ETL bronze -> silver/gold para Generales 2023, circuitos de San Isidro.

Lee el raw descargado por importers/sources/dine/import_generales_2023_san_isidro.py y
puebla core.* y marts.agregados_territoriales. Idempotente: se puede re-ejecutar contra el
mismo directorio de raw sin duplicar filas (usa DELETE + INSERT por elección).

Uso:
    PYTHONPATH=. python3 etl/load_generales_2023_san_isidro.py [--raw-dir data/raw/dine/GENERALES2023/<timestamp>]
"""

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.core.db import apply_schema, get_connection
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC, load_circuitos_municipio

ELECCION_ID = "GENERALES2023"
ELECCION_COMPARABLE_ID = "PASO2023"
DISTRITO_ID = "BA"
CIRCUITOS_GEOJSON_PATH = settings.data_raw_dir / "geo_source" / "circuitos_zip" / "circuitos-electorales-pba.geojson"


def _normalize_circuito_code(raw: str) -> str:
    raw = raw.strip()
    return str(int(raw)) if raw.isdigit() else raw


def load_circuito_geometries() -> dict[str, dict]:
    """Geometrías oficiales de circuitos (Poder Judicial de la Nación / datos abiertos PBA),
    ya usadas para el mapa Leaflet. Ver docs/DATA_SOURCES.md."""
    geo = json.loads(CIRCUITOS_GEOJSON_PATH.read_text())
    out = {}
    for f in geo["features"]:
        if f["properties"].get("departamen") != "San Isidro":
            continue
        cid = _normalize_circuito_code(f["properties"]["circuito"])
        out[cid] = f["geometry"]
    return out


def latest_raw_dir() -> Path:
    base = settings.data_raw_dir / "dine" / ELECCION_ID
    runs = sorted(p for p in base.iterdir() if p.is_dir())
    if not runs:
        raise FileNotFoundError(f"No hay corridas de import en {base}")
    return runs[-1]


def load(raw_dir: Path) -> None:
    manifest = json.loads((raw_dir / "_manifest.json").read_text())
    circuitos_meta = load_circuitos_municipio(SAN_ISIDRO_INDEC)
    circuitos_by_id = {c.id: c for c in circuitos_meta}

    con = get_connection()
    apply_schema(con)

    con.execute("BEGIN TRANSACTION")

    con.execute(
        """
        INSERT INTO core.distritos (id, nombre) VALUES ('BA', 'Buenos Aires')
        ON CONFLICT (id) DO NOTHING
        """
    )

    con.execute(
        """
        INSERT INTO core.elecciones
            (id, nombre, tipo, ambito, fecha, anio, categoria_id, categoria_nombre,
             id_eleccion_dine, id_distrito_dine, fuente, eleccion_comparable_id)
        VALUES (?, ?, 'GENERAL', 'NACIONAL', DATE '2023-10-22', 2023, ?, 'Presidente/a', ?, 2, 'DINE', ?)
        ON CONFLICT (id) DO NOTHING
        """,
        [ELECCION_ID, "Generales 2023 - Presidente/a", manifest["categoria_id"], manifest["tipo_eleccion"], ELECCION_COMPARABLE_ID],
    )

    municipio_feature = json.loads((raw_dir / "municipio_san_isidro.json").read_text())
    props = municipio_feature["properties"]
    geom_geojson = json.dumps(municipio_feature["geometry"])
    con.execute(
        """
        INSERT INTO core.municipios (indec, nombre, distrito_id, geom)
        VALUES (?, ?, 'BA', ST_GeomFromGeoJSON(?))
        ON CONFLICT (indec) DO NOTHING
        """,
        [SAN_ISIDRO_INDEC, props["DPTO"], geom_geojson],
    )

    circuito_geoms = load_circuito_geometries()
    for c in circuitos_meta:
        geom = circuito_geoms.get(c.id)
        con.execute(
            """
            INSERT INTO core.circuitos (id, id_dine, distrito_id, municipio_nombre, municipio_indec, geom)
            VALUES (?, ?, 'BA', ?, ?, ST_GeomFromGeoJSON(?))
            ON CONFLICT (id) DO NOTHING
            """,
            [c.id, c.id_dine, c.municipio_nombre, c.municipio_indec, json.dumps(geom) if geom else None],
        )

    con.execute("DELETE FROM core.resultados_circuito WHERE eleccion_id = ?", [ELECCION_ID])
    con.execute("DELETE FROM core.resultados_circuito_totales WHERE eleccion_id = ?", [ELECCION_ID])

    fuerzas_seen: dict[str, tuple[str, str | None]] = {}

    for entry in manifest["circuitos"]:
        circuito_id = entry["id"]
        data = json.loads((raw_dir / entry["archivo"]).read_text())
        estado = data["estadoRecuento"]
        otros = data["valoresTotalizadosOtros"]
        positivos = data["valoresTotalizadosPositivos"]

        votos_positivos_total = sum(a["votos"] for a in positivos)
        ranking = sorted(positivos, key=lambda a: a["votos"], reverse=True)
        ganador_id = ranking[0]["idAgrupacion"] if ranking else None
        if len(ranking) >= 2 and votos_positivos_total > 0:
            diff_pct = round((ranking[0]["votos"] - ranking[1]["votos"]) / votos_positivos_total * 100, 2)
        else:
            diff_pct = None

        # Las fuerzas políticas deben existir antes de insertar totales (ganador_fuerza_id
        # es FK) y antes del detalle por fuerza.
        for agrupacion in positivos:
            fid = agrupacion["idAgrupacion"]
            nombre = agrupacion["nombreAgrupacion"]
            if fid not in fuerzas_seen:
                fuerzas_seen[fid] = (nombre, None)
                con.execute(
                    """
                    INSERT INTO core.fuerzas_politicas (id, nombre_normalizado, color_hex)
                    VALUES (?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET nombre_normalizado = excluded.nombre_normalizado
                    """,
                    [fid, nombre, None],
                )
                con.execute(
                    """
                    INSERT INTO core.fuerzas_por_eleccion (fuerza_id, eleccion_id, nombre_en_boleta)
                    VALUES (?, ?, ?)
                    ON CONFLICT (fuerza_id, eleccion_id) DO NOTHING
                    """,
                    [fid, ELECCION_ID, nombre],
                )

        con.execute(
            """
            INSERT INTO core.resultados_circuito_totales
                (eleccion_id, circuito_id, mesas_totalizadas, electores, votantes,
                 votos_positivos, votos_blanco, votos_nulos, votos_recurridos_comando_impugnados,
                 participacion_pct, ganador_fuerza_id, diferencia_1ro_2do_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ELECCION_ID,
                circuito_id,
                estado["mesasTotalizadas"],
                estado["cantidadElectores"],
                estado["cantidadVotantes"],
                votos_positivos_total,
                otros["votosEnBlanco"],
                otros["votosNulos"],
                otros["votosRecurridosComandoImpugnados"],
                estado["participacionPorcentaje"],
                ganador_id,
                diff_pct,
            ],
        )

        for agrupacion in positivos:
            fid = agrupacion["idAgrupacion"]
            con.execute(
                """
                INSERT INTO core.resultados_circuito (eleccion_id, circuito_id, fuerza_id, votos, votos_pct)
                VALUES (?, ?, ?, ?, ?)
                """,
                [ELECCION_ID, circuito_id, fid, agrupacion["votos"], agrupacion["votosPorcentaje"]],
            )

    # marts.agregados_territoriales — nivel circuito (copia directa de core.resultados_circuito)
    con.execute("DELETE FROM marts.agregados_territoriales WHERE eleccion_id = ? AND nivel = 'circuito'", [ELECCION_ID])
    con.execute(
        """
        INSERT INTO marts.agregados_territoriales (nivel, nivel_id, eleccion_id, fuerza_id, votos, votos_pct, participacion_pct)
        SELECT 'circuito', rc.circuito_id, rc.eleccion_id, rc.fuerza_id, rc.votos, rc.votos_pct, t.participacion_pct
        FROM core.resultados_circuito rc
        JOIN core.resultados_circuito_totales t
          ON t.eleccion_id = rc.eleccion_id AND t.circuito_id = rc.circuito_id
        WHERE rc.eleccion_id = ?
        """,
        [ELECCION_ID],
    )

    # marts.agregados_territoriales — nivel municipio (San Isidro = suma de sus circuitos)
    con.execute("DELETE FROM marts.agregados_territoriales WHERE eleccion_id = ? AND nivel = 'municipio'", [ELECCION_ID])
    con.execute(
        """
        INSERT INTO marts.agregados_territoriales (nivel, nivel_id, eleccion_id, fuerza_id, votos, votos_pct, participacion_pct)
        SELECT
            'municipio', ?, eleccion_id, fuerza_id,
            SUM(votos) AS votos,
            ROUND(SUM(votos) * 100.0 / SUM(SUM(votos)) OVER (), 2) AS votos_pct,
            NULL AS participacion_pct
        FROM core.resultados_circuito
        WHERE eleccion_id = ?
        GROUP BY eleccion_id, fuerza_id
        """,
        [SAN_ISIDRO_INDEC, ELECCION_ID],
    )

    con.execute("COMMIT")
    con.close()
    print(f"Carga completa para {ELECCION_ID} desde {raw_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()
    load(args.raw_dir or latest_raw_dir())
