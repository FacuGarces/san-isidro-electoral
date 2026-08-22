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

# Bounding box real de los 10 circuitos de San Isidro (calculado desde
# data/raw/geo_source/circuitos_zip/circuitos-electorales-pba.geojson), con ~0.01° de margen.
# `viewbox`+`bounded=1` restringe TODA búsqueda a esta zona — necesario porque "San Isidro" y
# varios nombres de calle comunes (confirmado con "Alvarado") existen en otras provincias, y sin
# esto Nominatim puede devolver un resultado real pero en el lugar equivocado del país.
SAN_ISIDRO_VIEWBOX = "-58.610,-34.437,-58.469,-34.541"  # left,top,right,bottom (lon,lat,lon,lat)


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


# Títulos personales que la fuente mezcla con el apellido de la calle, en cualquier posición
# (p.ej. "SANTANA MTRO. N° 1551" con el título DESPUÉS del apellido, "GRAL. ALVARADO N°1376" con
# el título ANTES) — Nominatim no los resuelve (los trata como parte del nombre y no encuentra
# la calle), pero SÍ resuelve el apellido solo. Confirmado a mano probando cada uno: sacar el
# título entero (no expandirlo a "General"/"Almirante") recupera la calle real casi siempre.
# "AV."/"AVDA." se dejan (son tipo de vía, no título).
_TITULOS_PERSONALES = r"\b(ALMTE|GRAL|MTRO|PRESB|MONS|CNEL|TTE|CAP|DR|ING|PBRO|FRAY)\.?\b"

# La fuente rotula la colectora de la Panamericana como "RUTA NAC. RN A003 ACCESO NORTE RAMAL
# TIGRE" — Nominatim no tiene ese nombre oficial cargado, pero sí conoce "Panamericana" como
# alias de uso común para la misma vía.
_ACCESO_NORTE = re.compile(r"RUTA\s+NAC\.?\s*RN\s*A0*3\s*ACCESO\s+NORTE(\s+RAMAL\s+\w+)?", re.IGNORECASE)
# "RUTA PROV RP 195 SAN MARTIN LIBERTADOR GRAL. AV." es como la fuente rotula lo que OSM (y el
# uso real) conoce simplemente como "Avenida del Libertador" — ninguna combinación de sacar
# "RUTA PROV RP 195" + el título "GRAL." llega a ese nombre (queda "SAN MARTIN LIBERTADOR AV.",
# que Nominatim no reconoce). Confirmado a mano: buscando el nombre real, las 3 escuelas de esta
# avenida con numeración muy alta (16624/17115/17175/17592) sí tienen match exacto — el problema
# nunca fue que esas alturas no existieran, era el nombre de calle irreconocible.
_LIBERTADOR_GARBLED = re.compile(r"RUTA\s+PROV\.?\s*RP\s*195\s+SAN\s+MARTIN\s+LIBERTADOR\s+GRAL\.?\s*AV\.?", re.IGNORECASE)
# "RUTA PROV RP <número>" (cualquier otra) es una clasificación catastral que nunca aparece en
# el nombre real de la calle — sacarla no cambia el significado de la dirección, solo saca
# ruido que Nominatim no sabe interpretar.
_RUTA_PROV = re.compile(r"RUTA\s+PROV\.?\s*RP\s*\d+\s*", re.IGNORECASE)
# "J.M.MORENO" en Villa Adelina es José María Moreno (confirmado contra OSM, no Domingo
# Faustino Sarmiento ni Mariano Moreno — hay 3 calles "Moreno" distintas en San Isidro, esta
# expansión puntual es la única forma de no adivinar cuál).
_JM_MORENO = re.compile(r"\bJ\.?\s*M\.?\s*MORENO\b", re.IGNORECASE)


