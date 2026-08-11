"""Mapeo de candidatos (nombre de persona + foto) para listas/fuerzas de San Isidro.

DINE no expone el nombre de la persona candidata: solo el nombre de fantasía de la lista/interna
(p.ej. "LA FUERZA DEL CAMBIO") o el nombre de la fuerza política. Este mapeo es manual y
deliberadamente incompleto — solo se completan candidatos verificados contra una fuente
periodística confiable (ver frontend/public/candidatos/LICENSES.md). Mejor sin foto/nombre que
mal atribuido a una persona real.

Clave para PASO: (categoria_id, lista_numero) — la lista/interna dentro de una fuerza.
Clave para Generales: (categoria_id, nombre_fuerza) — ahí ya no hay interna, es la fuerza misma.
"""

_FOTO = "/candidatos"

CANDIDATO_POR_LISTA: dict[tuple[int, str], dict] = {
    # Presidente/a (categoria_id=1) — PASO 2023
    (1, "3007"): {"nombre": "Horacio Rodríguez Larreta", "foto": f"{_FOTO}/larreta.jpg"},
    (1, "3008"): {"nombre": "Patricia Bullrich", "foto": f"{_FOTO}/bullrich.jpg"},
    (1, "3005"): {"nombre": "Sergio Massa", "foto": f"{_FOTO}/massa.jpg"},
    (1, "3006"): {"nombre": "Juan Grabois", "foto": f"{_FOTO}/grabois.png"},
    (1, "3016"): {"nombre": "Javier Milei", "foto": f"{_FOTO}/milei.jpg"},
    (1, "3009"): {"nombre": "Myriam Bregman", "foto": f"{_FOTO}/bregman.jpg"},
    (1, "3001"): {"nombre": "Juan Schiaretti", "foto": f"{_FOTO}/schiaretti.png"},
    # Intendente/a San Isidro (categoria_id=7) — PASO 2023
    (7, "3644"): {"nombre": "Ramón Lanús", "foto": f"{_FOTO}/lanus.jpg"},
    (7, "3602"): {"nombre": "Macarena Posse", "foto": f"{_FOTO}/posse.jpg"},
    (7, "3636"): {"nombre": "Eduardo Ruffa", "foto": f"{_FOTO}/ruffa.jpg"},
    (7, "3604"): {"nombre": "Federico Meca", "foto": f"{_FOTO}/meca.jpg"},
    (7, "3612"): {"nombre": "Rodolfo José Paulucci", "foto": f"{_FOTO}/paulucci.jpg"},
}

CANDIDATO_POR_FUERZA: dict[tuple[int, str], dict] = {
    # Presidente/a — Generales 2023 (candidato único, el que ganó la interna)
    (1, "JUNTOS POR EL CAMBIO"): {"nombre": "Patricia Bullrich", "foto": f"{_FOTO}/bullrich.jpg"},
    (1, "UNION POR LA PATRIA"): {"nombre": "Sergio Massa", "foto": f"{_FOTO}/massa.jpg"},
    (1, "LA LIBERTAD AVANZA"): {"nombre": "Javier Milei", "foto": f"{_FOTO}/milei.jpg"},
    (1, "HACEMOS POR NUESTRO PAIS"): {"nombre": "Juan Schiaretti", "foto": f"{_FOTO}/schiaretti.png"},
    (1, "FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD"): {"nombre": "Myriam Bregman", "foto": f"{_FOTO}/bregman.jpg"},
    # Intendente/a San Isidro — Generales 2023
    (7, "JUNTOS POR EL CAMBIO"): {"nombre": "Ramón Lanús", "foto": f"{_FOTO}/lanus.jpg"},
    (7, "UNION POR LA PATRIA"): {"nombre": "Federico Meca", "foto": f"{_FOTO}/meca.jpg"},
    (7, "LA LIBERTAD AVANZA"): {"nombre": "Rodolfo José Paulucci", "foto": f"{_FOTO}/paulucci.jpg"},
}


def candidato_lista(categoria_id: int, lista_numero: str) -> dict | None:
    return CANDIDATO_POR_LISTA.get((categoria_id, lista_numero))


def candidato_fuerza(categoria_id: int, nombre_fuerza: str) -> dict | None:
    return CANDIDATO_POR_FUERZA.get((categoria_id, nombre_fuerza))
