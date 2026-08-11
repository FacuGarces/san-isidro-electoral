import time

import requests

from app.core.config import settings

DISTRITO_BUENOS_AIRES = 2

# tipoEleccion en la API de DINE
TIPO_ELECCION = {
    "PASO": 1,
    "GENERAL": 2,
    "BALLOTAGE": 3,
}

# categoriaId (= idCargo) confirmado desde el frontend de resultados.gob.ar
CATEGORIA_PRESIDENTE = 1


class DineClient:
    def __init__(self, base_url: str = settings.dine_api_base, timeout: int = settings.request_timeout_seconds):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str, params: dict, retries: int = 3) -> dict:
        url = f"{self.base_url}{path}"
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                time.sleep(1.5 * attempt)
        raise RuntimeError(f"Fallo al consultar {url} con params={params}: {last_error}")

    def get_resultados_circuito(self, anio: int, tipo_eleccion: int, categoria_id: int, circuito_id_dine: str, distrito_id: int = DISTRITO_BUENOS_AIRES) -> dict:
        """Totales agregados (todas las mesas) de un circuito. circuito_id_dine debe venir
        zero-padded a 5 caracteres, ver docs/DATA_SOURCES.md."""
        params = {
            "anioEleccion": anio,
            "tipoRecuento": 1,
            "tipoEleccion": tipo_eleccion,
            "categoriaId": categoria_id,
            "distritoId": distrito_id,
            "circuitoId": circuito_id_dine,
        }
        return self._get("/resultados/getResultados", params)

    def get_totalizado_distrito(self, anio: int, id_eleccion: int, id_cargo: int, id_distrito: int = DISTRITO_BUENOS_AIRES) -> dict:
        params = {
            "año": anio,
            "recuento": "Provisorio",
            "idEleccion": id_eleccion,
            "idCargo": id_cargo,
            "idDistrito": id_distrito,
        }
        return self._get("/resultado/totalizado", params)

    def get_mapa_departamentos(self, anio: int, id_eleccion: int, id_cargo: int, id_indra_provincia: str = "02", id_distrito: int = DISTRITO_BUENOS_AIRES) -> dict:
        params = {
            "año": anio,
            "recuento": "Provisorio",
            "idEleccion": id_eleccion,
            "idCargo": id_cargo,
            "idDistrito": id_distrito,
            "id_indra": id_indra_provincia,
            "tipo": "departamentos",
            "minimizado": "true",
        }
        return self._get("/mapas", params)
