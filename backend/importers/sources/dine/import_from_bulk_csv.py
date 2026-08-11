"""Importer alternativo — CSV masivo oficial (catálogo de datos abiertos), no la API en vivo.

Usar cuando `/resultados/getResultados` (el que usa import_circuito_categoria.py) no sirve el
nivel circuito para una elección — confirmado para Ballotage 2023, ver docs/DATA_SOURCES.md,
sección "Ballotage 2023". DINE publica por separado, vía datos.gob.ar (catálogo CKAN, no
enlazado desde la página normal de resultados), un ZIP con el resultado completo **mesa por
mesa** de cada elección — bastante más fino que lo que devuelve la API en vivo a nivel circuito.

Este script agrega mesa → circuito (suma electores/votantes/votos por agrupación, cuenta mesas
distintas) para producir el mismo formato raw (un JSON por circuito + `_manifest.json`) que
genera `import_circuito_categoria.py`, así `load_circuito_categoria.py` funciona sin cambios
sobre cualquiera de las 2 fuentes.

Uso (Ballotage 2023, Presidente, San Isidro):
    PYTHONPATH=. python3 importers/sources/dine/import_from_bulk_csv.py \\
        --csv-url https://www.argentina.gob.ar/sites/default/files/2023_segundavuelta.zip \\
        --csv-name "2023_segundavuelta/ResultadosElectorales_2023_SegundaVuelta.csv" \\
        --eleccion-id BALLOTAGE2023 --anio 2023 --tipo-eleccion BALLOTAGE \\
        --categoria-id 1 --cargo-nombre "PRESIDENTE Y VICE"
"""

import argparse
import csv
import io
import json
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.core.config import settings
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC, load_circuitos_municipio
from importers.sources.dine.client import TIPO_ELECCION

DISTRITO_ID_BUENOS_AIRES = "2"


