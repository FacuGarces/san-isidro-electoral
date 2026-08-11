from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    database_path: Path = PROJECT_ROOT / "database" / "san_isidro.duckdb"
    schema_path: Path = PROJECT_ROOT / "database" / "schema.sql"
    data_raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    data_processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    dine_api_base: str = "https://resultados.mininterior.gob.ar/api"
    request_timeout_seconds: int = 30


settings = Settings()
