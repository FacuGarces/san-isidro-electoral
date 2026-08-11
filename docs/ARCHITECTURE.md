# Plataforma de Inteligencia Electoral — Partido de San Isidro

**Documento de arquitectura técnica — Fase 1 (Planificación)**
Estado: borrador para revisión. No se ha escrito código de aplicación todavía.
Última actualización: 2026-08-07.

---

## 0. Resumen ejecutivo

Se diseña una plataforma de BI electoral territorial, acotada al partido de San Isidro (PBA), que
ingiere datos oficiales de mesa, los normaliza en un modelo histórico comparable entre elecciones,
los georreferencia, y los expone vía API + frontend de mapas/dashboards. La plataforma se piensa
para vivir años y absorber nuevas elecciones y nuevas capas de datos (censales, urbanas) sin
rediseño.

Principio rector: **separar adquisición (scraping/descarga) de modelado (silver/gold) de
consumo (API/frontend)**, para que cada capa pueda evolucionar o romperse sin arrastrar a las demás.

---

## 1. Fechas electorales verificadas

El pedido original tenía una fecha a confirmar. Verificación contra fuentes oficiales (agosto 2026):

| Elección | Fecha | Fuente oficial |
|---|---|---|
| PASO 2023 | 13 de agosto de 2023 | DINE / Ministerio del Interior |
| Elecciones Generales 2023 | 22 de octubre de 2023 | DINE |
| Ballotage 2023 | 19 de noviembre de 2023 | DINE |
| Elección Provincial de Buenos Aires 2025 | **7 de septiembre de 2025** (confirmada, coincide con lo indicado) | [Junta Electoral PBA](https://www.juntaelectoral.gba.gov.ar/escrutinio-definitivo-2025/) / [Chequeado](https://chequeado.com/el-explicador/elecciones-2025-en-la-provincia-de-buenos-aires-preguntas-y-respuestas-sobre-los-comicios-del-7-de-septiembre/) |
| Elección Legislativa Nacional 2025 | **26 de octubre de 2025** (el pedido decía 25 de octubre — **corregido**, fue domingo 26, Decreto 335/2025) | [LA NACION](https://www.lanacion.com.ar/politica/fecha-confirmada-que-dia-son-las-elecciones-legislativas-en-argentina-2025-nid11062025/) / [Argentina.gob.ar](https://www.argentina.gob.ar/elecciones-2025) |

Nota histórica relevante para el modelo de datos: **2025 fue la primera vez desde 1983 que la
elección provincial bonaerense se desdobló de la nacional**, con Boleta Única Papel en la nacional.
Esto implica boletas y circuitos administrados por autoridades distintas (Junta Electoral PBA vs.
DINE/Cámara Nacional Electoral) el mismo año — el modelo de datos debe tratar "elección" como una
entidad completamente independiente por jurisdicción, no asumir que provincial y nacional comparten
mesa/circuito 1:1 en 2025 (en 2023 sí coincidían).

---

## 2. Fuentes de datos oficiales confirmadas

| Elección | Fuente | Acceso |
|---|---|---|
| PASO 2023, Generales 2023, Ballotage 2023, Legislativas Nacionales 2025 | **DINE — Sistema de Publicación de Resultados Electorales**, Ministerio del Interior | API REST pública documentada en [resultados-electorales.argentina.apidocs.ar](https://resultados-electorales.argentina.apidocs.ar/) y portal [resultados.mininterior.gob.ar](https://resultados.mininterior.gob.ar). Dataset espejo en [datos.gob.ar](https://datos.gob.ar/dataset/dine-api-publicacion-resultados-electorales) con documentación técnica + colección Insomnia + "Estándar de Preservación de Datos Electorales". Permite filtrar por distrito/sección/circuito/mesa y exportar CSV. |
| Elección Provincial PBA 2025 | **Junta Electoral de la Provincia de Buenos Aires (JEP)** | Portal oficial [resultados.eleccionesbonaerenses.gba.gob.ar](https://resultados.eleccionesbonaerenses.gba.gob.ar/) (única fuente autorizada por la Junta) + [juntaelectoral.gba.gov.ar](https://www.juntaelectoral.gba.gov.ar/escrutinio-definitivo-2025/) para el escrutinio definitivo. No expone una API pública documentada como la de DINE — requiere ingeniería inversa del tráfico del sitio (requests XHR/JSON del propio front oficial) o scraping estructurado. **Riesgo identificado, ver §12.** |
| Establecimientos de votación (escuelas) | DINE (nombre + dirección aparecen en resultados) + geocoding propio | Georreferenciación no viene dada — se resuelve con Nominatim/Google Geocoding + validación manual para San Isidro (partido acotado, universo de escuelas manejable, ~100-150 establecimientos). |
| Capas futuras (radios censales, INDEC) | INDEC / Municipio de San Isidro (datos abiertos) | Ver §14 "Segunda etapa". |

**No se usan fuentes periodísticas para resultados** — se usan solo para (a) verificar fechas
oficiales cuando el decreto/resolución no es fácil de ubicar directamente, y (b) contexto narrativo
en reportes, nunca como fuente de datos numéricos.

### Padrón electoral — límite legal

Se investigó qué información de padrón es pública. Conclusión: en Argentina el padrón electoral
**no es de descarga masiva pública con datos personales**. La consulta pública permite a cada
ciudadano verificar *su propio* lugar de votación (padrón.gob.ar), y copias certificadas del padrón
completo con nombre/DNI están reservadas a partidos políticos reconocidos y agrupaciones para fines
de fiscalización, bajo marco legal específico (Código Electoral Nacional) — no es un dataset abierto
para scraping automatizado por un tercero.

**Decisión de arquitectura:** la plataforma NO intentará descargar ni almacenar padrón nominal.
Usará únicamente el campo `electores` (cantidad de electores habilitados por mesa) que ya viene
incluido de forma pública y agregada en los propios datos de resultados de DINE/JEP. El modelo de
datos distingue explícitamente entre `electores_habilitados` (agregado, público, por mesa) y
cualquier noción de identidad individual, que nunca se modela. Si en el futuro el usuario obtiene
por vía partidaria legítima un padrón para fiscalización, se define un import path aislado
(`backend/importers/sources/padron_fiscalizacion/`, fuera del alcance de este documento) que en
ningún caso se cruza con resultados a nivel de persona.

---

## 3. Arquitectura general del sistema

```
                    ┌─────────────────────────────────────────────┐
                    │              FUENTES OFICIALES                │
                    │   DINE API   │   JEP PBA (scraping)  │ Geo    │
                    └──────┬───────────────┬──────────────┬────────┘
                           │               │              │
                    ┌──────▼───────────────▼──────────────▼────────┐
                    │  CAPA DE INGESTA (backend/importers)          │
                    │  - 1 módulo por fuente, idempotente           │
                    │  - Escribe RAW inmutable (data/raw/)          │
                    │  - Nunca transforma, solo descarga + hashea   │
                    └──────────────────────┬────────────────────────┘
                                            │
                    ┌───────────────────────▼───────────────────────┐
                    │  CAPA ETL (backend/etl) — bronze→silver→gold   │
                    │  bronze: raw parseado a tablas crudas          │
                    │  silver: normalizado, tipado, validado         │
                    │  gold: agregados, métricas, comparaciones      │
                    └──────────────────────┬────────────────────────┘
                                            │
                    ┌───────────────────────▼───────────────────────┐
                    │  DUCKDB (database/)  — motor analítico único   │
                    │  Esquemas: raw / core / geo / marts            │
                    └──────────────────────┬────────────────────────┘
                                            │
                    ┌───────────────────────▼───────────────────────┐
                    │  API — FastAPI (backend/app)                   │
                    │  Repositorios → Servicios → Routers /api/v1    │
                    └──────────────────────┬────────────────────────┘
                                            │  JSON / GeoJSON
                    ┌───────────────────────▼───────────────────────┐
                    │  FRONTEND — React + TS + Vite                  │
                    │  Mapas (MapLibre) · Dashboard · Comparaciones  │
                    └─────────────────────────────────────────────────┘
```

**Patrón de datos: bronze/silver/gold (medallion architecture) sobre un único motor DuckDB.**
Se elige este patrón (en vez de escribir directo a tablas finales) porque:
- Los datos oficiales de mesa llegan con errores/reaperturas/actas rectificadas → se necesita poder
  re-derivar silver/gold desde bronze sin volver a scrapear.
- Permite auditar exactamente qué vino de la fuente vs. qué se calculó.
- Es el mismo patrón que va a hacer trivial incorporar radios censales/INDEC en el futuro: entran
  como una nueva fuente bronze, no tocan el resto.

**Principio de capas independientes:** ingesta, transformación, servicio y presentación son
paquetes separados con contratos claros (archivos parquet/tablas versionadas entre capas), de forma
que el scraper de JEP se pueda reescribir sin tocar la API, o el frontend se pueda re-hacer sin
tocar el ETL.

---

## 4. Tecnologías elegidas y justificación

| Capa | Tecnología | Por qué |
|---|---|---|
| Frontend | React + TypeScript + Vite | Pedido explícito; Vite da HMR instantáneo, build rápido a `dist/` para hosting estático. |
| Estilos | TailwindCSS | Consistencia de design tokens (violeta #30115E) sin CSS disperso; fácil dark-safe/responsive. |
| Server state | React Query (TanStack Query) | Cachea llamadas a la API, evita loading spinners en cada filtro, invalidación fina — clave para "los filtros no deben recargar la página". |
| Client/UI state | Zustand | Estado de filtros del dashboard (elección, mesa, fuerza, etc.) compartido entre mapa y gráficos sin prop-drilling ni el boilerplate de Redux. |
| Mapas | **MapLibre GL JS** (no Leaflet) | Renderizado vectorial por GPU, maneja miles de mesas + heatmaps con fluidez muy superior a Leaflet (que es DOM/Canvas 2D por capa); soporta MVT tiles a futuro si el dataset crece; sin costo de licencia (a diferencia de Mapbox GL). Leaflet queda descartado por rendimiento a esta escala de capas. |
| Gráficos | Recharts (dashboard) + Plotly solo para vistas estadísticas puntuales (dispersión swing, distribución) | Recharts es liviano y suficiente para el 90% (barras, líneas, rankings); Plotly se reserva para gráficos estadísticos que Recharts no resuelve bien, evitando cargar su bundle pesado en toda la app. |
| Backend | Python + FastAPI | Pedido explícito; tipado con Pydantic, OpenAPI autogenerado, async nativo para I/O de scraping. |
| Procesamiento | pandas, geopandas, numpy, shapely | Pedido explícito; estándar de facto para el pipeline ETL y análisis espacial. |
| Base de datos | **DuckDB** (no SQLite) | Motor analítico columnar, embebido (cero infraestructura), extensión `spatial` madura (lee/escribe GeoJSON, Shapefile, hace joins espaciales), lee Parquet nativamente, y su dialecto SQL es prácticamente un subconjunto de PostgreSQL → **migración a Postgres/PostGIS es un `pg_dump`-equivalente de bajo esfuerzo**, no una reescritura. SQLite se descarta: no tiene tipos espaciales nativos maduros ni es columnar (los reportes de esta plataforma son agregaciones sobre cientos de miles de filas, ahí DuckDB gana por orden de magnitud). |
| Migración futura | PostgreSQL + PostGIS | Camino de escalamiento cuando haya escritura concurrente multiusuario o el dataset supere lo cómodo para un archivo embebido (ver §11). |
| Contenedores | Docker + docker-compose | Pedido explícito, deploy reproducible en VPS/Hostinger. |

---

## 5. Flujo completo de datos

1. **Scheduled trigger** (cron / GitHub Actions / cron del VPS) dispara `scripts/update_data.py <eleccion>`.
2. **Ingesta** (`backend/importers`): descarga desde DINE API o JEP, guarda respuesta cruda tal cual
   en `data/raw/<fuente>/<eleccion>/<timestamp>/`, calcula hash SHA-256 del payload. Si el hash es
   idéntico al último import exitoso, no reprocesa (idempotencia, evita reescribir gold sin motivo).
3. **Bronze** (`backend/etl/bronze_to_silver` — paso 1): parsea el raw (JSON/CSV) a tablas DuckDB
   `raw.*` sin transformar valores, solo tipado mínimo. Se conserva 1:1 con la fuente.
4. **Validación** (`backend/etl/validators`): corre reglas de calidad (§13) contra bronze. Los
   registros que fallan van a `raw.rejected_rows` con motivo, no bloquean el resto del batch.
5. **Silver**: normaliza a los esquemas de `core.*` (ver modelo §6) — resuelve nombres de fuerzas
   políticas a un catálogo estable entre elecciones, castea tipos, geocodifica establecimientos
   nuevos (cachea resultados de geocoding para no re-pegarle a la API externa).
6. **Gold** (`backend/etl/silver_to_gold`): calcula métricas derivadas y materializa `marts.*` —
   porcentajes por fuerza, ganador por mesa, swing vs. elección anterior comparable, agregados por
   circuito/sección/municipio, capas GeoJSON para heatmaps. Estas tablas son las que lee la API.
7. **API** sirve `marts.*` y `core.*` vía FastAPI, nunca toca `raw.*` directamente.
8. **Frontend** consume la API, cachea con React Query, renderiza mapas/dashboards.

Todo el flujo es **re-ejecutable de punta a punta desde `raw/`** — si se cambia una regla de
negocio (p. ej. cómo se calcula "competitividad"), se recalcula gold sin volver a tocar internet.

---

## 6. Modelo de base de datos

Esquema `core` (normalizado, 3FN para dimensiones; hechos desnormalizados lo justo para performance
analítica):

```
core.elecciones
  id (pk), nombre, tipo (PASO|GENERAL|BALLOTAGE), ambito (NACIONAL|PROVINCIAL|MUNICIPAL),
  fecha, año, elecciones_comparables[] (fk a sí misma, para swing: p.ej. Generales 2023 → PASO 2023)

core.distritos / core.secciones / core.circuitos
  jerarquía territorial oficial, con vigencia (desde/hasta) porque los circuitos
  pueden cambiar de una elección a otra (2023 vs 2025 no son necesariamente idénticos)

core.establecimientos
  id (pk), nombre, direccion, lat, lon, geom (point, spatial),
  fuente_geocoding, precision_geocoding, validado (bool), circuito_id (fk)
  -- UNIQUE(nombre, direccion) + índice espacial para dedupe

core.mesas
  id (pk), eleccion_id (fk), numero_mesa, establecimiento_id (fk), circuito_id (fk),
  electores_habilitados, tipo_mesa (general|extranjeros|etc.)
  UNIQUE(eleccion_id, numero_mesa)

core.fuerzas_politicas
  id (pk), nombre_normalizado, color_hex
  -- catálogo estable: "La Libertad Avanza" es la misma fila en 2023 y 2025

core.fuerzas_por_eleccion
  fuerza_id (fk), eleccion_id (fk), nombre_en_boleta, orden_boleta
  -- resuelve que una alianza cambie de nombre/composición entre elecciones
  -- (p.ej. coaliciones que se renombran) sin romper la serie histórica

core.resultados_mesa   -- tabla de hechos, grano = 1 fila por mesa x fuerza
  mesa_id (fk), fuerza_id (fk),
  votos, porcentaje_positivos, porcentaje_padron

core.resultados_mesa_totales  -- grano = 1 fila por mesa
  mesa_id (fk),
  votantes, votos_positivos, votos_blanco, votos_nulos,
  votos_recurridos, votos_impugnados, participacion_pct,
  ganador_fuerza_id (fk), diferencia_1ro_2do_pct

marts.swing_mesa
  mesa_id, eleccion_origen_id, eleccion_destino_id, fuerza_id, delta_votos, delta_pct
  -- precalculado en gold para que comparaciones no agreguen en caliente sobre millones de filas

marts.agregados_territoriales
  nivel (mesa|circuito|seccion|municipio), nivel_id, eleccion_id, fuerza_id,
  votos, pct, participacion_pct
```

Decisiones clave:
- **`resultados_mesa` en formato largo (1 fila por mesa×fuerza)**, no ancho (1 columna por fuerza),
  porque el número de fuerzas cambia por elección (PASO tiene más listas que General) — un esquema
  ancho rompería con cada elección nueva. El pivot a ancho se hace en la capa `marts` o en la API,
  no en el modelo base.
- **`fuerzas_por_eleccion` como tabla puente** es lo que permite comparar 2023 vs 2025 aunque los
  nombres de alianza cambien — la justificación técnica es exactamente el problema real de esta
  elección (Cambia Federal, Fuerza Patria, LLA no son consistentes en su armado entre 2023-2025).
- **Vigencia temporal en la jerarquía territorial** porque asumir que "circuito 39" significa lo
  mismo en 2023 y 2025 sin verificarlo es la fuente de error más probable en comparaciones
  históricas electorales en Argentina (redistritamientos, fusiones de circuitos).

---

## 7. Modelo GIS

- **Establecimientos** → `POINT` geocodificado (lat/lon validados: rango de coordenadas de San
  Isidro, ~-34.47/-34.51 lat, -58.51/-58.56 lon; cualquier punto fuera de ese bounding box se marca
  para revisión manual, no se descarta silenciosamente).
- **Circuitos/secciones** → `POLYGON`/`MULTIPOLYGON`, obtenidos de capas oficiales del INDEC (radios
  censales / marco geoestadístico) o de la Cámara Nacional Electoral cuando publiquen shapefiles de
  circuitos; si no hay polígono oficial disponible para un circuito, se deja `geom = NULL`
  explícitamente (nunca se interpola un polígono aproximado — eso induciría a error en el heatmap).
- Todas las geometrías se guardan en **EPSG:4326** (WGS84) para consistencia con GeoJSON/Leaflet-MapLibre,
  con reproyección a EPSG:22185 (POSGAR 2007 / Faja 5, la proyección catastral de Buenos Aires)
  solo para cálculos de área/distancia donde la precisión métrica importa (p.ej. densidad).
- DuckDB `spatial` extension maneja joins espaciales (mesa dentro de circuito, cuando el circuito
  del dato de resultados es ambiguo) y exporta directo a GeoJSON para el frontend.
- Capas de heatmap se **pre-materializan como GeoJSON estático versionado** en `data/geo/` durante
  el paso gold (no se calculan en el navegador ni en cada request), y se sirven con cache-control
  largo + hash en el nombre de archivo para invalidación.

---

## 8. Organización de carpetas

```
san-isidro-electoral/
├── backend/
│   ├── app/                    # FastAPI app
│   │   ├── api/v1/routers/     # 1 router por dominio (elecciones, mesas, mapas, comparaciones, reportes, export)
│   │   ├── core/                # config, conexión DB, logging
│   │   ├── models/              # definiciones de tablas (SQL/dataclasses)
│   │   ├── schemas/             # Pydantic request/response
│   │   ├── services/            # lógica de negocio (comparaciones, rankings, clustering)
│   │   └── repositories/        # única capa que toca SQL — abstrae DuckDB vs. futuro Postgres
│   ├── importers/sources/{dine,jep_pba,geocoding}/
│   ├── etl/{bronze_to_silver,silver_to_gold,validators}/
│   ├── exporters/               # CSV/XLSX/JSON/GeoJSON/Parquet
│   └── tests/
├── frontend/
│   └── src/{app,components,features/{map,dashboard,comparisons,reports},hooks,lib,store,styles,types}/
├── data/{raw,processed,geo,logs}/   # raw es inmutable y versionado por timestamp
├── database/{schema.sql,migrations/}
├── scripts/                     # entrypoints CLI: update_data.py, build_geo.py, validate.py
├── docs/                        # este documento + DATA_SOURCES.md + RUNBOOK.md
└── docker/                      # Dockerfile.backend, Dockerfile.frontend, docker-compose.yml
```

(Ya scaffoldeado en el filesystem como esqueleto de carpetas vacías, sin código todavía.)

---

## 9. API (contrato inicial, `/api/v1`)

```
GET  /elecciones                          listado + metadata (fecha, tipo, ámbito)
GET  /elecciones/{id}/fuerzas             fuerzas políticas que compitieron

GET  /mesas?eleccion=&circuito=&seccion=  listado filtrable
GET  /mesas/{id}                          detalle completo + histórico de esa mesa/establecimiento

GET  /establecimientos                    listado geocodificado
GET  /establecimientos/{id}/mesas         mesas de ese establecimiento por elección

GET  /mapa/heatmap?capa=&eleccion=        GeoJSON pre-materializado (participación, abstención,
                                           voto por fuerza, ganador, margen, swing, blanco...)
GET  /mapa/capas                          catálogo de capas de heatmap disponibles

GET  /comparaciones/paso-vs-general?eleccion_a=&eleccion_b=
GET  /comparaciones/swing?eleccion_a=&eleccion_b=&nivel=mesa|circuito|seccion

GET  /reportes/ranking?tipo=mejores_mesas|peores_mesas|competitividad|crecimiento|
                        caida|participacion|abstencion&fuerza=&eleccion=

GET  /export/{formato}?entidad=&filtros=  formato ∈ csv|xlsx|json|geojson|parquet

GET  /calidad/incidencias                 log de validaciones fallidas (transparencia de datos)
```

Convenciones: paginación cursor-based en listados grandes, filtros siempre como query params
(cacheables por React Query con key determinística), versionado de API desde el día uno (`/v1`)
para no romper el frontend cuando se sumen capas del INDEC más adelante.

---

## 10. Estructura del frontend

- **`app/`** — rutas (React Router): `/mapa`, `/dashboard`, `/comparaciones`, `/reportes`, `/mesa/:id`.
- **`features/map/`** — componente MapLibre, control de capas de heatmap, popup de mesa/establecimiento.
- **`features/dashboard/`** — filtros globales (Zustand store compartido) + grid de gráficos Recharts.
- **`features/comparisons/`** — vistas PASO vs General, 2023 vs 2025, Provincial vs Nacional.
- **`features/reports/`** — tablas de rankings con export.
- **`hooks/`** — `useMesas`, `useHeatmapLayer`, `useComparacion`, etc., todos sobre React Query.
- **`lib/api.ts`** — cliente HTTP tipado (fetch + tipos generados desde el OpenAPI de FastAPI).
- **`store/filters.ts`** — Zustand: elección activa, circuito, fuerza, rango de participación — un
  único store leído tanto por el mapa como por los gráficos para que cambiar un filtro actualice
  todo sin recargar la página ni prop-drilling.

---

## 11. Estrategia de actualización de datos

- **Elecciones ya ocurridas (2023, 2025):** import inicial único con escrutinio definitivo como
  fuente de verdad (no el provisorio informático de la noche del escrutinio, que tiene mayor tasa
  de error de telegrama/OCR).
- **Futuras elecciones:** el mismo importer se reutiliza; solo cambia el parámetro `eleccion_id`.
  Durante la noche electoral, el scheduler puede correr cada 5-10 minutos contra el resultado
  provisorio y marcar explícitamente `es_provisorio=true` en gold, reemplazado por el definitivo
  cuando esté disponible — la UI debe distinguir visualmente ambos estados, nunca mezclarlos como
  si fueran igual de confiables.
- Cron (`scripts/update_data.py`) vía systemd timer o cron del VPS en producción; GitHub Actions
  como alternativa/backup para correr el pipeline sin depender del VPS estar encendido.
- Reprocesamiento completo de gold es siempre seguro y barato (DuckDB analítico) — se prefiere
  recalcular todo antes que hacer updates incrementales frágiles, dado el volumen (San Isidro:
  cientos de mesas, no millones de filas).

## 12. Estrategia de cache

| Nivel | Mecanismo |
|---|---|
| Cliente | React Query (`staleTime` largo para catálogos como elecciones/fuerzas, corto para resultados que puedan estar en revisión) |
| HTTP | Cache-Control fuerte en GeoJSON estático versionado por hash de contenido; ETags en la API |
| Servidor | Tablas `marts.*` son en sí mismas una capa de cache — nunca se agrega en caliente sobre `raw`/`core` en el hot path de un request |
| CDN (producción) | GeoJSON de heatmaps y exports servidos detrás de CDN/Nginx cache, ya que son inmutables entre corridas de ETL |

## 13. Estrategia de escalabilidad

- DuckDB embebido cubre cómodamente el volumen de San Isidro (bajo volumen respecto a lo que
  soporta: cientos de miles de filas es trivial para su motor columnar) y de todo el conurbano si
  algún día se expande el alcance.
- **Camino de escalamiento explícito a Postgres + PostGIS** cuando aparezca cualquiera de estas
  señales: escritura concurrente multiusuario (varios operadores cargando datos a la vez), necesidad
  de replicación/alta disponibilidad, o el frontend pasa de solo-lectura a tener usuarios que anotan/
  comentan sobre mesas. La capa `repositories/` es la única que sabe hablar SQL — cambiar el motor
  es cambiar esa capa, no el resto del backend.
- Backend stateless (FastAPI sin sesión en memoria) → escala horizontalmente detrás de un load
  balancer sin cambios si el tráfico lo justifica.
- Capas GeoJSON pesadas se sirven pre-generadas, no calculadas por request, así el cuello de botella
  nunca es el motor de mapas.

## 14. Riesgos del proyecto

1. **JEP PBA no tiene API pública documentada** (a diferencia de DINE) → el importer de la elección
   provincial 2025 depende de ingeniería inversa de un sitio que puede cambiar sin aviso. Mitigación:
   aislar ese importer, guardar HTML/JSON crudo en `raw/` apenas se obtiene (para no depender de que
   el sitio siga arriba en el futuro), y tener un fallback manual de carga de CSV si el scraping se
   rompe.
2. **Nombres de fuerzas políticas inconsistentes entre elecciones** (alianzas se arman/desarman) →
   mitigado por el modelo `fuerzas_por_eleccion` (§6), pero requiere curación manual al incorporar
   cada elección nueva — no es 100% automatizable sin criterio político/editorial.
3. **Cambios de circuitos entre 2023 y 2025** → mitigado con vigencia temporal en la jerarquía
   territorial, pero puede requerir mapeo manual mesa-a-mesa donde no haya continuidad de numeración.
4. **Geocoding de escuelas** con direcciones ambiguas o repetidas (varias mesas, mismo edificio) →
   dedupe por normalización de dirección + validación manual dado que el universo es acotado
   (~100-150 establecimientos en San Isidro, revisable a mano).
5. **Dependencia de disponibilidad de fuentes oficiales** — si DINE o JEP cambian su URL/formato,
   el pipeline de ingesta rompe. Mitigación: raw versionado significa que aunque la fuente
   desaparezca, lo ya descargado no se pierde.
6. **Alcance del pedido es muy amplio** (heatmaps múltiples, GIS avanzado, reportes automáticos,
   exports en 5 formatos, capas futuras) — riesgo de sobre-extensión en una primera iteración.
   Mitigación: este documento prioriza una Fase 2 incremental (ver §16) en vez de intentar todo a la vez.

## 15. Posibles problemas de calidad de datos

- Mesas duplicadas por reapertura de acta o rectificación posterior → se resuelve quedándose con la
  versión de mayor `version`/timestamp por `(eleccion_id, numero_mesa)`, versión anterior queda en
  `raw` para auditoría, nunca se borra.
- Escuelas duplicadas por variantes de escritura de nombre/dirección → normalización (unaccent,
  uppercase, remoción de sufijos tipo "Esc." vs "Escuela") + matching fuzzy + revisión manual del
  universo acotado.
- Coordenadas inválidas o fuera del bounding box de San Isidro → cuarentena automática, nunca se
  plotean en el mapa sin validar.
- Datos faltantes (mesa sin `electores_habilitados`, sin georreferenciar) → se muestran explícitamente
  como "sin datos" en la UI, nunca se imputan/inventan valores.
- Inconsistencias aritméticas (suma de votos por fuerza ≠ votos positivos declarados) → regla de
  validación dedicada que loguea la mesa en `calidad/incidencias` sin bloquear el resto del import.
- Errores de formato en CSV/API (encoding, separadores decimales `,` vs `.`, que es un problema real
  y frecuente en fuentes argentinas) → parseo defensivo con tipos explícitos en la capa bronze.

## 16. Mejoras futuras / Segunda etapa (arquitectura ya preparada para esto)

La capa `bronze/silver/gold` + el modelo `core.circuitos` con geometría son exactamente lo que
permite sumar sin rediseñar:

- Radios censales INDEC, indicadores socioeconómicos, densidad poblacional → nueva fuente bronze +
  join espacial contra `core.circuitos`/`core.establecimientos`, sin tocar el modelo electoral.
- Infraestructura urbana (clubes, iglesias, centros de jubilados, espacios verdes, escuelas no
  electorales) → tabla `core.puntos_interes(tipo, geom, ...)` genérica, independiente del dominio
  electoral, consumida por el mismo frontend de mapas como capas adicionales activables.
- Análisis espacial avanzado (clustering de voto, hot-spots de abstención) → capa `marts.analisis_espacial`
  calculada con `geopandas`/`libpysal` sobre `core`, expuesta como una capa de heatmap más.
- Multi-partido/multi-distrito: aunque el alcance actual es exclusivamente San Isidro, el modelo de
  datos ya es genérico por `distrito_id` — extenderlo a otro partido bonaerense es agregar filas, no
  reescribir esquema.

---

## 17. Diseño visual

- Paleta: blanco + `#30115E` como color de marca; toda la escala de violetas derivada (tints/shades
  generados programáticamente para mantener consistencia, no elegidos a mano por componente) para
  gráficos, estados, mapas de calor y botones.
- Tipografía moderna (Inter o similar), mucho espacio en blanco, cards con sombra suave y bordes
  redondeados — se define como design tokens de Tailwind (`tailwind.config.ts`), no como estilos
  sueltos por componente.
- Sin imágenes decorativas, sin logotipos, sin identidad partidaria — estética de herramienta BI
  profesional (referencia de tono: Metabase/Superset/Linear, no un sitio de campaña).
- Responsive orientado a desktop/tablet (uso analítico, no mobile-first).

## 18. Deploy

- `docker-compose.yml` con 2 servicios: `backend` (FastAPI + Uvicorn, DuckDB como archivo montado
  en volumen) y `frontend` (build estático servido por Nginx). Un tercer servicio opcional `etl`
  para correr el pipeline como job separado (cron dentro del contenedor o disparado externamente).
- Frontend compila con `npm run build` → `dist/` publicable en cualquier hosting estático
  (Hostinger, Nginx en VPS, o GitHub Pages si el backend se expone en otro dominio con CORS
  configurado).
- Variables de entorno (`backend/.env`): paths de datos, orígenes CORS permitidos, nivel de log.
- README documentará instalación, primer import de datos, actualización, y troubleshooting.

---

## 19. Próximos pasos propuestos (Fase 2 — implementación incremental)

Dado el tamaño del alcance completo, se propone no implementar todo de una sola vez sino en
entregas verificables:

1. **Esqueleto + modelo de datos**: `database/schema.sql`, conexión DuckDB, importer DINE para
   PASO 2023 (fuente con API documentada, menor riesgo) acotado a San Isidro, carga a bronze/silver/gold.
2. **API mínima + mapa**: endpoints de mesas/establecimientos, geocoding de escuelas de San Isidro,
   mapa MapLibre con 1 heatmap (participación) sobre datos reales de PASO 2023.
3. **Resto de elecciones 2023** (General, Ballotage) + comparaciones PASO vs General.
4. **Importer JEP PBA 2025** (mayor riesgo técnico, se aborda con margen) + Legislativa Nacional 2025.
5. **Dashboard completo, todos los heatmaps, reportes automáticos, exports.**
6. **Docker + deploy a VPS/Hostinger.**

¿Confirmás este enfoque y arrancamos por el punto 1, o preferís ajustar algo del documento antes
(tecnologías, modelo de datos, alcance de la Fase 2)?
