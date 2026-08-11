from fastapi import APIRouter

from app.repositories.elecciones import list_elecciones

router = APIRouter(prefix="/elecciones", tags=["elecciones"])


@router.get("")
def get_elecciones():
    return list_elecciones()
