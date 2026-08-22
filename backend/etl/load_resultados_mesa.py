"""ETL — voto por mesa, San Isidro (nivel mesa/escuela, 2025 en adelante).

Puebla `core.resultados_mesa` + `core.resultados_mesa_totales` (tablas que ya estaban en el
schema, sin usar hasta ahora — ver docs/DATA_SOURCES.md, sección "Nivel mesa (escuela)") a
partir del CSV masivo mesa-por-mesa ya cacheado por `import_from_bulk_csv.py` para la carga a
nivel circuito de la misma elección (`data/raw/dine/_bulk_csv_cache/<nombre>.csv`) — no hace
falta un importer nuevo, el dato ya está descargado.

A diferencia de `load_circuito_categoria.py` (que agrega mesa→circuito y descarta el detalle de
mesa), este script mantiene el grano mesa. Requiere que `load_locales_votacion.py` haya corrido
antes para esta elección (necesita que `core.mesas` ya tenga las filas — este loader completa
resultados sobre mesas que ya existen, no las crea).

Uso (Diputados Nacionales 2025, San Isidro):
    PYTHONPATH=. python3 etl/load_resultados_mesa.py \\
        --resultados-csv-name resultados2025.csv --eleccion-id DIPUTADOS2025 \\
        --cargo-nombre "DIPUTADO NACIONAL"
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from app.core.config import settings
from app.core.db import apply_schema, get_connection
from app.core.fuerzas import normalizar_nombre_fuerza
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC, load_circuitos_municipio

DISTRITO_ID_BUENOS_AIRES = "2"


def agregar_por_mesa(resultados_csv: Path, cargo_nombre: str, mesa_ids_validos: set[str]) -> dict:
    """Lee el CSV mesa-por-mesa y arma, por mesa: electores, votantes, positivos/blanco/nulos/
    otros, y votos por fuerza (agrupacion_id -> {votos, nombre}).

    `mesa_id` NO es único en toda la provincia de Buenos Aires — se reinicia por circuito en
    otros municipios (mismo gotcha ya pisado en `import_locales_votacion.py`: filtrar por
    mesa_id solo, sin acotar antes a los circuitos de San Isidro, mezcla mesas de otros
    municipios que reusan el mismo número — pasó acá con el mismo síntoma, participación
    reventada por sumar votantes de mesas ajenas). Por eso además de `mesa_ids_validos` se
    filtra por los `id_dine` reales de San Isidro."""
    circuitos = load_circuitos_municipio(SAN_ISIDRO_INDEC)
    ids_dine_san_isidro = {c.id_dine for c in circuitos}

    electores: dict[str, int] = {}
    votos_por_fuerza: dict[str, dict[str, dict]] = defaultdict(dict)
    otros: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    with open(resultados_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["distrito_id"] != DISTRITO_ID_BUENOS_AIRES:
                continue
            if row["circuito_id"] not in ids_dine_san_isidro:
                continue
            if row["cargo_nombre"] != cargo_nombre:
                continue
            mesa_id = str(int(row["mesa_id"]))
            if mesa_id not in mesa_ids_validos:
                continue

            electores[mesa_id] = int(row["mesa_electores"])
            votos = int(row["votos_cantidad"])
            tipo = row["votos_tipo"]

            if tipo == "POSITIVO":
                fid = row["agrupacion_id"]
                entry = votos_por_fuerza[mesa_id].setdefault(fid, {"votos": 0, "nombre": row["agrupacion_nombre"]})
                entry["votos"] += votos
            elif tipo == "EN BLANCO":
                otros[mesa_id]["blanco"] += votos
            elif tipo == "NULO":
                otros[mesa_id]["nulos"] += votos
            elif tipo in ("IMPUGNADO", "RECURRIDO"):
                otros[mesa_id]["recurridos_impugnados"] += votos

    return {"electores": electores, "votos_por_fuerza": votos_por_fuerza, "otros": otros}


def load(resultados_csv_name: str, eleccion_id: str, cargo_nombre: str) -> None:
    resultados_csv = settings.data_raw_dir / "dine" / "_bulk_csv_cache" / resultados_csv_name
    if not resultados_csv.exists():
        raise FileNotFoundError(
            f"No se encontró {resultados_csv} — correr primero import_from_bulk_csv.py o "
            "import_locales_votacion.py para esta elección (cachean el CSV de resultados)."
        )

    con = get_connection()
    apply_schema(con)

    mesa_ids_validos = {
        row[0].split(":", 1)[1] for row in con.execute("SELECT id FROM core.mesas WHERE eleccion_id = ?", [eleccion_id]).fetchall()
    }
    if not mesa_ids_validos:
        raise RuntimeError(
            f"core.mesas no tiene filas para eleccion_id={eleccion_id!r} — correr "
            "load_locales_votacion.py primero para esta elección."
        )
    print(f"  {len(mesa_ids_validos)} mesas cargadas en core.mesas para {eleccion_id!r}.")

    print("  leyendo y agregando el CSV mesa-por-mesa...")
    agregados = agregar_por_mesa(resultados_csv, cargo_nombre, mesa_ids_validos)
    print(f"  {len(agregados['electores'])} mesas con resultado matcheadas (de {len(mesa_ids_validos)} en core.mesas).")

    con.execute("DELETE FROM core.resultados_mesa WHERE mesa_id LIKE ?", [f"{eleccion_id}:%"])
    con.execute("DELETE FROM core.resultados_mesa_totales WHERE mesa_id LIKE ?", [f"{eleccion_id}:%"])

    con.execute("BEGIN TRANSACTION")

    mesas_cargadas = 0
    for numero_mesa, electores in agregados["electores"].items():
        mesa_pk = f"{eleccion_id}:{numero_mesa}"
        fuerzas = agregados["votos_por_fuerza"].get(numero_mesa, {})
        otros_mesa = agregados["otros"].get(numero_mesa, {})

        for fid, entry in fuerzas.items():
            nombre_normalizado = normalizar_nombre_fuerza(entry["nombre"])
            con.execute(
                "INSERT INTO core.fuerzas_politicas (id, nombre_normalizado, color_hex) VALUES (?, ?, NULL) ON CONFLICT (id) DO NOTHING",
                [fid, nombre_normalizado],
            )

        positivos_total = sum(e["votos"] for e in fuerzas.values())
        blanco = otros_mesa.get("blanco", 0)
        nulos = otros_mesa.get("nulos", 0)
        recurridos = otros_mesa.get("recurridos_impugnados", 0)
        votantes = positivos_total + blanco + nulos + recurridos
        participacion_pct = round(votantes * 100.0 / electores, 2) if electores else None

        for fid, entry in fuerzas.items():
            pct = round(entry["votos"] * 100.0 / positivos_total, 2) if positivos_total else None
            con.execute(
                "INSERT INTO core.resultados_mesa (mesa_id, fuerza_id, votos, porcentaje_positivos) VALUES (?, ?, ?, ?)",
                [mesa_pk, fid, entry["votos"], pct],
            )

        ranking = sorted(fuerzas.items(), key=lambda kv: kv[1]["votos"], reverse=True)
        ganador_id = ranking[0][0] if ranking else None
        diferencia_pct = (
            round((ranking[0][1]["votos"] - ranking[1][1]["votos"]) * 100.0 / positivos_total, 2)
            if len(ranking) >= 2 and positivos_total
            else None
        )

        con.execute(
            """
            INSERT INTO core.resultados_mesa_totales
                (mesa_id, votantes, votos_positivos, votos_blanco, votos_nulos,
                 votos_recurridos_comando_impugnados, participacion_pct, ganador_fuerza_id, diferencia_1ro_2do_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [mesa_pk, votantes, positivos_total, blanco, nulos, recurridos, participacion_pct, ganador_id, diferencia_pct],
        )
        mesas_cargadas += 1

    con.execute("COMMIT")
    con.close()
    print(f"OK. {mesas_cargadas} mesas con resultado cargadas para eleccion_id={eleccion_id!r}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resultados-csv-name", required=True, help="Nombre del CSV en data/raw/dine/_bulk_csv_cache/")
    parser.add_argument("--eleccion-id", required=True)
    parser.add_argument("--cargo-nombre", required=True, help='Nombre exacto de cargo_nombre en el CSV, p.ej. "DIPUTADO NACIONAL"')
    args = parser.parse_args()
    load(args.resultados_csv_name, args.eleccion_id, args.cargo_nombre)
