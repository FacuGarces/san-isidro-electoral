from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.repositories.comparacion import get_comparacion_geojson
from app.repositories.mapa import get_circuitos_geojson, get_establecimientos_geojson

router = APIRouter(prefix="/mapa", tags=["mapa"])


@router.get("/circuitos")
def get_circuitos(eleccion_id: str):
    geojson = get_circuitos_geojson(eleccion_id)
    if not geojson["features"]:
        raise HTTPException(status_code=404, detail=f"Sin datos para eleccion_id={eleccion_id!r}")
    return JSONResponse(geojson)


@router.get("/establecimientos")
def get_establecimientos(eleccion_id: str):
    # A diferencia de /circuitos, acá una FeatureCollection vacía es una respuesta válida (la
    # mayoría de las elecciones no tienen nivel mesa cargado todavía) — el frontend simplemente
    # no muestra la capa, no es un 404.
    return JSONResponse(get_establecimientos_geojson(eleccion_id))


@router.get("/comparacion")
def get_comparacion(actual: str, base: str):
    geojson = get_comparacion_geojson(actual, base)
    if geojson is None:
        raise HTTPException(status_code=404, detail=f"actual={actual!r} o base={base!r} no existen")
    if not geojson["features"]:
        raise HTTPException(status_code=404, detail=f"Sin datos para actual={actual!r}, base={base!r}")
    return JSONResponse(geojson)
