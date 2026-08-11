import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import elecciones, mapa

app = FastAPI(title="San Isidro Electoral Intelligence API", version="0.1.0")

# El frontend en dev pasa por el proxy de Vite (mismo origen) — estos 2 solo importan para pegarle
# directo a la API desde el navegador sin proxy. En producción, el frontend vive en GitHub Pages
# (origen distinto al backend en Render), así que ese origen tiene que estar permitido explícito.
# CORS_ALLOWED_ORIGIN (env var, seteada en Render) es la URL de Pages, p.ej.
# "https://facugarces.github.io" — sin path, CORS matchea por esquema+host+puerto nomás.
_allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if extra_origin := os.environ.get("CORS_ALLOWED_ORIGIN"):
    _allowed_origins.append(extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(elecciones.router, prefix="/api/v1")
app.include_router(mapa.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
