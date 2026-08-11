# San Isidro Electoral Intelligence

Plataforma de inteligencia electoral para el partido de San Isidro (Buenos Aires). Ver
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para el diseño completo y
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) para el detalle de las fuentes oficiales usadas.

## Estado actual

- Datos cargados: PASO/Generales/Ballotage 2023 (Presidente/a e Intendente/a), Concejales y
  Senadores Provinciales 2025 (parcial) y Diputados Nacionales 2025 — a nivel circuito, para los
  10 circuitos de San Isidro. Detalle completo en [CLAUDE.md](CLAUDE.md) y
  [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
- Backend: FastAPI sobre DuckDB (`backend/`).
- Frontend: React + Vite + MapLibre, mapa real con calles de OpenStreetMap (`frontend/`).

## Cómo correrlo

### 1. Backend

```bash
cd backend
source ../.venv/bin/activate   # o: python3 -m venv ../.venv && pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --port 8000 --reload
```

Verificar: `curl http://127.0.0.1:8000/api/v1/health` → `{"status":"ok"}`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Abre en `http://localhost:5173`. El dev server tiene un proxy configurado (`vite.config.ts`) que
redirige `/api` al backend en `:8000`, así que ambos tienen que estar corriendo a la vez.

## Actualizar / recargar datos

```bash
cd backend
source ../.venv/bin/activate
PYTHONPATH=. python3 importers/sources/dine/import_paso_2023_san_isidro.py   # baja raw de DINE
PYTHONPATH=. python3 etl/load_paso_2023_san_isidro.py                        # carga a DuckDB
```

## Deploy (GitHub Pages + Render)

El frontend y el backend viven en hosts separados — Pages es 100% estático, no puede correr
FastAPI/DuckDB.

### Backend → Render

1. En [render.com](https://render.com), "New" → "Blueprint", conectá este repo. Ya tiene
   [`render.yaml`](render.yaml) (plan free, `rootDir: backend`).
2. Una vez creado, copiá la URL pública que te da Render (algo como
   `https://san-isidro-electoral-api.onrender.com`).
3. En el servicio de Render, seteá la variable de entorno `CORS_ALLOWED_ORIGIN` con la URL de
   Pages (paso siguiente), p.ej. `https://<tu-usuario>.github.io` (sin path).
4. El plan free "duerme" sin tráfico — la primera request después de un rato de inactividad
   tarda ~30-50s en despertar, es esperable.

### Frontend → GitHub Pages

1. En este repo en GitHub: Settings → Pages → Source → "GitHub Actions" (ya hay un workflow,
   [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml), que hace el build
   y el deploy solo con esto).
2. Settings → Secrets and variables → Actions → pestaña **Variables** → agregar
   `VITE_API_BASE` = la URL de Render del paso anterior (sin `/` final).
3. Volver a correr el workflow (push a `main`, o "Run workflow" a mano) para que tome la
   variable nueva.
4. Página final: `https://<tu-usuario>.github.io/<nombre-del-repo>/`.

## Notas técnicas

- **Versiones de Vite/MapLibre**: se fijaron a `vite@6.4.3` y `maplibre-gl@5.24.0` a propósito.
  Las versiones más nuevas (Vite 8.x, MapLibre 6.x) tienen, al momento de escribir esto, un bug de
  empaquetado del Web Worker de MapLibre en modo dev que deja el mapa sin cargar tiles. Si en el
  futuro se actualizan estas dependencias, verificar que el mapa siga cargando calles antes de
  confirmar el upgrade.
- **`.claude/launch.json`**: vive en `~/.claude/launch.json` (carpeta home), no en este repo,
  porque ese es el directorio raíz que usa la herramienta de preview de Claude Code en esta
  máquina. Contiene la entrada `san-isidro-frontend` para levantar el frontend.
