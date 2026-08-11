"""ETL bronze -> silver/gold genérico — cualquier categoría/tipo de elección, San Isidro.

Lee el raw descargado por importers/sources/dine/import_circuito_categoria.py y puebla
core.* + marts.agregados_territoriales, igual que los loaders un-off anteriores
(load_paso_2023_san_isidro.py, load_generales_2023_san_isidro.py) pero parametrizado, y además
captura el desglose de listas internas (core.resultados_circuito_lista) — relevante en PASO,
donde una misma fuerza puede llevar más de un candidato a una categoría (p.ej. San Isidro 2023
tuvo 2+ precandidatos a intendente en JxC y en UP).

Idempotente: se puede re-ejecutar contra el mismo raw sin duplicar filas (DELETE + INSERT por
eleccion_id).

Uso:
    PYTHONPATH=. python3 etl/load_circuito_categoria.py \\
        --eleccion-id PASO2023_INTENDENTE --nombre "PASO 2023 - Intendente/a" \\
        --tipo PASO --ambito MUNICIPAL --fecha 2023-08-13 --anio 2023 \\
        --categoria-id 7 --categoria-nombre "Intendente/a" \\
        [--comparable-id GENERALES2023_INTENDENTE] [--raw-dir data/raw/dine/<eleccion_id>/<timestamp>]
"""

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.core.db import apply_schema, get_connection
from app.core.fuerzas import normalizar_nombre_fuerza
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC, load_circuitos_municipio

DISTRITO_ID = "BA"
CIRCUITOS_GEOJSON_PATH = settings.data_raw_dir / "geo_source" / "circuitos_zip" / "circuitos-electorales-pba.geojson"


def _normalize_circuito_code(raw: str) -> str:
    raw = raw.strip()
    return str(int(raw)) if raw.isdigit() else raw


def load_circuito_geometries() -> dict[str, dict]:
    geo = json.loads(CIRCUITOS_GEOJSON_PATH.read_text())
    out = {}
    for f in geo["features"]:
        if f["properties"].get("departamen") != "San Isidro":
            continue
        cid = _normalize_circuito_code(f["properties"]["circuito"])
        out[cid] = f["geometry"]
    return out


def latest_raw_dir(eleccion_id: str) -> Path:
    base = settings.data_raw_dir / "dine" / eleccion_id
    runs = sorted(p for p in base.iterdir() if p.is_dir())
    if not runs:
        raise FileNotFoundError(f"No hay corridas de import en {base}")
    return runs[-1]


