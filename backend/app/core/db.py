from contextlib import contextmanager

import duckdb

from app.core.config import settings


def get_connection() -> duckdb.DuckDBPyConnection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.database_path))
    return con


def apply_schema(con: duckdb.DuckDBPyConnection) -> None:
    sql = settings.schema_path.read_text()
    con.execute(sql)


@contextmanager
def read_connection():
    """Conexión de solo lectura para servir requests de la API. DuckDB permite
    múltiples conexiones read_only concurrentes al mismo archivo sin conflicto con
    los scripts de import/ETL, que abren su propia conexión de escritura aparte."""
    con = duckdb.connect(str(settings.database_path), read_only=True)
    con.execute("LOAD spatial")
    try:
        yield con
    finally:
        con.close()
