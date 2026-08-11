import json

from app.core.candidatos import candidato_fuerza, candidato_lista
from app.core.db import read_connection


def get_circuitos_geojson(eleccion_id: str) -> dict:
    """FeatureCollection de circuitos con resultados embebidos, para el mapa. Todo sale
    de core.* — nada de archivos estáticos precalculados (a diferencia del preview inicial
    en preview/mapa_paso2023.html, que leía un GeoJSON generado a mano)."""
    with read_connection() as con:
        categoria_row = con.execute(
            "SELECT categoria_id FROM core.elecciones WHERE id = ?", [eleccion_id]
        ).fetchone()
        categoria_id = categoria_row[0] if categoria_row else None

        totales = con.execute(
            """
            SELECT circuito_id, mesas_totalizadas, electores, votantes, votos_positivos,
                   votos_blanco, votos_nulos, participacion_pct, ganador_fuerza_id,
                   diferencia_1ro_2do_pct, ST_AsGeoJSON(c.geom)
            FROM core.resultados_circuito_totales t
            JOIN core.circuitos c ON c.id = t.circuito_id
            WHERE t.eleccion_id = ?
            """,
            [eleccion_id],
        ).fetchall()

        detalle_rows = con.execute(
            """
            SELECT rc.circuito_id, fp.nombre_normalizado, rc.votos, rc.votos_pct
            FROM core.resultados_circuito rc
            JOIN core.fuerzas_politicas fp ON fp.id = rc.fuerza_id
            WHERE rc.eleccion_id = ?
            ORDER BY rc.circuito_id, rc.votos DESC
            """,
            [eleccion_id],
        ).fetchall()

        # Listas internas (candidatos) dentro de cada fuerza — sólo interesante cuando hay
        # más de una por fuerza+circuito (típico de una interna PASO reñida).
        listas_rows = con.execute(
            """
            SELECT l.circuito_id, fp.nombre_normalizado, l.lista_numero, l.lista_nombre, l.votos, l.votos_pct_fuerza
            FROM core.resultados_circuito_lista l
            JOIN core.fuerzas_politicas fp ON fp.id = l.fuerza_id
            WHERE l.eleccion_id = ?
            ORDER BY l.circuito_id, fp.nombre_normalizado, l.votos DESC
            """,
            [eleccion_id],
        ).fetchall()

        ganador_nombre = dict(
            con.execute("SELECT id, nombre_normalizado FROM core.fuerzas_politicas").fetchall()
        )

    listas_by_circuito_fuerza: dict[tuple[str, str], list[dict]] = {}
    for circuito_id, fuerza, numero, lista_nombre, votos, pct in listas_rows:
        candidato = candidato_lista(categoria_id, numero) if categoria_id else None
        listas_by_circuito_fuerza.setdefault((circuito_id, fuerza), []).append(
            {"nombre": lista_nombre, "votos": votos, "pct": pct, "candidato": candidato}
        )

    detalle_by_circuito: dict[str, list[dict]] = {}
    for circuito_id, fuerza, votos, pct in detalle_rows:
        detalle_by_circuito.setdefault(circuito_id, []).append(
            {
                "fuerza": fuerza,
                "votos": votos,
                "pct": pct,
                "candidato": candidato_fuerza(categoria_id, fuerza) if categoria_id else None,
                "listas": listas_by_circuito_fuerza.get((circuito_id, fuerza), []),
            }
        )

    features = []
    for row in totales:
        (
            circuito_id,
            mesas,
            electores,
            votantes,
            positivos,
            blanco,
            nulos,
            participacion_pct,
            ganador_id,
            diferencia_pct,
            geom_json,
        ) = row
        if geom_json is None:
            continue
        ganador = ganador_nombre.get(ganador_id, "?")
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geom_json),
                "properties": {
                    "circuito_id": circuito_id,
                    "ganador": ganador,
                    "candidato_ganador": candidato_fuerza(categoria_id, ganador) if categoria_id else None,
                    "mesas": mesas,
                    "electores": electores,
                    "votantes": votantes,
                    "positivos": positivos,
                    "blanco": blanco,
                    "nulos": nulos,
                    "participacion_pct": participacion_pct,
                    "diferencia_pct": diferencia_pct,
                    "detalle": detalle_by_circuito.get(circuito_id, []),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}
