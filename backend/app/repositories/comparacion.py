import json

from app.core.candidatos import candidato_fuerza, candidato_lista
from app.core.db import read_connection


def get_comparacion_geojson(actual_id: str, base_id: str) -> dict | None:
    """Diferencia entre dos elecciones cualesquiera, circuito por circuito: puede ser una
    evolución temporal (Generales vs. su PASO, misma categoría) o un cruce entre categorías en
    el mismo momento ("voto cruzado": Presidente vs. Intendente en la misma elección, para ver
    cuánto del voto a la boleta nacional no se traslada al candidato local). Antes este endpoint
    solo aceptaba pares linkeados por `eleccion_comparable_id`; ahora acepta cualquier par de
    elecciones ya cargadas — `eleccion_comparable_id` sigue existiendo en el schema como el
    default sugerido para el preset "evolución", pero no es un requisito de este endpoint.

    Devuelve una forma compatible con CircuitosGeoJSON del frontend, reinterpretando algunos
    campos para el modo comparación (ver comentarios inline): `participacion_pct` pasa a ser el
    swing de participación (no el valor absoluto), y `detalle[].pct` pasa a ser la diferencia en
    puntos porcentuales de esa fuerza — así el resto del frontend (selector de métrica, mapa,
    ranking) funciona sin cambios estructurales, solo mostrando otra magnitud. Devuelve None si
    alguna de las dos elecciones no existe.
    """
    with read_connection() as con:
        rows = con.execute(
            "SELECT id, categoria_id FROM core.elecciones WHERE id IN (?, ?)", [actual_id, base_id]
        ).fetchall()
        categoria_por_eleccion = dict(rows)
        if actual_id not in categoria_por_eleccion or base_id not in categoria_por_eleccion:
            return None
        # Categoría de cada lado por separado: en un cruce entre categorías (voto cruzado,
        # p.ej. actual=Intendente, base=Presidente) cada una tiene su propio mapeo de
        # candidatos — nunca hay que asumir una categoria_id compartida.
        categoria_id_actual = categoria_por_eleccion[actual_id]
        categoria_id_base = categoria_por_eleccion[base_id]

        totales = con.execute(
            """
            SELECT
                t.circuito_id, ST_AsGeoJSON(c.geom),
                t.mesas_totalizadas, t.electores, t.votantes, t.votos_positivos,
                t.votos_blanco, t.votos_nulos, t.participacion_pct, t.ganador_fuerza_id,
                b.participacion_pct, b.ganador_fuerza_id
            FROM core.resultados_circuito_totales t
            JOIN core.circuitos c ON c.id = t.circuito_id
            JOIN core.resultados_circuito_totales b
              ON b.circuito_id = t.circuito_id AND b.eleccion_id = ?
            WHERE t.eleccion_id = ?
            """,
            [base_id, actual_id],
        ).fetchall()

        detalle_actual = con.execute(
            """
            SELECT rc.circuito_id, fp.nombre_normalizado, rc.votos_pct
            FROM core.resultados_circuito rc
            JOIN core.fuerzas_politicas fp ON fp.id = rc.fuerza_id
            WHERE rc.eleccion_id = ?
            """,
            [actual_id],
        ).fetchall()
        detalle_base = con.execute(
            """
            SELECT rc.circuito_id, fp.nombre_normalizado, rc.votos_pct
            FROM core.resultados_circuito rc
            JOIN core.fuerzas_politicas fp ON fp.id = rc.fuerza_id
            WHERE rc.eleccion_id = ?
            """,
            [base_id],
        ).fetchall()

        ganador_nombre = dict(
            con.execute("SELECT id, nombre_normalizado FROM core.fuerzas_politicas").fetchall()
        )

        # Todas las fuerzas a nivel San Isidro completo (no por circuito) para cada lado — usa
        # el agregado ya calculado en marts.agregados_territoriales (nivel='municipio'), no hace
        # falta recalcular acá. Alimenta el banner de comparación general (todas las fuerzas, no
        # solo la ganadora) para cuando todavía no se eligió un circuito puntual.
        def _todas_municipio(eid: str) -> dict[str, float]:
            rows = con.execute(
                """
                SELECT fp.nombre_normalizado, m.votos_pct
                FROM marts.agregados_territoriales m
                JOIN core.fuerzas_politicas fp ON fp.id = m.fuerza_id
                WHERE m.eleccion_id = ? AND m.nivel = 'municipio'
                """,
                [eid],
            ).fetchall()
            return dict(rows)

        pct_actual_muni = _todas_municipio(actual_id)
        pct_base_muni = _todas_municipio(base_id)

        # Candidatos internos del lado "base" (listas), sumados a nivel San Isidro completo —
        # solo tiene sentido cuando el lado base es una PASO (una General no tiene internas). Si
        # el lado base es Presidente y el actual Intendente (voto cruzado), esto simplemente
        # viene vacío y no se muestra desglose de listas, que es lo correcto.
        listas_muni_rows = con.execute(
            """
            SELECT fp.nombre_normalizado, l.lista_numero, l.lista_nombre, SUM(l.votos) AS votos
            FROM core.resultados_circuito_lista l
            JOIN core.fuerzas_politicas fp ON fp.id = l.fuerza_id
            WHERE l.eleccion_id = ?
            GROUP BY 1, 2, 3
            """,
            [base_id],
        ).fetchall()

    pct_actual = {(c, f): pct for c, f, pct in detalle_actual}
    pct_base = {(c, f): pct for c, f, pct in detalle_base}

    fuerzas_by_circuito: dict[str, set[str]] = {}
    for circuito_id, fuerza in list(pct_actual.keys()) + list(pct_base.keys()):
        fuerzas_by_circuito.setdefault(circuito_id, set()).add(fuerza)

    features = []
    for row in totales:
        (
            circuito_id,
            geom_json,
            mesas,
            electores,
            votantes,
            positivos,
            blanco,
            nulos,
            part_actual,
            ganador_actual_id,
            part_base,
            ganador_base_id,
        ) = row
        if geom_json is None:
            continue

        detalle = []
        for fuerza in sorted(fuerzas_by_circuito.get(circuito_id, set())):
            a = pct_actual.get((circuito_id, fuerza), 0.0)
            b = pct_base.get((circuito_id, fuerza), 0.0)
            detalle.append(
                {
                    "fuerza": fuerza,
                    "votos": 0,
                    "listas": [],
                    "pct": round(a - b, 2),
                    "pct_actual": a,
                    "pct_base": b,
                    "candidato": candidato_fuerza(categoria_id_actual, fuerza),
                }
            )
        detalle.sort(key=lambda d: d["pct_actual"], reverse=True)

        ganador_actual = ganador_nombre.get(ganador_actual_id, "?")
        ganador_base = ganador_nombre.get(ganador_base_id, "?")
        swing_ganador = next((d["pct"] for d in detalle if d["fuerza"] == ganador_actual), 0.0)
        participacion_swing = (
            round(part_actual - part_base, 2) if part_actual is not None and part_base is not None else None
        )

        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geom_json),
                "properties": {
                    "circuito_id": circuito_id,
                    "ganador": ganador_actual,
                    "ganador_base": ganador_base,
                    "cambio_ganador": ganador_actual != ganador_base,
                    "candidato_actual": candidato_fuerza(categoria_id_actual, ganador_actual),
                    "candidato_base": candidato_fuerza(categoria_id_base, ganador_base),
                    "mesas": mesas,
                    "electores": electores,
                    "votantes": votantes,
                    "positivos": positivos,
                    "blanco": blanco,
                    "nulos": nulos,
                    "participacion_pct": participacion_swing,
                    "participacion_actual": part_actual,
                    "participacion_base": part_base,
                    "diferencia_pct": swing_ganador,
                    "detalle": detalle,
                },
            }
        )

    # Agrupar listas del lado "base" por fuerza, con el % que representa cada candidato DENTRO
    # de su propia fuerza (no del total de votos) — así "Lanús 52.3%" se lee como "de los votos
    # de JxC en la PASO", que es la lectura natural de una interna.
    listas_por_fuerza: dict[str, list[dict]] = {}
    totales_lista_por_fuerza: dict[str, int] = {}
    for fuerza, _numero, _nombre, votos in listas_muni_rows:
        totales_lista_por_fuerza[fuerza] = totales_lista_por_fuerza.get(fuerza, 0) + votos
    for fuerza, numero, nombre, votos in listas_muni_rows:
        total_fuerza = totales_lista_por_fuerza[fuerza]
        listas_por_fuerza.setdefault(fuerza, []).append(
            {
                "nombre": nombre,
                "votos": votos,
                "pct_fuerza": round(votos * 100.0 / total_fuerza, 2) if total_fuerza else None,
                "candidato": candidato_lista(categoria_id_base, numero),
            }
        )
    for lista in listas_por_fuerza.values():
        lista.sort(key=lambda x: x["votos"], reverse=True)

    todas_fuerzas = sorted(
        set(pct_actual_muni) | set(pct_base_muni),
        key=lambda f: max(pct_actual_muni.get(f, 0.0), pct_base_muni.get(f, 0.0)),
        reverse=True,
    )
    resumen_fuerzas = []
    for fuerza in todas_fuerzas:
        a = pct_actual_muni.get(fuerza)
        b = pct_base_muni.get(fuerza)
        resumen_fuerzas.append(
            {
                "fuerza": fuerza,
                "pct_actual": a,
                "pct_base": b,
                "swing_pct": round(a - b, 2) if a is not None and b is not None else None,
                "candidato_actual": candidato_fuerza(categoria_id_actual, fuerza),
                "candidatos_base": listas_por_fuerza.get(fuerza, []) or (
                    [
                        {
                            "nombre": fuerza,
                            "votos": 0,
                            "pct_fuerza": 100.0,
                            "candidato": candidato_fuerza(categoria_id_base, fuerza),
                        }
                    ]
                    if b is not None
                    else []
                ),
            }
        )

    resumen = {"fuerzas": resumen_fuerzas} if resumen_fuerzas else None

    return {"type": "FeatureCollection", "features": features, "resumen": resumen}