def load(
    raw_dir: Path,
    eleccion_id: str,
    nombre: str,
    tipo: str,
    ambito: str,
    fecha: str,
    anio: int,
    categoria_nombre: str,
    comparable_id: str | None,
) -> None:
    manifest = json.loads((raw_dir / "_manifest.json").read_text())
    circuitos_meta = load_circuitos_municipio(SAN_ISIDRO_INDEC)

    con = get_connection()
    apply_schema(con)

    con.execute("BEGIN TRANSACTION")

    con.execute(
        "INSERT INTO core.distritos (id, nombre) VALUES ('BA', 'Buenos Aires') ON CONFLICT (id) DO NOTHING"
    )

    con.execute(
        """
        INSERT INTO core.elecciones
            (id, nombre, tipo, ambito, fecha, anio, categoria_id, categoria_nombre,
             id_eleccion_dine, id_distrito_dine, fuente, eleccion_comparable_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 2, 'DINE', ?)
        ON CONFLICT (id) DO NOTHING
        """,
        [eleccion_id, nombre, tipo, ambito, fecha, anio, manifest["categoria_id"], categoria_nombre, manifest["tipo_eleccion"], comparable_id],
    )

    # El municipio (nombre + geom) no depende de la categoría — si ya está cargado por otra
    # elección se deja como está.
    con.execute(
        "INSERT INTO core.municipios (indec, nombre, distrito_id) VALUES (?, 'San Isidro', 'BA') ON CONFLICT (indec) DO NOTHING",
        [SAN_ISIDRO_INDEC],
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

    con.execute("DELETE FROM core.resultados_circuito WHERE eleccion_id = ?", [eleccion_id])
    con.execute("DELETE FROM core.resultados_circuito_totales WHERE eleccion_id = ?", [eleccion_id])
    con.execute("DELETE FROM core.resultados_circuito_lista WHERE eleccion_id = ?", [eleccion_id])

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

        for agrupacion in positivos:
            fid = agrupacion["idAgrupacion"]
            nombre_fuerza = agrupacion["nombreAgrupacion"]
            # nombre_normalizado ≠ nombre_en_boleta a propósito: el comparador
            # (comparacion.py) empareja circuito+fuerza entre 2 elecciones por este campo, y
            # desde 2025 DINE nombra las mismas marcas con variantes de string ("ALIANZA X",
            # "FTE." en vez de "FRENTE") — sin normalizar, la comparación las trata como fuerzas
            # distintas. Ver app/core/fuerzas.py.
            con.execute(
                """
                INSERT INTO core.fuerzas_politicas (id, nombre_normalizado, color_hex)
                VALUES (?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET nombre_normalizado = excluded.nombre_normalizado
                """,
                [fid, normalizar_nombre_fuerza(nombre_fuerza), None],
            )
            con.execute(
                """
                INSERT INTO core.fuerzas_por_eleccion (fuerza_id, eleccion_id, nombre_en_boleta)
                VALUES (?, ?, ?)
                ON CONFLICT (fuerza_id, eleccion_id) DO NOTHING
                """,
                [fid, eleccion_id, nombre_fuerza],
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
                eleccion_id,
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
                [eleccion_id, circuito_id, fid, agrupacion["votos"], agrupacion["votosPorcentaje"]],
            )
            votos_fuerza = agrupacion["votos"]
            for lista in agrupacion.get("listas", []):
                pct_fuerza = round(lista["votos"] * 100.0 / votos_fuerza, 2) if votos_fuerza else None
                con.execute(
                    """
                    INSERT INTO core.resultados_circuito_lista
                        (eleccion_id, circuito_id, fuerza_id, lista_numero, lista_nombre, votos, votos_pct_fuerza)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (eleccion_id, circuito_id, fuerza_id, lista_numero) DO NOTHING
                    """,
                    [eleccion_id, circuito_id, fid, lista["numero"], lista["nombre"], lista["votos"], pct_fuerza],
                )

    con.execute("DELETE FROM marts.agregados_territoriales WHERE eleccion_id = ? AND nivel = 'circuito'", [eleccion_id])
    con.execute(
        """
        INSERT INTO marts.agregados_territoriales (nivel, nivel_id, eleccion_id, fuerza_id, votos, votos_pct, participacion_pct)
        SELECT 'circuito', rc.circuito_id, rc.eleccion_id, rc.fuerza_id, rc.votos, rc.votos_pct, t.participacion_pct
        FROM core.resultados_circuito rc
        JOIN core.resultados_circuito_totales t
          ON t.eleccion_id = rc.eleccion_id AND t.circuito_id = rc.circuito_id
        WHERE rc.eleccion_id = ?
        """,
        [eleccion_id],
    )

    con.execute("DELETE FROM marts.agregados_territoriales WHERE eleccion_id = ? AND nivel = 'municipio'", [eleccion_id])
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
        [SAN_ISIDRO_INDEC, eleccion_id],
    )

    con.execute("COMMIT")
    con.close()
    print(f"Carga completa para {eleccion_id} desde {raw_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eleccion-id", required=True)
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--tipo", required=True, choices=["PASO", "GENERAL", "BALLOTAGE"])
    parser.add_argument("--ambito", required=True, choices=["NACIONAL", "PROVINCIAL", "MUNICIPAL"])
    parser.add_argument("--fecha", required=True, help="YYYY-MM-DD")
    parser.add_argument("--anio", type=int, required=True)
    parser.add_argument("--categoria-nombre", required=True)
    parser.add_argument("--comparable-id", default=None)
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()

    load(
        raw_dir=args.raw_dir or latest_raw_dir(args.eleccion_id),
        eleccion_id=args.eleccion_id,
        nombre=args.nombre,
        tipo=args.tipo,
        ambito=args.ambito,
        fecha=args.fecha,
        anio=args.anio,
        categoria_nombre=args.categoria_nombre,
        comparable_id=args.comparable_id,
    )
