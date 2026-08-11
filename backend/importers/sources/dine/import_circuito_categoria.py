"""Importer DINE genérico — cualquier categoría/tipo de elección, circuitos de San Isidro.

Descarga cruda (raw, inmutable) desde la API oficial de DINE. No transforma datos: eso es
responsabilidad de la capa ETL (backend/etl/load_circuito_categoria.py). Reemplaza el patrón de
un script por combinación tipo+categoría (como import_paso_2023_san_isidro.py) ahora que hay
más de una categoría (Presidente, Intendente, ...) — ver docs/DATA_SOURCES.md para el mapeo de
categoriaId y las limitaciones conocidas de la API.

Uso:
    PYTHONPATH=. python3 importers/sources/dine/import_circuito_categoria.py \\
        --eleccion-id PASO2023_INTENDENTE --anio 2023 --tipo-eleccion PASO --categoria-id 7
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC, load_circuitos_municipio
from importers.sources.dine.client import TIPO_ELECCION, DineClient


def run(eleccion_id: str, anio: int, tipo_eleccion_key: str, categoria_id: int) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = settings.data_raw_dir / "dine" / eleccion_id / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    client = DineClient()
    circuitos = load_circuitos_municipio(SAN_ISIDRO_INDEC)
    print(f"San Isidro: {len(circuitos)} circuitos encontrados en el dataset oficial PBA.")

    tipo_eleccion = TIPO_ELECCION[tipo_eleccion_key]
    manifest = {
        "eleccion_id": eleccion_id,
        "anio": anio,
        "categoria_id": categoria_id,
        "tipo_eleccion": tipo_eleccion,
        "descargado_en": timestamp,
        "circuitos": [],
    }

    for circuito in circuitos:
        print(f"  circuito {circuito.id} (dine={circuito.id_dine}) ...", end=" ")
        data = client.get_resultados_circuito(
            anio=anio,
            tipo_eleccion=tipo_eleccion,
            categoria_id=categoria_id,
            circuito_id_dine=circuito.id_dine,
        )
        out_file = out_dir / f"circuito_{circuito.id}.json"
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        electores = data.get("estadoRecuento", {}).get("cantidadElectores", 0)
        mesas = data.get("estadoRecuento", {}).get("mesasTotalizadas", 0)
        print(f"{mesas} mesas, {electores} electores")
        manifest["circuitos"].append(
            {
                "id": circuito.id,
                "id_dine": circuito.id_dine,
                "archivo": out_file.name,
                "mesas_totalizadas": mesas,
                "electores": electores,
            }
        )

    manifest_path = out_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nOK. Datos crudos guardados en {out_dir}")
    return out_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eleccion-id", required=True)
    parser.add_argument("--anio", type=int, required=True)
    parser.add_argument("--tipo-eleccion", required=True, choices=list(TIPO_ELECCION.keys()))
    parser.add_argument("--categoria-id", type=int, required=True)
    args = parser.parse_args()
    run(args.eleccion_id, args.anio, args.tipo_eleccion, args.categoria_id)
