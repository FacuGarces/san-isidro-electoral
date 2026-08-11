# Checklist — pedido original vs. estado actual

Comparación punto por punto contra el mega-prompt inicial. ✅ hecho · 🟡 parcial / hay una base
armada · ⬜ falta. Pensado para volver a esto y priorizar qué sigue.

## Checklist visto como asesor político de LLA (2026-08-10)

Ejercicio: pensar la herramienta 100% orientada a ganar Intendente + Concejales 2027 y ver qué
le falta. Lo que un asesor pediría, cruzado contra lo que hay hoy:

| Necesita el asesor | Estado |
|---|---|
| Resultados PASO/General 2023, Presidente e Intendente, con interna separada | ✅ |
| Swing PASO→General por fuerza y por circuito | ✅ |
| **Voto cruzado Presidente vs. Intendente** (cuánto del voto a la marca nacional no se traslada al candidato local) | ✅ — era el gap más grande, se cerró completo (ver "Voto cruzado" en Comparaciones) |
| Clasificación bastión/competitivo/hostil | ✅ |
| Ranking de circuitos ponderado por padrón (impacto, no solo %) | ✅ |
| Legislativas 2025, elecciones pre-2023 | 🟡 — Diputados Nacionales 2025 investigado y cargable (mismo patrón que Ballotage), falta ejecutar el importer |
| Nivel mesa (para operativos de campo) | ⬜ — bloqueado, sin fuente pública para PBA (2023); para 2025 ya hay dato de mesa, falta cruzarlo con circuito |
| Demográficos/censales (INDEC, pirámide etaria, NSE por radio censal) | ⬜ — arquitectura prevista (ver "Segunda etapa"), no implementado |
| Concejales | 🟡 — DINE sigue sin publicarlo para Buenos Aires, pero se cargó **Concejales 2025** por circuito como dato PARCIAL (transcripto de capturas de una app oficial, ver docs/DATA_SOURCES.md sección "Senadores/Concejales 2025") |

Los primeros 5 ítems (los más baratos de resolver porque el dato ya estaba cargado) se cerraron
en la sesión del 2026-08-10 junto con el rediseño completo del flujo de comparación. Los 4
últimos son bloqueos de **fuente de datos**, no de interfaz — no se resuelven con más UX.

## Datos a descargar

| Ítem pedido | Estado |
|---|---|
| Resultados por mesa | ⬜ — nivel más fino disponible hoy es circuito (ver docs/DATA_SOURCES.md) |
| Resultados por escuela/establecimiento | ⬜ — depende de resolver mesa-por-mesa |
| Resultados por circuito | ✅ — San Isidro, PASO/Generales 2023, categorías Presidente e Intendente |
| Resultados por sección (electoral) | ⬜ — no agregado todavía a ese nivel |
| Resultados por municipio | ✅ — San Isidro como total; falta generalizar a "cualquier municipio" |
| Electores / votantes / participación | ✅ |
| Votos positivos / blanco / nulos | ✅ |
| Votos recurridos / impugnados | 🟡 — el dato de DINE los junta en un solo campo ("comando/impugnados"), no separados |
| Votos por fuerza política | ✅ — las 15 fuerzas de PASO 2023 |

## Categorías / cuerpo de boleta

| Categoría | Estado |
|---|---|
| Presidente/a | ✅ — PASO y Generales 2023, con desglose de listas internas de la PASO (Bullrich vs. Larreta en JxC, Massa vs. Grabois en UP) y foto de cada candidato |
| Intendente/a | ✅ — PASO y Generales 2023, con desglose de listas internas de la PASO (Lanús vs. Posse vs. Ruffa en JxC) — foto solo para Lanús, sin foto de licencia libre disponible para el resto |
| Concejales | 🟡 — DINE sigue sin publicarlo para Buenos Aires (2023), pero **Concejales 2025** está cargado por circuito como `CONCEJALES2025PBA_PARCIAL` (dato PARCIAL, ver docs/DATA_SOURCES.md) |
| Gobernador/a, Senadores/Diputados nacionales y provinciales | 🟡 — Senadores Provinciales 2025 cargado (`SENADORES2025PBA_PARCIAL`, PARCIAL); el resto no cargado, sí disponibles en DINE si se necesitan a futuro |