def _clean_direccion(direccion: str) -> str:
    # El símbolo "N°"/"Nº" rompe el parser de Nominatim (confirmado a mano: la misma dirección
    # geocodifica bien sin el símbolo, con el número pelado) — sacarlo es lo único que hace
    # falta en la mayoría de los casos, la fuente ya trae orden calle+altura razonable.
    direccion = re.sub(r"N[°º]\s*", "", direccion)
    direccion = _ACCESO_NORTE.sub("Panamericana", direccion)
    direccion = _LIBERTADOR_GARBLED.sub("Avenida del Libertador", direccion)
    direccion = _RUTA_PROV.sub("", direccion)
    direccion = _JM_MORENO.sub("Jose Maria Moreno", direccion)
    direccion = re.sub(_TITULOS_PERSONALES, "", direccion, flags=re.IGNORECASE)
    # Rango de altura ("651/643", casas contiguas que comparten predio) — quedarse con la
    # primera, Nominatim no entiende rangos y cualquiera de las dos cae en el mismo punto real.
    direccion = re.sub(r"(\d+)/\d+", r"\1", direccion)
    # "CALLE [ALTURA] E/ CALLE1 Y CALLE2" — el tramo "E/ ... Y ..." son las calles que cruzan
    # (referencia, no dirección), nunca aporta nada al geocoding y a veces mete un nombre de
    # calle real que confunde a Nominatim. El tramo de ANTES siempre tiene la calle (+ altura si
    # la hay) que realmente importa, sea "entre calles" puro o con altura.
    direccion = re.split(r"\s+(?:E/|ENTRE)\s+", direccion, maxsplit=1)[0]
    return re.sub(r"\s+", " ", direccion).strip(" ,")


def _get_con_reintentos(params: dict) -> list:
    # Nominatim (servicio público, gratuito) corta la conexión de vez en cuando bajo uso
    # sostenido — con 125+ escuelas y hasta 3 intentos cada una, un solo timeout transitorio no
    # debería tirar abajo una corrida de varios minutos. 3 intentos con backoff simple.
    last_exc: Exception | None = None
    for intento in range(3):
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers={"User-Agent": NOMINATIM_USER_AGENT}, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            time.sleep(3 * (intento + 1))
    raise last_exc  # type: ignore[misc]


def _query_nominatim(query: str) -> tuple[float, float, str] | None:
    """Búsqueda de texto libre (`q=`) — Nominatim junta calle+altura como una frase a interpretar
    entera. Confirmado a mano que esto degrada mal para casas de numeración baja/media sobre una
    calle larga que también tiene un POI con nombre (escuela, club): en vez de interpolar la
    altura pedida, cae al POI nombrado más relevante de esa calle e ignora el número — varias
    escuelas EN ESA MISMA calle terminaban todas en el mismo punto (el de la escuela con más
    "importance" en OSM). Ver `_query_nominatim_estructurado`, que no tiene este problema."""
    results = _get_con_reintentos(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "ar", "viewbox": SAN_ISIDRO_VIEWBOX, "bounded": 1}
    )
    if not results:
        return None
    r = results[0]
    return float(r["lat"]), float(r["lon"]), r.get("type", "")


def _query_nominatim_estructurado(street: str, city: str) -> tuple[float, float, str] | None:
    """Búsqueda estructurada (`street=`/`city=`) — separar calle+altura de la localidad en
    campos propios hace que Nominatim SÍ interpole la altura real en vez de caer a un POI
    nombrado de la misma calle. Confirmado a mano: la búsqueda de texto libre colapsaba 3+
    escuelas distintas de una misma calle al mismo punto (el de la escuela más "importante" de
    esa calle en OSM); la estructurada da un punto `type: house` distinto y correcto para cada
    altura. Usar esta como método principal, no como fallback."""
    results = _get_con_reintentos(
        {
            "street": street,
            "city": city,
            "country": "Argentina",
            "format": "json",
            "limit": 1,
            "viewbox": SAN_ISIDRO_VIEWBOX,
            "bounded": 1,
        }
    )
    if not results:
        return None
    r = results[0]
    return float(r["lat"]), float(r["lon"]), r.get("type", "")


