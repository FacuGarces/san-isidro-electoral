"""Carga puntual (no genérica) — Concejales 2025, San Isidro, PARCIAL.

Mismo origen y mismas limitaciones que `load_senadores_pba_2025_parcial.py` — leer ese archivo
primero. Fuente: capturas de pantalla de la app oficial "Elecciones Bonaerenses 2025"
(ar.gob.gba.eleccionesbonaerenses2025), provistas por el usuario el 2026-08-10 (Senadores) y
2026-08-11 (Concejales, este archivo). Ver docs/DATA_SOURCES.md, sección "Senadores/Concejales
2025", para el detalle completo de la investigación de por qué esto no se puede cargar por el
patrón genérico (el sistema de la Junta Electoral PBA nunca tabuló Concejales por circuito, solo
por municipio — ahí sí hay un PDF definitivo real, `escrutinio-definitivo-2025/concejales/
2025106.pdf`, pero sin desglose por circuito).

Diferencia con Senadores: acá aparece una fuerza nueva, "ACCION VECINAL SAN ISIDRO ES DISTINTO"
— una lista puramente local (compite solo por Concejal en San Isidro, no en la boleta de
Senadores de la 1ra Sección), sin código de alianza provincial conocido. Los otros 2 códigos
(`pba2206` LLA, `pba2200` Fuerza Patria/Unión por la Patria) se reusan tal cual del loader de
Senadores — son códigos de alianza a nivel PBA, no cambian entre categorías de una misma
elección. Para la lista local se usa un id propio (`local2025106_accion_vecinal`, prefijo
`local<código de distrito>_` a propósito) en vez de inventar un número de agrupación que
aparente ser oficial sin haberlo verificado.

Si en algún momento aparece una fuente real (definitiva, por circuito) para esto, hay que borrar
esta elección (`DELETE FROM core.elecciones WHERE id = 'CONCEJALES2025PBA_PARCIAL'` — cascadea
al resto por eleccion_id) y cargarla con el patrón normal.

Limitaciones conocidas de esta carga (por eso "PARCIAL" en el id y en el nombre):
- Las capturas muestran "Escrutado" entre 93,93% y 100% según el circuito, no 100% parejo — no es
  el escrutinio definitivo (ese sí existe, pero solo a nivel San Isidro completo, no por
  circuito — ver el PDF oficial citado en DATA_SOURCES.md).
- Cada tarjeta muestra máximo 3 fuerzas (las más votadas) — nunca suma 100%, faltan las fuerzas
  chicas.
- Sin electores, mesas, participación ni votos en blanco/nulos por circuito.
- `votos` queda NULL en core.resultados_circuito — solo tenemos el %.

Uso:
    PYTHONPATH=. python3 etl/load_concejales_pba_2025_parcial.py
"""

from app.core.db import apply_schema, get_connection
from app.core.fuerzas import normalizar_nombre_fuerza
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC

ELECCION_ID = "CONCEJALES2025PBA_PARCIAL"
CATEGORIA_ID = 10  # "Concejal", mismo id que usa la tabla de categoriaId en docs/DATA_SOURCES.md

# (nombre_normalizado tal cual lo mostró la app) -> fuerza_id.
FUERZAS = {
    "ALIANZA LA LIBERTAD AVANZA": "pba2206",
    "ALIANZA FUERZA PATRIA": "pba2200",
    "ACCION VECINAL SAN ISIDRO ES DISTINTO": "local2025106_accion_vecinal",
}

# circuito_id -> [(fuerza, pct), ...] ordenados como los mostró la app (1ro, 2do, 3ro).
# Transcripto a mano de las capturas de pantalla, 2026-08-11.
RESULTADOS_POR_CIRCUITO: dict[str, list[tuple[str, float]]] = {
    "887": [("ALIANZA LA LIBERTAD AVANZA", 59.50), ("ALIANZA FUERZA PATRIA", 15.08), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 12.41)],
    "888": [("ALIANZA LA LIBERTAD AVANZA", 52.81), ("ALIANZA FUERZA PATRIA", 18.94), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 14.18)],
    "889": [("ALIANZA LA LIBERTAD AVANZA", 49.62), ("ALIANZA FUERZA PATRIA", 24.31), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 13.53)],
    "890": [("ALIANZA LA LIBERTAD AVANZA", 56.19), ("ALIANZA FUERZA PATRIA", 19.48), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 11.93)],
    "891": [("ALIANZA LA LIBERTAD AVANZA", 52.35), ("ALIANZA FUERZA PATRIA", 19.04), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 16.32)],
    "892": [("ALIANZA LA LIBERTAD AVANZA", 38.58), ("ALIANZA FUERZA PATRIA", 33.24), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 16.81)],
    "0892A": [("ALIANZA LA LIBERTAD AVANZA", 39.70), ("ALIANZA FUERZA PATRIA", 28.55), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 19.11)],
    "893": [("ALIANZA LA LIBERTAD AVANZA", 53.39), ("ALIANZA FUERZA PATRIA", 23.21), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 11.87)],
    "894": [("ALIANZA LA LIBERTAD AVANZA", 62.28), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 14.85), ("ALIANZA FUERZA PATRIA", 12.10)],
    "895": [("ALIANZA LA LIBERTAD AVANZA", 66.65), ("ALIANZA FUERZA PATRIA", 11.41), ("ACCION VECINAL SAN ISIDRO ES DISTINTO", 11.10)],
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
        VALUES (?, ?, 'GENERAL', 'MUNICIPAL', '2025-09-07', 2025, ?, ?, NULL, NULL, 'JEP_PBA', NULL)
        ON CONFLICT (id) DO NOTHING
        """,
        [
            ELECCION_ID,
            "Concejales 2025 - San Isidro (PARCIAL, no definitivo)",
            CATEGORIA_ID,
            "Concejales",
        ],
    )

    for nombre_fuerza, fuerza_id in FUERZAS.items():
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

        filas_ordenadas = sorted(filas, key=lambda f: f[1], reverse=True)
        ganador_nombre, ganador_pct = filas_ordenadas[0]
        segundo_pct = filas_ordenadas[1][1] if len(filas_ordenadas) > 1 else None
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
    # comparar. Sin conteo de votos por circuito no se puede ponderar por electores — se
    # aproxima con el promedio simple de % entre los 10 circuitos, igual que Senadores.
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