## Elecciones a analizar

| Elección | Estado |
|---|---|
| PASO 2023 | ✅ cargada (circuito) |
| Generales 2023 (22/10) | ✅ cargada (circuito) — `eleccion_comparable_id` apunta a PASO2023 |
| Ballotage 2023 (19/11) | ✅ cargada (circuito) — la API en vivo no sirve este nivel, se cargó desde el CSV masivo de datos.gob.ar (ver docs/DATA_SOURCES.md) |
| Provincial PBA (7/9/2025) | 🟡 — Senadores Provinciales y Concejales cargados por circuito como PARCIAL (`SENADORES2025PBA_PARCIAL`, `CONCEJALES2025PBA_PARCIAL`); el techo real de la fuente oficial es municipio/sección, no circuito (ver docs/DATA_SOURCES.md) |
| Nacional (26/10/2025 — corregido de 25/10) | ⬜ — Diputados Nacionales investigado y cargable (mismo patrón que Ballotage), falta ejecutar el importer |

## Base de datos

| Ítem | Estado |
|---|---|
| Esquema normalizado (core/marts) | ✅ |
| Ganador, diferencia 1°-2° por circuito | ✅ |
| Swing / comparación histórica | ✅ — `app/repositories/comparacion.py`, swing por circuito y por fuerza, ponderado por electores para el agregado de San Isidro |
| % por fuerza | ✅ |

## Georreferenciación

| Ítem | Estado |
|---|---|
| Coordenadas de circuitos (polígonos oficiales) | ✅ |
| Coordenadas de escuelas individuales | ⬜ |
| Validación de coordenadas / dedupe | ⬜ (no aplica todavía, sin datos de escuela) |
| Capas geográficas reutilizables | ✅ — geometría vive en `core.circuitos.geom` (DuckDB spatial) |

## Mapas

| Ítem | Estado |
|---|---|
| Mapa interactivo con calles reales | ✅ — MapLibre + OpenStreetMap |
| Click en establecimiento con resultado completo | ⬜ — hoy el click es a nivel circuito, no escuela |
| Evolución histórica / comparación al clickear | ⬜ — necesita más elecciones |
| Activar/desactivar capas | 🟡 — hay selector de una capa a la vez, no múltiples simultáneas |

## Mapas de calor

| Capa pedida | Estado |
|---|---|
| Participación | ✅ |
| Abstención | 🟡 — es el complemento de participación, no tiene vista propia |
| Voto LLA | ✅ |
| Voto Unión por la Patria | ✅ |
| Voto "Acción Vecinal" | ⬜ — no compitió en PASO 2023 San Isidro con ese nombre; revisar si aplica en otra elección |
| Voto otras fuerzas | 🟡 — están en el detalle por circuito, no como capa de mapa propia |
| Ganador por mesa | 🟡 — hecho a nivel circuito, no mesa |
| Margen de victoria | ✅ — como orden del ranking; falta como capa de color propia en el mapa |
| Crecimiento histórico | ⬜ — necesita 2+ elecciones |
| Caída histórica | ⬜ — ídem |
| Voto en blanco | ⬜ — el dato está cargado en la base pero no tiene capa de mapa |

## Comparaciones

| Ítem | Estado |
|---|---|
| PASO vs. General | ✅ — preset "Evolución" en el dashboard, swing por circuito y por fuerza, leyenda divergente, detección de cambio de ganador |
| **Voto cruzado (Presidente vs. Intendente)** | ✅ — preset "Voto cruzado", muestra cuánto del voto a la boleta nacional no se traslada al candidato local. No estaba pedido originalmente; salió del ejercicio de pensar la app como asesor político de LLA para 2027 (ver docs/DATA_SOURCES.md o CLAUDE.md) — es la comparación de mayor valor estratégico y ya se podía calcular con datos existentes |
| General vs. Ballotage | ✅ — funciona con el endpoint genérico de comparación, sin cambios de backend |
| 2023 vs. 2025 | ⬜ |
| Provincial vs. Nacional | ⬜ |
| Diferencia absoluta / porcentual, cambio de ganador | ✅ |

