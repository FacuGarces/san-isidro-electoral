-- San Isidro Electoral Intelligence — esquema DuckDB
-- Ver docs/ARCHITECTURE.md §6-7 para el diseño completo.
--
-- Nota de implementación (entrega 1): la fuente de DINE solo nos da granularidad de
-- CIRCUITO para PASO 2023 (ver docs/DATA_SOURCES.md — el mesaId por circuito no está
-- resuelto todavía). Por eso `core.circuitos` ya incluye `municipio_nombre`/`municipio_indec`
-- (no estaba en el diseño original de ARCHITECTURE.md, que asumía que esa info vivía en
-- establecimientos/mesas) y agregamos `core.resultados_circuito*` como grano intermedio.
-- Las tablas de mesa (`core.establecimientos`, `core.mesas`, `core.resultados_mesa*`) quedan
-- creadas y listas para cuando se resuelva el import a nivel mesa, sin requerir migración.

INSTALL spatial;
LOAD spatial;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS marts;

-- ============================================================
-- CORE — dimensiones
-- ============================================================

CREATE TABLE IF NOT EXISTS core.elecciones (
    id              VARCHAR PRIMARY KEY,      -- p.ej. 'PASO2023'
    nombre          VARCHAR NOT NULL,
    tipo            VARCHAR NOT NULL CHECK (tipo IN ('PASO','GENERAL','BALLOTAGE')),
    ambito          VARCHAR NOT NULL CHECK (ambito IN ('NACIONAL','PROVINCIAL','MUNICIPAL')),
    fecha           DATE NOT NULL,
    anio            INTEGER NOT NULL,
    categoria_id    INTEGER NOT NULL,          -- idCargo en la API DINE (1=Presidente, ...)
    categoria_nombre VARCHAR NOT NULL,
    id_eleccion_dine INTEGER,                  -- idEleccion en la API DINE (1=PASO,2=Gral,3=Ballotage), NULL si no aplica (JEP)
    id_distrito_dine INTEGER,                  -- idDistrito en la API DINE (2=Buenos Aires), NULL si no aplica
    fuente          VARCHAR NOT NULL,          -- 'DINE' | 'JEP_PBA'
    eleccion_comparable_id VARCHAR REFERENCES core.elecciones(id) -- p.ej. Generales2023 -> PASO2023
);