def _download_csv(url: str, csv_name: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / Path(csv_name).name
    if cached.exists():
        print(f"  (ya descargado, usando cache en {cached})")
        return cached
    print(f"  descargando {url} ...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open(csv_name) as src, open(cached, "wb") as dst:
            dst.write(src.read())
    return cached


def run(csv_url: str, csv_name: str, eleccion_id: str, anio: int, tipo_eleccion_key: str, categoria_id: int, cargo_nombre: str) -> Path:
    circuitos = load_circuitos_municipio(SAN_ISIDRO_INDEC)
    ids_dine = {c.id_dine for c in circuitos}
    id_dine_to_id = {c.id_dine: c.id for c in circuitos}
    print(f"San Isidro: {len(circuitos)} circuitos objetivo: {sorted(ids_dine)}")

    cache_dir = settings.data_raw_dir / "dine" / "_bulk_csv_cache"
    csv_path = _download_csv(csv_url, csv_name, cache_dir)

    # Acumuladores por circuito.
    electores_por_mesa: dict[str, dict[str, int]] = defaultdict(dict)  # circuito -> {mesa: electores}
    votantes_por_mesa: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # circuito -> {mesa: votantes}
    votos_por_fuerza: dict[str, dict[str, dict]] = defaultdict(dict)  # circuito -> {nombre_fuerza: {"votos": int, "id": str}}
    otros: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # circuito -> {tipo: votos}

    print("  leyendo y agregando CSV mesa -> circuito (puede tardar unos segundos)...")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows_matched = 0
        for row in reader:
            if row["distrito_id"] != DISTRITO_ID_BUENOS_AIRES:
                continue
            circuito_dine = row["circuito_id"]
            if circuito_dine not in ids_dine:
                continue
            if row["cargo_nombre"] != cargo_nombre:
                continue
            rows_matched += 1

            mesa_id = row["mesa_id"]
            electores_por_mesa[circuito_dine][mesa_id] = int(row["mesa_electores"])

            votos = int(row["votos_cantidad"])
            votantes_por_mesa[circuito_dine][mesa_id] += votos

            tipo = row["votos_tipo"]
            if tipo == "POSITIVO":
                nombre_fuerza = row["agrupacion_nombre"]
                agrupacion_id = row["agrupacion_id"]
                entry = votos_por_fuerza[circuito_dine].setdefault(nombre_fuerza, {"votos": 0, "id": agrupacion_id, "nombre": nombre_fuerza})
                entry["votos"] += votos
            elif tipo == "EN BLANCO":
                otros[circuito_dine]["votosEnBlanco"] += votos
            elif tipo == "NULO":
                otros[circuito_dine]["votosNulos"] += votos
            elif tipo in ("IMPUGNADO", "RECURRIDO"):
                # El resto del proyecto (API en vivo) ya junta recurridos+impugnados en un solo
                # campo — ver docs/CHECKLIST.md, "Votos recurridos / impugnados". Replicamos acá
                # para que ambas fuentes carguen el mismo shape.
                otros[circuito_dine]["votosRecurridosComandoImpugnados"] += votos

    print(f"  {rows_matched} filas mesa-nivel matcheadas para {cargo_nombre} en San Isidro.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = settings.data_raw_dir / "dine" / eleccion_id / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "eleccion_id": eleccion_id,
        "anio": anio,
        "categoria_id": categoria_id,
        "tipo_eleccion": TIPO_ELECCION[tipo_eleccion_key],
        "descargado_en": timestamp,
        "fuente": f"bulk_csv:{csv_url}",
        "circuitos": [],
    }

    for circuito_dine, mesa_electores in electores_por_mesa.items():
        circuito_id = id_dine_to_id[circuito_dine]
        electores = sum(mesa_electores.values())
        votantes = sum(votantes_por_mesa[circuito_dine].values())
        mesas = len(mesa_electores)
        participacion = round(votantes * 100.0 / electores, 2) if electores else None

        positivos = sorted(votos_por_fuerza[circuito_dine].values(), key=lambda a: a["votos"], reverse=True)
        votos_positivos_total = sum(a["votos"] for a in positivos)

        data = {
            "estadoRecuento": {
                "mesasEsperadas": mesas,
                "mesasTotalizadas": mesas,
                "mesasTotalizadasPorcentaje": 100.0,
                "cantidadElectores": electores,
                "cantidadVotantes": votantes,
                "participacionPorcentaje": participacion,
            },
            "valoresTotalizadosPositivos": [
                {
                    "idAgrupacion": a["id"],
                    "nombreAgrupacion": a["nombre"],
                    "votos": a["votos"],
                    "votosPorcentaje": round(a["votos"] * 100.0 / votos_positivos_total, 2) if votos_positivos_total else 0,
                    "idAgrupacionTelegrama": "",
                    "urlLogo": "",
                }
                for a in positivos
            ],
            "valoresTotalizadosOtros": {
                "votosNulos": otros[circuito_dine].get("votosNulos", 0),
                "votosNulosPorcentaje": None,
                "votosEnBlanco": otros[circuito_dine].get("votosEnBlanco", 0),
                "votosEnBlancoPorcentaje": None,
                "votosRecurridosComandoImpugnados": otros[circuito_dine].get("votosRecurridosComandoImpugnados", 0),
                "votosRecurridosComandoImpugnadosPorcentaje": None,
            },
        }
        out_file = out_dir / f"circuito_{circuito_id}.json"
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"  circuito {circuito_id}: {mesas} mesas, {electores} electores, {votos_positivos_total} votos positivos")
        manifest["circuitos"].append({"id": circuito_id, "id_dine": circuito_dine, "archivo": out_file.name, "mesas_totalizadas": mesas, "electores": electores})

    (out_dir / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nOK. Datos crudos guardados en {out_dir}")
    return out_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-url", required=True, help="URL del .zip publicado en datos.gob.ar")
    parser.add_argument("--csv-name", required=True, help="Nombre del .csv dentro del .zip")
    parser.add_argument("--eleccion-id", required=True)
    parser.add_argument("--anio", type=int, required=True)
    parser.add_argument("--tipo-eleccion", required=True, choices=list(TIPO_ELECCION.keys()))
    parser.add_argument("--categoria-id", type=int, required=True)
    parser.add_argument("--cargo-nombre", required=True, help='Nombre exacto de la columna cargo_nombre en el CSV, p.ej. "PRESIDENTE Y VICE"')
    args = parser.parse_args()
    run(args.csv_url, args.csv_name, args.eleccion_id, args.anio, args.tipo_eleccion, args.categoria_id, args.cargo_nombre)