El endpoint `/mapa/comparacion` ya es genérico (`?actual=&base=`, cualquier par de elecciones
cargadas) — cargar una elección nueva a futuro (2025, por ejemplo) no requeriría ningún cambio de
backend, solo subir los datos, siempre que la fuente los publique a nivel circuito.

## Dashboard

| Ítem | Estado |
|---|---|
| Filtro por elección | ✅ — tabs de Categoría + Etapa (Ver/Comparar) en el header, con presets para las comparaciones más usadas |
| Resumen ejecutivo (KPIs siempre visibles) | ✅ — `KpiHeader.tsx`: electores, mesas, participación, fuerza líder con candidato, y en modo comparar swing + circuitos que cambiaron de mano |
| Clasificación de circuitos (bastión/competitivo/hostil) | ✅ — umbrales sobre el % de la fuerza seleccionada, visible en el popup del mapa |
| Ranking por impacto (swing × padrón), no solo % | ✅ — toggle en el panel de circuitos, modo comparar |
| Filtro por circuito | ✅ — buscador en el panel Circuitos, `CircuitFilterBar.tsx` |
| Filtro por fuerza política | ✅ — como métrica |
| Filtro por participación (rango) | ✅ — min/max en el mismo buscador; en modo comparar filtra por swing de participación |
| Filtro por ganador | 🟡 — la vista "Ganador" lo muestra, no se puede aislar un partido |
| Gráficos que se actualizan dinámicamente | ✅ — mapa, ranking y detalle reaccionan en vivo |

## Reportes automáticos

| Ítem | Estado |
|---|---|
| Mejores/peores circuitos por fuerza | 🟡 — el ranking ya lo ordena, falta una vista "reporte" dedicada |
| Circuitos competitivos (margen chico) | 🟡 — el dato existe (`diferencia_pct`), falta una vista propia |
| Ranking de crecimiento/caída | ⬜ — necesita histórico |
| Ranking de participación/abstención | ✅ — vía la vista "Participación" |

## Exportaciones

| Formato | Estado |
|---|---|
| CSV / Excel / JSON / GeoJSON / Parquet | 🟡 — CSV (formato largo circuito×fuerza, delimitado con `;` para Excel es-AR) y GeoJSON, botones en el header del panel "Circuitos" (`lib/export.ts`), todo client-side sobre los datos ya cargados. JSON crudo ya se puede ver/guardar desde la respuesta de la API. Parquet no implementado — nicho, sin pedido concreto todavía |

## Calidad del dato

| Ítem | Estado |
|---|---|
| Detección de duplicados | 🟡 — se validó a mano en la carga, no hay chequeo automático |
| Datos faltantes / inconsistencias | 🟡 — se verificó a mano (suma de fuerzas = positivos), no es un validador reusable |
| Log de errores | ⬜ — existe la tabla `raw.rejected_rows` en el esquema pero no se usa todavía |

## Análisis espacial

| Ítem | Estado |
|---|---|
| Clusters, patrones territoriales, zonas homogéneas | ⬜ |

## Segunda etapa (capas futuras)

| Ítem | Estado |
|---|---|
| Radios censales / INDEC | ⬜ — arquitectura preparada (mismo patrón bronze/silver/gold), no implementado |
| Infraestructura urbana (clubes, iglesias, etc.) | ⬜ |

## Padrón electoral

| Ítem | Estado |
|---|---|
| Investigar qué es público | ✅ — resuelto: solo el campo agregado "electores por mesa/circuito" es público; no hay padrón nominal descargable en bloque |
| Usar solo datos agregados, nunca individuales | ✅ — decisión de arquitectura ya tomada y documentada |

