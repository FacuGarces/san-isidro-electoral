"""Importer DINE — PASO 2023, categoría Presidente, circuitos de San Isidro.

Descarga cruda (raw, inmutable) desde la API oficial de DINE. No transforma datos:
eso es responsabilidad de la capa ETL (backend/etl). Ver docs/DATA_SOURCES.md para el
detalle de los endpoints usados y sus limitaciones conocidas.

Uso:
    PYTHONPATH=. python3 importers/sources/dine/import_paso_2023_san_isidro.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC, load_circuitos_municipio
from importers.sources.dine.client import CATEGORIA_PRESIDENTE, TIPO_ELECCION, DineClient

ANIO = 2023
ELECCION_ID = "PASO2023"


def run() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = settings.data_raw_dir / "dine" / ELECCION_ID / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    client = DineClient()
    circuitos = load_circuitos_municipio(SAN_ISIDRO_INDEC)
    print(f"San Isidro: {len(circuitos)} circuitos encontrados en el dataset oficial PBA.")

    manifest = {
        "eleccion_id": ELECCION_ID,
        "anio": ANIO,
        "categoria_id": CATEGORIA_PRESIDENTE,
        "tipo_eleccion": TIPO_ELECCION["PASO"],
        "descargado_en": timestamp,
        "circuitos": [],
    }

    for circuito in circuitos:
        print(f"  circuito {circuito.id} (dine={circuito.id_dine}) ...", end=" ")
        data = client.get_resultados_circuito(
            anio=ANIO,
            tipo_eleccion=TIPO_ELECCION["PASO"],
            categoria_id=CATEGORIA_PRESIDENTE,
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

    print("Descargando agregado + polígono de municipio (San Isidro) ...")
    mapa = client.get_mapa_departamentos(anio=ANIO, id_eleccion=TIPO_ELECCION["PASO"], id_cargo=CATEGORIA_PRESIDENTE)
    san_isidro_feature = next(
        f for f in mapa["features"] if f["properties"].get("INDEC_D") == SAN_ISIDRO_INDEC or f["properties"].get("INDEC_PD", "").endswith(SAN_ISIDRO_INDEC)
    )
    (out_dir / "municipio_san_isidro.json").write_text(json.dumps(san_isidro_feature, ensure_ascii=False, indent=2))

    manifest_path = out_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nOK. Datos crudos guardados en {out_dir}")
    return out_dir


if __name__ == "__main__":
    run()
