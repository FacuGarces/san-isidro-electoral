"""Carga puntual (no genérica) — Senadores Provinciales 2025, San Isidro, PARCIAL.

Fuente: capturas de pantalla de la app oficial "Elecciones Bonaerenses 2025"
(ar.gob.gba.eleccionesbonaerenses2025), provistas por el usuario el 2026-08-10. El backend de
esa app (resultados.eleccionesbonaerenses.gba.gob.ar) está dado de baja desde después de la
elección — confirmado por DNS (CNAME a una distribución CloudFront ya eliminada) y por el
archivo de Wayback Machine, que no tiene ninguna captura con los números finales de San Isidro
por circuito. Ver docs/DATA_SOURCES.md, sección "Senadores/Concejales 2025", para el detalle
completo de esa investigación.

Por eso este NO es el patrón genérico (import_circuito_categoria.py / load_circuito_categoria.py
/ import_from_bulk_csv.py) — es un script de una sola vez, con los datos hardcodeados tal cual
se transcribieron de las capturas. Si en algún momento aparece una fuente real (definitiva,
descargable) para esto, hay que borrar esta elección (`DELETE FROM core.elecciones WHERE id =
'SENADORES2025PBA_PARCIAL'` — cascadea al resto por eleccion_id) y cargarla con el patrón normal.

Limitaciones conocidas de esta carga (por eso "PARCIAL" en el id y en el nombre):
- Las capturas muestran "Escrutado" entre 93,93% y 100% según el circuito, no 100% parejo —
  no es el escrutinio definitivo (ese si existe, pero solo a nivel San Isidro completo, no por
  circuito — ver el PDF oficial citado en DATA_SOURCES.md).
- Cada tarjeta muestra máximo 3 fuerzas (las más votadas) — nunca suma 100%, faltan las fuerzas
  chicas (Política Obrera, Frente Patriota Federal, etc. — sí están en el resultado
  definitivo agregado de San Isidro, pero no se pudo ver su desglose por circuito).
- Sin electores, mesas, participación ni votos en blanco/nulos por circuito — la app no los
  mostraba en esta vista y la pantalla de detalle (que sí los tendría) ya no carga.
- `votos` queda NULL en core.resultados_circuito — solo tenemos el %, no el conteo. Por eso
  el esquema se relajó (ver database/schema.sql, comentario en esa columna).

Uso:
    PYTHONPATH=. python3 etl/load_senadores_pba_2025_parcial.py
"""

from app.core.db import apply_schema, get_connection
from app.core.fuerzas import normalizar_nombre_fuerza
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC

ELECCION_ID = "SENADORES2025PBA_PARCIAL"
CATEGORIA_ID = 5  # "Senadores/as provinciales", mismo id que ya usa docs/DATA_SOURCES.md

# (nombre_normalizado tal cual el PDF oficial de escrutinio definitivo) -> fuerza_id.
# Prefijo "pba" a propósito: estos códigos son de la Junta Electoral de la Provincia de Buenos
# Aires (fuente JEP_PBA), un esquema de numeración de listas totalmente distinto al idAgrupacion
# de DINE — nunca deberían mezclarse con los ids ya usados por las elecciones nacionales/DINE.
FUERZAS = {
    "ALIANZA LA LIBERTAD AVANZA": "pba2206",
    "ALIANZA FUERZA PATRIA": "pba2200",
    "ALIANZA SOMOS BUENOS AIRES": "pba2204",
    "FTE. DE IZQUIERDA Y DE TRABAJADORES - UNIDAD": "pba2203",
}

# circuito_id -> [(fuerza, pct), ...] ordenados como los mostró la app (1ro, 2do, 3ro).
# Transcripto a mano de las capturas de pantalla, 2026-08-10.
RESULTADOS_POR_CIRCUITO: dict[str, list[tuple[str, float]]] = {
    "887": [("ALIANZA LA LIBERTAD AVANZA", 66.59), ("ALIANZA FUERZA PATRIA", 17.95), ("ALIANZA SOMOS BUENOS AIRES", 4.82)],
    "888": [("ALIANZA LA LIBERTAD AVANZA", 61.39), ("ALIANZA FUERZA PATRIA", 22.42), ("ALIANZA SOMOS BUENOS AIRES", 5.47)],
    "889": [("ALIANZA LA LIBERTAD AVANZA", 56.60), ("ALIANZA FUERZA PATRIA", 28.55), ("ALIANZA SOMOS BUENOS AIRES", 4.30)],
    "890": [("ALIANZA LA LIBERTAD AVANZA", 63.65), ("ALIANZA FUERZA PATRIA", 22.54), ("FTE. DE IZQUIERDA Y DE TRABAJADORES - UNIDAD", 3.45)],
    "891": [("ALIANZA LA LIBERTAD AVANZA", 62.63), ("ALIANZA FUERZA PATRIA", 22.32), ("FTE. DE IZQUIERDA Y DE TRABAJADORES - UNIDAD", 4.64)],
    "892": [("ALIANZA LA LIBERTAD AVANZA", 46.35), ("ALIANZA FUERZA PATRIA", 39.33), ("FTE. DE IZQUIERDA Y DE TRABAJADORES - UNIDAD", 3.94)],
    "0892A": [("ALIANZA LA LIBERTAD AVANZA", 50.25), ("ALIANZA FUERZA PATRIA", 34.29), ("FTE. DE IZQUIERDA Y DE TRABAJADORES - UNIDAD", 4.96)],
    "893": [("ALIANZA LA LIBERTAD AVANZA", 59.75), ("ALIANZA FUERZA PATRIA", 26.70), ("ALIANZA SOMOS BUENOS AIRES", 4.11)],
    "894": [("ALIANZA LA LIBERTAD AVANZA", 72.87), ("ALIANZA FUERZA PATRIA", 14.59), ("ALIANZA SOMOS BUENOS AIRES", 3.62)],
    "895": [("ALIANZA LA LIBERTAD AVANZA", 75.30), ("ALIANZA FUERZA PATRIA", 11.91), ("ALIANZA SOMOS BUENOS AIRES", 3.56)],
}


