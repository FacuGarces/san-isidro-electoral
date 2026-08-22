"""Importer — mapeo mesa -> escuela (local de votación), San Isidro.

Ver docs/DATA_SOURCES.md, sección "Nivel mesa (escuela)". El ZIP de datos.gob.ar usado para
cargar una elección con `import_from_bulk_csv.py` (2025 en adelante) trae, además del CSV de
resultados, un archivo separado `localesDeVotacionyMesas.csv` con nombre/dirección/localidad de
cada local por mesa — el mapeo mesa->escuela que 2023 nunca resolvió, disponible recién desde
2025. `import_from_bulk_csv.py` extrae solo el CSV de resultados del ZIP y descarta el resto;
este script extrae ese otro miembro por separado (con su propio cache).

Cruza por `mesa_id` (normalizado a entero — el archivo de locales lo trae zero-padded a 5
dígitos, el de resultados sin padding) contra el CSV de resultados ya cacheado por
`import_from_bulk_csv.py`, para heredar el `circuito_id` (el archivo de locales solo trae
`seccion_id`, no circuito). Geocodifica cada escuela ÚNICA (no cada mesa — muchas mesas
comparten local) contra Nominatim (OpenStreetMap), 1 request/seg respetando su política de uso.

Uso (Diputados Nacionales 2025, San Isidro):
    PYTHONPATH=. python3 importers/sources/dine/import_locales_votacion.py \\
        --csv-url https://datos.mininterior.gob.ar/dataset/947e871a-650e-4b63-8939-ecb29acb717c/resource/a24110fb-bfcf-47a6-8aa7-2e53dab9caf5/download/elecciones_legislativas_2025.zip \\
        --resultados-csv-name resultados2025.csv \\
        --eleccion-id DIPUTADOS2025
"""

import argparse
import csv
import io
import json
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.core.config import settings
from importers.sources.dine.circuitos import SAN_ISIDRO_INDEC, load_circuitos_municipio

DISTRITO_ID_BUENOS_AIRES = "02"
SECCION_NOMBRE_SAN_ISIDRO = "SAN ISIDRO"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim exige un User-Agent identificable con contacto — sin esto responde 403.
NOMINATIM_USER_AGENT = "san-isidro-electoral-intelligence (uso interno, sin publicar; contacto: repo GitHub FacuGarces/san-isidro-electoral)"


