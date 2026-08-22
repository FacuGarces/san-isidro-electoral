import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import elecciones, mapa

app = FastAPI(title="San Isidro Electoral Intelligence API", version="0.1.0")

# El frontend en dev pasa por el proxy de Vite (mismo origen) — estos 2 solo importan para pegarle
# directo a la API desde el navegador sin proxy. En producción, el frontend vive en el Panel de
# Gestión (Netlify, https://panel-de-gestion-lla-si.netlify.app) — origen distinto al backend en
# Render — así que ese origen tiene que estar permitido explícito. CORS_ALLOWED_ORIGIN (env var,
# seteada en Render) acepta uno o varios orígenes separados por coma, p.ej.
# "https://panel-de-gestion-lla-si.netlify.app,https://facugarces.github.io" — sin path, CORS
# matchea por esquema+host+puerto nomás.
_allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if extra_origins := os.environ.get("CORS_ALLOWED_ORIGIN"):
    _allowed_origins.extend(o.strip() for o in extra_origins.split(",") if o.strip())

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