## Deploy

| Ítem | Estado |
|---|---|
| Dockerfile / docker-compose | ⬜ |
| Variables de entorno de producción | ⬜ |
| Instrucciones de deploy (Hostinger/VPS) | ⬜ |

## Documentación

| Ítem | Estado |
|---|---|
| README con instalación/uso | ✅ |
| Arquitectura documentada | ✅ — ARCHITECTURE.md |
| Fuentes de datos documentadas | ✅ — DATA_SOURCES.md |
| Esta checklist | ✅ |

## Diseño / UX

| Ítem | Estado |
|---|---|
| Violeta claro de fondo, tarjetas blancas, violeta oscuro para texto/acentos | ✅ |
| Minimalista, sin estilo partidario en el chrome de la app | ✅ |
| Tipografía moderna (Montserrat) | ✅ |
| Selector de categoría/etapa como tabs visibles (no dropdown+toggle confuso) | ✅ — rediseñado a pedido del usuario, ver `PillTabs.tsx` |
| Colores de swing con ícono direccional (no solo color) | ✅ — corregido a pedido del usuario tras reportar que no se entendía |
| Fotos de candidatos en el desglose de listas y en el banner de comparación | ✅ — con fallback a iniciales cuando no hay foto verificada |
| Responsive / tablet | ⬜ — hoy está pensado para desktop, no se probó en pantallas chicas |
| Modo claro/oscuro | ✅ |
| Sistema de elevación / profundidad (no plano) | ✅ — pasada 2026-08-10, ver CLAUDE.md |
| Selector de fuerza/métrica sin `<select>` nativo | ✅ — combobox propio, ver CLAUDE.md |

---

## Resumen — qué es lo más grande que falta, en orden de impacto

1. ~~**Ballotage 2023**~~ — ✅ cargada 2026-08-10. La API en vivo no sirve Segunda Vuelta a nivel
   circuito (confirmado, ni siquiera fuera de Buenos Aires), pero apareció una fuente alternativa:
   el CSV masivo mesa-por-mesa de `datos.gob.ar` (no enlazado desde la web normal de DINE). Ver
   docs/DATA_SOURCES.md, sección "Ballotage 2023", y `importers/sources/dine/import_from_bulk_csv.py`.
2. ~~**Exportaciones**~~ — ✅ CSV y GeoJSON, 2026-08-10. Ver `frontend/src/lib/export.ts`.
3. ~~**Filtros del dashboard**~~ — ✅ buscador de circuito + rango de participación, 2026-08-10.
   Ver `CircuitFilterBar.tsx` / `lib/filtros.ts`.
4. **Nivel mesa/escuela** — el bloqueo real cambió: ya hay dato de voto por mesa (mismo CSV
   masivo que resolvió Ballotage), lo que falta es el mapeo mesa→escuela/domicilio. Ver
   docs/DATA_SOURCES.md, sección "Nivel mesa (escuela)", actualización 2026-08-10.
5. ~~**Provincial PBA 2025 (Senadores + Concejales)**~~ — 🟡 cargados por circuito como PARCIAL
   (`SENADORES2025PBA_PARCIAL` 2026-08-10, `CONCEJALES2025PBA_PARCIAL` 2026-08-11): el sistema de
   la Junta Electoral PBA nunca tabuló estas 2 categorías por circuito (confirmado con 3 fuentes
   independientes), solo por municipio/sección — el dato por circuito viene de capturas de una
   app oficial cuyo backend ya no está online, transcriptas a mano, sin electores/mesas/
   participación. Ver docs/DATA_SOURCES.md, sección "Senadores/Concejales 2025".
6. **Diputados Nacionales 2025** — mismo patrón que Ballotage (CSV masivo de datos.gob.ar), ya
   investigado y confirmado cargable — solo falta ejecutar el importer.
7. **Responsive/mobile** y **Deploy** — para cuando el resto esté más maduro.