def _geocode(direccion: str, localidad: str) -> tuple[float, float, str] | None:
    direccion = _clean_direccion(direccion)
    tiene_altura = bool(re.search(r"\d", direccion))

    if tiene_altura:
        # Estructurada primero (ver docstring): evita el bug de "cae al POI más importante de
        # la calle e ignora la altura" que tiene la búsqueda de texto libre.
        geo = _query_nominatim_estructurado(direccion, localidad)
        if geo:
            return geo
        time.sleep(1.1)
        geo = _query_nominatim_estructurado(direccion, "San Isidro")
        if geo:
            return geo
        time.sleep(1.1)

    geo = _query_nominatim(f"{direccion}, {localidad}, San Isidro, Buenos Aires, Argentina")
    if geo:
        return geo
    time.sleep(1.1)

    if not tiene_altura:
        # "CALLE1 Y CALLE2" (cruce puro, sin altura, p.ej. "BECCO Y GUIDO") — probar solo la
        # primera calle da precisión de calle en vez de nada. Nunca se pierde una altura acá
        # (no la hay), así que no aplica el riesgo de duplicados del bloque de arriba.
        primera_calle = re.split(r"\s+Y\s+", direccion, maxsplit=1)[0].strip(" ,")
        if primera_calle and primera_calle != direccion:
            geo = _query_nominatim(f"{primera_calle}, {localidad}, San Isidro, Buenos Aires, Argentina")
            if geo:
                return geo
        return None

    # Último fallback (solo si SÍ hay altura, para no perderla): cuando la fuente trae
    # "APELLIDO NOMBRE [TÍTULO] ALTURA" (p.ej. "ESQUIU MAMERTO FRAY 2821" — la calle real es
    # "Fray M. Esquiú", solo el apellido importa para el match), un nombre de pila en el medio
    # rompe el match aunque ya se haya sacado el título. Probar solo la primera palabra + la
    # altura (nunca se descarta el número) rescata este patrón sin el riesgo de arriba —
    # estructurada primero, texto libre como último recurso.
    m = re.match(r"(\S+)\b.*?(\d+)\s*$", direccion)
    if m and m.group(1) != direccion:
        calle_altura = f"{m.group(1)} {m.group(2)}"
        geo = _query_nominatim_estructurado(calle_altura, localidad)
        if geo:
            return geo
        time.sleep(1.1)
        return _query_nominatim(f"{calle_altura}, {localidad}, San Isidro, Buenos Aires, Argentina")
    return None


def run(csv_url: str, resultados_csv_name: str, eleccion_id: str, ignorar_cache: bool = False) -> Path:
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
    if not ignorar_cache and base_dir.exists():
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

    # Validación estructural: 2 escuelas reales NUNCA comparten la misma coordenada exacta. Si
    # pasa, es porque Nominatim devolvió un match genérico (calle sin interpolación para esa
    # altura — confirmado a mano: 3 escuelas distintas sobre la misma avenida con alturas muy
    # altas, 17592/17175/17115, quedaban clavadas en el mismo punto) — más engañoso que no
    # geocodificar, porque se ve preciso y no lo es. Invalidar todo el grupo.
    por_coordenada: dict[tuple[float, float], list[dict]] = {}
    for escuela in escuelas.values():
        if escuela["lat"] is not None:
            por_coordenada.setdefault((escuela["lat"], escuela["lon"]), []).append(escuela)
    for coord, grupo in por_coordenada.items():
        if len(grupo) > 1:
            nombres = ", ".join(e["nombre"] for e in grupo)
            print(f"  ADVERTENCIA: {len(grupo)} escuelas con la misma coordenada exacta {coord} (match genérico de Nominatim) — invalidadas: {nombres}")
            for e in grupo:
                e["lat"] = e["lon"] = e["precision_geocoding"] = None
                sin_geocodificar += 1

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
    parser.add_argument(
        "--ignorar-cache",
        action="store_true",
        help="Re-geocodificar TODO desde cero, ignorando resultados de corridas anteriores. "
        "Usar después de un cambio al método de geocoding (p.ej. el bug de búsqueda de texto "
        "libre cayendo al POI más importante de la calle e ignorando la altura) — reusar cache "
        "viejo mezclaría resultados de 2 métodos distintos sin forma de saber cuáles confiar.",
    )
    args = parser.parse_args()
    run(args.csv_url, args.resultados_csv_name, args.eleccion_id, ignorar_cache=args.ignorar_cache)