def load() -> None:
    con = get_connection()
    apply_schema(con)
    con.execute("BEGIN TRANSACTION")

    con.execute(
        """
        INSERT INTO core.elecciones
            (id, nombre, tipo, ambito, fecha, anio, categoria_id, categoria_nombre,
             id_eleccion_dine, id_distrito_dine, fuente, eleccion_comparable_id)
        VALUES (?, ?, 'GENERAL', 'PROVINCIAL', '2025-09-07', 2025, ?, ?, NULL, NULL, 'JEP_PBA', NULL)
        ON CONFLICT (id) DO NOTHING
        """,
        [
            ELECCION_ID,
            "Senadores Provinciales 2025 - San Isidro (PARCIAL, no definitivo)",
            CATEGORIA_ID,
            "Senadores Provinciales (1ra Sección)",
        ],
    )

    for nombre_fuerza, fuerza_id in FUERZAS.items():
        # nombre_normalizado normalizado (sin "ALIANZA", etc.) para que el comparador la
        # empareje con la misma fuerza en elecciones de otras fuentes/años — ver
        # app/core/fuerzas.py. nombre_en_boleta abajo conserva el nombre oficial tal cual.
        con.execute(
            """
            INSERT INTO core.fuerzas_politicas (id, nombre_normalizado, color_hex) VALUES (?, ?, NULL)
            ON CONFLICT (id) DO UPDATE SET nombre_normalizado = excluded.nombre_normalizado
            """,
            [fuerza_id, normalizar_nombre_fuerza(nombre_fuerza)],
        )
        con.execute(
            """
            INSERT INTO core.fuerzas_por_eleccion (fuerza_id, eleccion_id, nombre_en_boleta)
            VALUES (?, ?, ?) ON CONFLICT (fuerza_id, eleccion_id) DO NOTHING
            """,
            [fuerza_id, ELECCION_ID, nombre_fuerza],
        )

    con.execute("DELETE FROM core.resultados_circuito WHERE eleccion_id = ?", [ELECCION_ID])
    con.execute("DELETE FROM core.resultados_circuito_totales WHERE eleccion_id = ?", [ELECCION_ID])

    for circuito_id, filas in RESULTADOS_POR_CIRCUITO.items():
        for nombre_fuerza, pct in filas:
            con.execute(
                "INSERT INTO core.resultados_circuito (eleccion_id, circuito_id, fuerza_id, votos, votos_pct) VALUES (?, ?, ?, NULL, ?)",
                [ELECCION_ID, circuito_id, FUERZAS[nombre_fuerza], pct],
            )

        ganador_nombre, ganador_pct = filas[0]
        segundo_pct = filas[1][1] if len(filas) > 1 else None
        diferencia = round(ganador_pct - segundo_pct, 2) if segundo_pct is not None else None

        con.execute(
            """
            INSERT INTO core.resultados_circuito_totales
                (eleccion_id, circuito_id, mesas_totalizadas, electores, votantes,
                 votos_positivos, votos_blanco, votos_nulos, votos_recurridos_comando_impugnados,
                 participacion_pct, ganador_fuerza_id, diferencia_1ro_2do_pct)
            VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            [ELECCION_ID, circuito_id, FUERZAS[ganador_nombre], diferencia],
        )

    # Agregado a nivel San Isidro completo, para el banner "todas las fuerzas" del modo
    # comparar (comparacion.py lee marts.agregados_territoriales nivel='municipio'). Sin
    # conteo de votos por circuito no se puede ponderar por electores — se aproxima con el
    # promedio simple de % entre los 10 circuitos, igual que hace el frontend para esta misma
    # elección (ver lib/format.ts / DetailPanel.aggregateAll). `votos` queda NULL a propósito.
    con.execute("DELETE FROM marts.agregados_territoriales WHERE eleccion_id = ? AND nivel = 'municipio'", [ELECCION_ID])
    pct_sum: dict[str, float] = {}
    for filas in RESULTADOS_POR_CIRCUITO.values():
        for nombre_fuerza, pct in filas:
            pct_sum[nombre_fuerza] = pct_sum.get(nombre_fuerza, 0.0) + pct
    n = len(RESULTADOS_POR_CIRCUITO)
    for nombre_fuerza, suma in pct_sum.items():
        con.execute(
            """
            INSERT INTO marts.agregados_territoriales (nivel, nivel_id, eleccion_id, fuerza_id, votos, votos_pct, participacion_pct)
            VALUES ('municipio', ?, ?, ?, NULL, ?, NULL)
            """,
            [SAN_ISIDRO_INDEC, ELECCION_ID, FUERZAS[nombre_fuerza], round(suma / n, 2)],
        )

    con.execute("COMMIT")
    con.close()
    print(f"Carga parcial completa para {ELECCION_ID} — {len(RESULTADOS_POR_CIRCUITO)} circuitos, sin electores/mesas/participación.")


if __name__ == "__main__":
    load()