def _download_locales_csv(csv_url: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / "localesDeVotacionyMesas.csv"
    if cached.exists():
        print(f"  (ya descargado, usando cache en {cached})")
        return cached
    print(f"  descargando {csv_url} ...")
    resp = requests.get(csv_url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("localesDeVotacionyMesas.csv") as src, open(cached, "wb") as dst:
            dst.write(src.read())
    return cached


def _mesa_to_circuito(resultados_csv_path: Path) -> dict[int, str]:
    """mesa_id (int) -> circuito_id (id normalizado, el mismo que usa core.circuitos.id), solo
    para los circuitos de San Isidro. `mesa_id` NO es único en toda la provincia — se reinicia
    por circuito en otros municipios (confirmado: cruzar sin este filtro pisó el mapeo de
    San Isidro con mesas de otro circuito que reusaba el mismo mesa_id) — hay que restringir a
    los circuitos objetivo ANTES de armar el diccionario, no después."""
    circuitos = load_circuitos_municipio(SAN_ISIDRO_INDEC)
    id_dine_to_id = {c.id_dine: c.id for c in circuitos}
    ids_dine = set(id_dine_to_id)

    mesa_circuito: dict[int, str] = {}
    with open(resultados_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["distrito_id"] != "2":
                continue
            circuito_dine = row["circuito_id"]
            if circuito_dine not in ids_dine:
                continue
            mesa_circuito[int(row["mesa_id"])] = id_dine_to_id[circuito_dine]
    return mesa_circuito


def _clean_direccion(direccion: str) -> str:
    # El símbolo "N°"/"Nº" rompe el parser de Nominatim (confirmado a mano: la misma dirección
    # geocodifica bien sin el símbolo, con el número pelado) — sacarlo es lo único que hace
    # falta en la mayoría de los casos, la fuente ya trae orden calle+altura razonable.
    return re.sub(r"N[°º]\s*", "", direccion).strip()


def _query_nominatim(query: str) -> tuple[float, float, str] | None:
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1, "countrycodes": "ar"},
        headers={"User-Agent": NOMINATIM_USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    r = results[0]
    return float(r["lat"]), float(r["lon"]), r.get("type", "")


def _geocode(direccion: str, localidad: str) -> tuple[float, float, str] | None:
    direccion = _clean_direccion(direccion)
    geo = _query_nominatim(f"{direccion}, {localidad}, San Isidro, Buenos Aires, Argentina")
    if geo:
        return geo
    time.sleep(1.1)
    # Fallback: muchas de las que fallan son direcciones "entre calles" (sin altura, p.ej.
    # "CAMINO MORON E/ PANAMERICANA Y FIGUEROA ALCORTA") o con abreviaturas que Nominatim no
    # resuelve con la altura puesta — probar solo con el primer tramo de calle (sin número ni
    # "E/ ... Y ...") da precisión de calle en vez de nada, mejor que dejar el punto vacío.
    calle = re.split(r"\s+(?:E/|ENTRE)\s+", direccion, maxsplit=1)[0]
    calle = re.sub(r"\d+\s*$", "", calle).strip(" ,")
    if calle and calle != direccion:
        return _query_nominatim(f"{calle}, {localidad}, San Isidro, Buenos Aires, Argentina")
    return None


def run(csv_url: str, resultados_csv_name: str, eleccion_id: str) -> Path:
    bulk_cache_dir = settings.data_raw_dir / "dine" / "_bulk_csv_cache"
    locales_cache_dir = settings.data_raw_dir / "dine" / "_locales_votacion_cache"

    locales_csv = _download_locales_csv(csv_url, locales_cache_dir)
    resultados_csv = bulk_cache_dir / resultados_csv_name
    if not resultados_csv.exists():
        raise FileNotFoundError(
            f"No se encontró {resultados_csv} — correr primero import_from_bulk_csv.py para "
            "esta elección (así queda cacheado el CSV de resultados que este script necesita "
            "para heredar circuito_id por mesa)."
        )

    print("  cruzando mesa_id -> circuito_id desde el CSV de resultados ya cacheado...")
    mesa_circuito = _mesa_to_circuito(resultados_csv)

    print("  leyendo locales de votación de San Isidro...")
    escuelas: dict[str, dict] = {}
    with open(locales_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["distrito_id"] != DISTRITO_ID_BUENOS_AIRES:
                continue
            if row["seccion_nombre"] != SECCION_NOMBRE_SAN_ISIDRO:
                continue
            mesa_id = int(row["mesa_id"])
            circuito_id = mesa_circuito.get(mesa_id)
            if circuito_id is None:
                # Mesa listada en el padrón de locales pero sin resultado cargado (mesa que no
                # totalizó, o de otro cargo/recuento) — no podemos ubicarla en un circuito, se
                # descarta en vez de adivinar.
                continue
            codigo = row["localvotacion_codigo"]
            escuela = escuelas.setdefault(
                codigo,
                {
                    "codigo": codigo,
                    "nombre": row["localvotacion_nombre"],
                    "direccion": row["localvotacion_direccion"],
                    "localidad": row["localvotacion_localidad"],
                    "mesas": [],
                },
            )
            escuela["mesas"].append(
                {"numero_mesa": str(mesa_id), "circuito_id": circuito_id, "electores": int(row["mesa_electores"])}
            )

    print(f"  {len(escuelas)} escuelas únicas, {sum(len(e['mesas']) for e in escuelas.values())} mesas.")

    # Reusar geocoding ya resuelto en una corrida anterior de esta misma elección — evita
    # volver a pegarle a Nominatim por las que ya salieron bien (1 req/seg es lento con 125+
    # escuelas, y no tiene sentido re-geocodificar lo que ya funcionó solo porque se está
    # reintentando el puñado que falló).
    ya_geocodificadas: dict[str, dict] = {}
    base_dir = settings.data_raw_dir / "dine" / eleccion_id
    if base_dir.exists():
        for run_dir in sorted(base_dir.iterdir()):
            prev_file = run_dir / "locales_votacion.json"
            if prev_file.exists():
                prev = json.loads(prev_file.read_text())
                for e in prev["escuelas"]:
                    if e.get("lat") is not None:
                        ya_geocodificadas[e["codigo"]] = e

    print(f"  geocodificando contra Nominatim (1 req/seg) — {len(ya_geocodificadas)} ya resueltas en corridas previas...")
    sin_geocodificar = 0
    for i, escuela in enumerate(escuelas.values(), 1):
        previa = ya_geocodificadas.get(escuela["codigo"])
        if previa:
            escuela["lat"], escuela["lon"], escuela["precision_geocoding"] = previa["lat"], previa["lon"], previa["precision_geocoding"]
            print(f"    [{i}/{len(escuelas)}] {escuela['nombre']} -> OK (cache)")
            continue
        geo = _geocode(escuela["direccion"], escuela["localidad"])
        if geo:
            escuela["lat"], escuela["lon"], escuela["precision_geocoding"] = geo
        else:
            escuela["lat"] = escuela["lon"] = escuela["precision_geocoding"] = None
            sin_geocodificar += 1
        print(f"    [{i}/{len(escuelas)}] {escuela['nombre']} -> {'OK' if geo else 'sin resultado'}")
        time.sleep(1.1)

    if sin_geocodificar:
        print(f"  ADVERTENCIA: {sin_geocodificar} escuela(s) sin geocodificar, quedan sin lat/lon (revisar a mano).")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = settings.data_raw_dir / "dine" / eleccion_id / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "locales_votacion.json"
    out_file.write_text(json.dumps({"eleccion_id": eleccion_id, "escuelas": list(escuelas.values())}, ensure_ascii=False, indent=2))
    print(f"\nOK. Datos crudos guardados en {out_file}")
    return out_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-url", required=True, help="URL del .zip publicado en datos.gob.ar")
    parser.add_argument("--resultados-csv-name", required=True, help="Nombre del CSV de resultados ya cacheado por import_from_bulk_csv.py")
    parser.add_argument("--eleccion-id", required=True)
    args = parser.parse_args()
    run(args.csv_url, args.resultados_csv_name, args.eleccion_id)
