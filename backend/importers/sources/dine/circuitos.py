import csv
from dataclasses import dataclass

from app.core.config import settings

CIRCUITOS_PBA_CSV = settings.data_raw_dir / "geo_source" / "circuitos-electorales-pba.csv"


@dataclass(frozen=True)
class Circuito:
    id: str  # código tal cual la fuente oficial, p.ej. "890" o "0892A"
    id_dine: str  # zero-padded a 5 caracteres, formato que espera la API de DINE
    municipio_nombre: str
    municipio_indec: str


def _to_dine_id(codigo: str) -> str:
    codigo = codigo.strip()
    if codigo.isdigit():
        return codigo.zfill(5)
    return codigo


def load_circuitos_municipio(municipio_indec: str, csv_path=CIRCUITOS_PBA_CSV) -> list[Circuito]:
    """Lee el dataset oficial 'Circuitos Electorales PBA' (Poder Judicial de la Nación,
    catalogo.datos.gba.gob.ar) y devuelve los circuitos de un municipio por su código INDEC.
    Ver docs/DATA_SOURCES.md."""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No se encontró {csv_path}. Descargar de "
            "https://catalogo.datos.gba.gob.ar/dataset/circuitos-electorales"
        )
    circuitos = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["indec_municipio"].strip() != municipio_indec:
                continue
            codigo = row["circuito"].strip()
            circuitos.append(
                Circuito(
                    id=codigo,
                    id_dine=_to_dine_id(codigo),
                    municipio_nombre=row["muncipio_nombre"].strip(),
                    municipio_indec=row["indec_municipio"].strip(),
                )
            )
    return circuitos


SAN_ISIDRO_INDEC = "756"