CREATE TABLE IF NOT EXISTS core.distritos (
    id      VARCHAR PRIMARY KEY,   -- 'BA'
    nombre  VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS core.circuitos (
    id                  VARCHAR PRIMARY KEY,   -- código de circuito tal cual fuente oficial (p.ej. '890', '0892A')
    id_dine             VARCHAR,               -- forma zero-padded a 5 usada por la API DINE (p.ej. '00890')
    distrito_id         VARCHAR NOT NULL REFERENCES core.distritos(id),
    municipio_nombre    VARCHAR NOT NULL,      -- p.ej. 'San Isidro'
    municipio_indec     VARCHAR NOT NULL,      -- p.ej. '756'
    seccion_electoral   VARCHAR,               -- 1ra-8va sección electoral PBA, si se conoce
    geom                GEOMETRY,              -- NULL si no hay polígono oficial de circuito disponible
    vigente_desde       DATE,
    vigente_hasta       DATE
);

CREATE TABLE IF NOT EXISTS core.municipios (
    indec       VARCHAR PRIMARY KEY,   -- '756'
    nombre      VARCHAR NOT NULL,      -- 'San Isidro'
    distrito_id VARCHAR NOT NULL REFERENCES core.distritos(id),
    geom        GEOMETRY               -- polígono del partido (de /api/mapas?tipo=departamentos)
);

CREATE TABLE IF NOT EXISTS core.establecimientos (
    id                  VARCHAR PRIMARY KEY,
    nombre              VARCHAR NOT NULL,
    direccion           VARCHAR,
    lat                 DOUBLE,
    lon                 DOUBLE,
    geom                GEOMETRY,
    fuente_geocoding    VARCHAR,
    precision_geocoding VARCHAR,
    validado            BOOLEAN DEFAULT FALSE,
    circuito_id         VARCHAR REFERENCES core.circuitos(id)
);

CREATE TABLE IF NOT EXISTS core.mesas (
    id                      VARCHAR PRIMARY KEY,   -- '{eleccion_id}:{numero_mesa}'
    eleccion_id             VARCHAR NOT NULL REFERENCES core.elecciones(id),
    numero_mesa             VARCHAR NOT NULL,
    establecimiento_id      VARCHAR REFERENCES core.establecimientos(id),
    circuito_id             VARCHAR NOT NULL REFERENCES core.circuitos(id),
    electores_habilitados   INTEGER,
    tipo_mesa               VARCHAR DEFAULT 'general',
    UNIQUE (eleccion_id, numero_mesa)
);

CREATE TABLE IF NOT EXISTS core.fuerzas_politicas (
    id                  VARCHAR PRIMARY KEY,   -- idAgrupacion de DINE, estable entre elecciones
    nombre_normalizado  VARCHAR NOT NULL,
    color_hex           VARCHAR
);

CREATE TABLE IF NOT EXISTS core.fuerzas_por_eleccion (
    fuerza_id       VARCHAR NOT NULL REFERENCES core.fuerzas_politicas(id),
    eleccion_id     VARCHAR NOT NULL REFERENCES core.elecciones(id),
    nombre_en_boleta VARCHAR NOT NULL,
    orden_boleta    INTEGER,
    PRIMARY KEY (fuerza_id, eleccion_id)
);

-- ============================================================
-- CORE — hechos, grano MESA (preparado, se puebla cuando se resuelva mesaId por circuito)
-- ============================================================

CREATE TABLE IF NOT EXISTS core.resultados_mesa (
    mesa_id             VARCHAR NOT NULL REFERENCES core.mesas(id),
    fuerza_id           VARCHAR NOT NULL REFERENCES core.fuerzas_politicas(id),
    votos               INTEGER NOT NULL,
    porcentaje_positivos DOUBLE,
    PRIMARY KEY (mesa_id, fuerza_id)
);

CREATE TABLE IF NOT EXISTS core.resultados_mesa_totales (
    mesa_id                 VARCHAR PRIMARY KEY REFERENCES core.mesas(id),
    votantes                INTEGER,
    votos_positivos         INTEGER,
    votos_blanco            INTEGER,
    votos_nulos             INTEGER,
    votos_recurridos_comando_impugnados INTEGER,
    participacion_pct       DOUBLE,
    ganador_fuerza_id       VARCHAR REFERENCES core.fuerzas_politicas(id),
    diferencia_1ro_2do_pct  DOUBLE
);

-- ============================================================
-- CORE — hechos, grano CIRCUITO (lo que sí tenemos hoy para PASO 2023)
-- ============================================================

CREATE TABLE IF NOT EXISTS core.resultados_circuito (
    eleccion_id VARCHAR NOT NULL REFERENCES core.elecciones(id),
    circuito_id VARCHAR NOT NULL REFERENCES core.circuitos(id),
    fuerza_id   VARCHAR NOT NULL REFERENCES core.fuerzas_politicas(id),
    -- Nullable a propósito: fuentes "parciales / no definitivas" (p.ej. una app oficial cuyo
    -- backend ya no está online, ver docs/DATA_SOURCES.md "Senadores/Concejales 2025") solo
    -- traen el % por fuerza, no el conteo de votos. Nunca completar con 0 — 0 significa "cero
    -- votos reales", no "dato desconocido".
    votos       INTEGER,
    votos_pct   DOUBLE,
    PRIMARY KEY (eleccion_id, circuito_id, fuerza_id)
);

-- Desglose de listas internas dentro de una misma fuerza (relevante en PASO: un frente puede
-- llevar más de un candidato/lista a una misma categoría, p.ej. San Isidro 2023 tuvo 2+
-- precandidatos a intendente tanto en JxC como en UP). En Generales normalmente hay 1 lista
-- por fuerza (la ganadora de la interna), pero se carga igual para no tener un caso especial.
CREATE TABLE IF NOT EXISTS core.resultados_circuito_lista (
    eleccion_id     VARCHAR NOT NULL REFERENCES core.elecciones(id),
    circuito_id     VARCHAR NOT NULL REFERENCES core.circuitos(id),
    fuerza_id       VARCHAR NOT NULL REFERENCES core.fuerzas_politicas(id),
    lista_numero    VARCHAR NOT NULL,
    lista_nombre    VARCHAR NOT NULL,
    votos           INTEGER NOT NULL,
    votos_pct_fuerza DOUBLE,  -- % sobre el total de votos de la fuerza en ese circuito
    PRIMARY KEY (eleccion_id, circuito_id, fuerza_id, lista_numero)
);

CREATE TABLE IF NOT EXISTS core.resultados_circuito_totales (
    eleccion_id             VARCHAR NOT NULL REFERENCES core.elecciones(id),
    circuito_id             VARCHAR NOT NULL REFERENCES core.circuitos(id),
    mesas_totalizadas       INTEGER,
    electores               INTEGER,
    votantes                INTEGER,
    votos_positivos         INTEGER,
    votos_blanco            INTEGER,
    votos_nulos             INTEGER,
    votos_recurridos_comando_impugnados INTEGER,
    participacion_pct       DOUBLE,
    ganador_fuerza_id       VARCHAR REFERENCES core.fuerzas_politicas(id),
    diferencia_1ro_2do_pct  DOUBLE,
    PRIMARY KEY (eleccion_id, circuito_id)
);

-- ============================================================
-- MARTS — agregados territoriales genéricos (mesa|circuito|seccion|municipio)
-- ============================================================

CREATE TABLE IF NOT EXISTS marts.agregados_territoriales (
    nivel       VARCHAR NOT NULL CHECK (nivel IN ('mesa','circuito','seccion','municipio')),
    nivel_id    VARCHAR NOT NULL,
    eleccion_id VARCHAR NOT NULL,  -- lógicamente FK a core.elecciones(id); DuckDB no soporta FK entre esquemas
    fuerza_id   VARCHAR NOT NULL,  -- lógicamente FK a core.fuerzas_politicas(id)
    votos       INTEGER,  -- nullable: fuentes parciales sin conteo real, ver comentario en core.resultados_circuito.votos
    votos_pct   DOUBLE,
    participacion_pct DOUBLE,
    PRIMARY KEY (nivel, nivel_id, eleccion_id, fuerza_id)
);

-- ============================================================
-- Calidad de datos
-- ============================================================

CREATE TABLE IF NOT EXISTS raw.rejected_rows (
    id              INTEGER PRIMARY KEY,
    fuente          VARCHAR NOT NULL,
    eleccion_id     VARCHAR,
    payload         VARCHAR NOT NULL,  -- JSON crudo de la fila rechazada
    motivo          VARCHAR NOT NULL,
    detectado_en    TIMESTAMP DEFAULT current_timestamp
);
