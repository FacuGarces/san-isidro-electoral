"""Normalización de nombre de fuerza política — un solo punto de verdad usado por todos los
loaders (`load_circuito_categoria.py`, el one-off de Senadores PBA, etc.) al escribir
`core.fuerzas_politicas.nombre_normalizado`.

Por qué hace falta: el motor de comparación (`app/repositories/comparacion.py`) empareja
circuito+fuerza entre dos elecciones por este nombre, no por `fuerza_id` (que además difiere
entre fuentes para la misma fuerza real — DINE nacional, DINE 2025 y la Junta Electoral PBA usan
3 numeraciones distintas). Desde 2025 DINE empezó a nombrar a las mismas marcas con variantes de
string ("ALIANZA LA LIBERTAD AVANZA" en vez de "LA LIBERTAD AVANZA", "FTE." en vez de "FRENTE")
— sin normalizar, el comparador las trata como dos fuerzas distintas y el swing sale roto (una
"desaparece" del 100% y la otra "aparece" del 0%, en vez de mostrar el cambio real).

Regla: se normalizan casos donde el nombre es *literalmente* la misma fuerza con formato
distinto (prefijo "ALIANZA", abreviatura "FTE." vs "FRENTE"), y además los rebrandings de marca
confirmados explícitamente por el usuario — nunca una fusión de marcas por cuenta propia sin
que el usuario lo pida (ver docs/DATA_SOURCES.md para el historial de esta decisión).

- "FUERZA PATRIA" (2025) = "UNION POR LA PATRIA" (2023): confirmado por el usuario 2026-08-10,
  es el mismo espacio político kirchnerista/peronista con la marca renombrada para 2025, no una
  alianza nueva sin relación. Se guarda bajo el nombre histórico "UNION POR LA PATRIA" (el que
  ya usan PASO/Generales/Ballotage 2023) para que la serie completa quede bajo un solo nombre."""

_ALIAS_EXACTO = {
    "FTE. DE IZQUIERDA Y DE TRABAJADORES - UNIDAD": "FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD",
    "FUERZA PATRIA": "UNION POR LA PATRIA",
}


def normalizar_nombre_fuerza(nombre: str) -> str:
    nombre = nombre.strip().upper()
    if nombre.startswith("ALIANZA "):
        nombre = nombre[len("ALIANZA ") :]
    return _ALIAS_EXACTO.get(nombre, nombre)
