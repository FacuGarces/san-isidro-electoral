import json

from app.core.candidatos import candidato_fuerza, candidato_lista
from app.core.db import read_connection


def get_establecimientos_geojson(eleccion_id: str) -> dict:
    """FeatureCollection de puntos (uno por escuela/local de votación) para una elección con
    nivel mesa cargado (ver core.mesas/core.establecimientos, docs/DATA_SOURCES.md sección
    'Nivel mesa (escuela)'). Solo geografía + agregados de mesas por ahora — el voto por mesa
    (core.resultados_mesa) todavía no se carga para ninguna elección, así que no hay ganador/%
    por escuela acá, solo ubicación y cuántas mesas/electores tiene cada local."""
    with read_connection() as con:
        rows = con.execute(
            """
            SELECT e.id, e.nombre, e.direccion, e.lat, e.lon, e.validado,
                   count(m.id) AS mesas, sum(m.electores_habilitados) AS electores,
                   any_value(m.circuito_id) AS circuito_id
            FROM core.mesas m
            JOIN core.establecimientos e ON e.id = m.establecimiento_id
            WHERE m.eleccion_id = ? AND e.lat IS NOT NULL AND e.lon IS NOT NULL
            GROUP BY e.id, e.nombre, e.direccion, e.lat, e.lon, e.validado
            """,
            [eleccion_id],
        ).fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "establecimiento_id": est_id,
                "nombre": nombre,
                "direccion": direccion,
                "validado": validado,
                "mesas": mesas,
                "electores": electores,
                "circuito_id": circuito_id,
            },
        }
        for est_id, nombre, direccion, lat, lon, validado, mesas, electores, circuito_id in rows
    ]
    return {"type": "FeatureCollection", "features": features}


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

    # positivos por circuito — para poder mostrar, además del % de la lista DENTRO de su
    # fuerza (votos_pct_fuerza, lo único que había hasta ahora), el % sobre el total de votos
    # positivos del circuito. Pedido explícito del usuario: al elegir un candidato de una
    # interna PASO, quiere ver los dos números, no solo el de la interna.
    positivos_by_circuito: dict[str, int | None] = {row[0]: row[4] for row in totales}

    listas_by_circuito_fuerza: dict[tuple[str, str], list[dict]] = {}
    for circuito_id, fuerza, numero, lista_nombre, votos, pct in listas_rows:
        candidato = candidato_lista(categoria_id, numero) if categoria_id else None
        positivos = positivos_by_circuito.get(circuito_id)
        pct_total = round(votos * 100.0 / positivos, 2) if positivos else None
        listas_by_circuito_fuerza.setdefault((circuito_id, fuerza), []).append(
            {"nombre": lista_nombre, "votos": votos, "pct": pct, "pct_total": pct_total, "candidato": candidato}
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
