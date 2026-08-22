import json

from app.core.candidatos import candidato_fuerza, candidato_lista
from app.core.db import read_connection


def get_establecimientos_geojson(eleccion_id: str) -> dict:
    """FeatureCollection de puntos (uno por escuela/local de votación) para una elección con
    nivel mesa cargado (ver core.mesas/core.establecimientos, docs/DATA_SOURCES.md sección
    'Nivel mesa (escuela)'). Si además hay voto por mesa cargado (core.resultados_mesa, ver
    load_resultados_mesa.py) suma ganador/detalle por fuerza agregando las mesas de cada
    escuela — si no, solo trae geografía + mesas/electores (compatibilidad con elecciones que
    tienen el mapeo mesa→escuela pero todavía no el voto, si las hubiera)."""
    with read_connection() as con:
        categoria_row = con.execute("SELECT categoria_id FROM core.elecciones WHERE id = ?", [eleccion_id]).fetchone()
        categoria_id = categoria_row[0] if categoria_row else None

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

        totales_rows = con.execute(
            """
            SELECT m.establecimiento_id, sum(t.votantes), sum(t.votos_positivos),
                   sum(t.votos_blanco), sum(t.votos_nulos)
            FROM core.mesas m
            JOIN core.resultados_mesa_totales t ON t.mesa_id = m.id
            WHERE m.eleccion_id = ?
            GROUP BY m.establecimiento_id
            """,
            [eleccion_id],
        ).fetchall()
        totales_by_est = {r[0]: r[1:] for r in totales_rows}

        detalle_rows = con.execute(
            """
            SELECT m.establecimiento_id, fp.nombre_normalizado, sum(rm.votos) AS votos
            FROM core.mesas m
            JOIN core.resultados_mesa rm ON rm.mesa_id = m.id
            JOIN core.fuerzas_politicas fp ON fp.id = rm.fuerza_id
            WHERE m.eleccion_id = ?
            GROUP BY m.establecimiento_id, fp.nombre_normalizado
            ORDER BY m.establecimiento_id, votos DESC
            """,
            [eleccion_id],
        ).fetchall()
        detalle_by_est: dict[str, list[dict]] = {}
        for est_id, fuerza, votos in detalle_rows:
            detalle_by_est.setdefault(est_id, []).append({"fuerza": fuerza, "votos": votos})

    features = []
    for est_id, nombre, direccion, lat, lon, validado, mesas, electores, circuito_id in rows:
        totales = totales_by_est.get(est_id)
        detalle = detalle_by_est.get(est_id, [])
        votantes = positivos = blanco = nulos = None
        participacion_pct = None
        ganador = candidato_ganador = None
        if totales:
            votantes, positivos, blanco, nulos = totales
            if electores:
                participacion_pct = round(votantes * 100.0 / electores, 2)
        if detalle:
            positivos_total = sum(d["votos"] for d in detalle) or None
            for d in detalle:
                d["pct"] = round(d["votos"] * 100.0 / positivos_total, 2) if positivos_total else None
                d["candidato"] = candidato_fuerza(categoria_id, d["fuerza"]) if categoria_id else None
            ganador = detalle[0]["fuerza"]
            candidato_ganador = detalle[0]["candidato"]

        features.append(
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
                    "votantes": votantes,
                    "positivos": positivos,
                    "blanco": blanco,
                    "nulos": nulos,
                    "participacion_pct": participacion_pct,
                    "ganador": ganador,
                    "candidato_ganador": candidato_ganador,
                    "detalle": detalle,
                },
            }
        )
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
