from app.core.db import read_connection


def list_elecciones() -> list[dict]:
    with read_connection() as con:
        rows = con.execute(
            """
            SELECT id, nombre, tipo, ambito, fecha, anio, categoria_nombre, fuente, eleccion_comparable_id
            FROM core.elecciones
            ORDER BY fecha
            """
        ).fetchall()
    cols = ["id", "nombre", "tipo", "ambito", "fecha", "anio", "categoria_nombre", "fuente", "eleccion_comparable_id"]
    return [dict(zip(cols, row)) for row in rows]
