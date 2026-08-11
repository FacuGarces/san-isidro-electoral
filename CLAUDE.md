# San Isidro Electoral Intelligence — contexto para retomar el proyecto

Plataforma de inteligencia electoral para el partido de San Isidro (PBA). Si arrancás una
conversación nueva en esta carpeta, empezá leyendo esto y después:

1. [docs/CHECKLIST.md](docs/CHECKLIST.md) — qué está hecho vs. el pedido original, y qué sigue
   (ahí está el orden de prioridad recomendado).
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — diseño completo: modelo de datos, stack, por qué
   cada tecnología.
3. [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) — cómo se saca cada dato de DINE/PBA, con los
   endpoints reales (no la documentación oficial, que está desactualizada).
4. [README.md](README.md) — cómo levantar todo.

## Estado en una línea

PASO 2023, Generales 2023 y **Ballotage 2023** cargadas a nivel **circuito** (no mesa) para los 10
circuitos de San Isidro. Presidente/a tiene las 3 rondas (PASO/General/Ballotage); Intendente/a
tiene PASO/General (no hay ballotage municipal en PBA, se define a pluralidad simple) — 5 filas en
`core.elecciones` en total, PASO↔Generales↔Ballotage linkeadas vía `eleccion_comparable_id`. Ambas
PASO traen desglose de **listas internas** por fuerza (`core.resultados_circuito_lista`) — permite
ver, por ejemplo, Bullrich vs. Larreta en la interna de JxC a presidente, o Lanús vs. Posse a
intendente en San Isidro — con **foto de cada candidato** cuando hay una verificada y de licencia
libre (ver más abajo). Concejales por DINE (2023) quedó descartado: no lo publica para Buenos Aires (ver
docs/DATA_SOURCES.md) y, como Intendente/Concejales van en la misma boleta ("lista sábana" 2023),
Intendente ya cubre esa necesidad — decisión explícita del usuario. Aparte de estas 5 elecciones
2023, hay 2 elecciones PARCIALES 2025 (`SENADORES2025PBA_PARCIAL`, `CONCEJALES2025PBA_PARCIAL`) —
ver sección "Datos parciales / no definitivos" más abajo.

**Ballotage 2023 — cargado desde una fuente distinta a las demás elecciones (2026-08-10):** el
patrón genérico (`import_circuito_categoria.py`, que usa la API en vivo `/resultados/getResultados`)
**no sirve** para esta elección — confirmado que ese endpoint devuelve vacío a nivel circuito para
Segunda Vuelta en cualquier distrito del país, no es un problema de San Isidro. La solución fue un
importer nuevo, `backend/importers/sources/dine/import_from_bulk_csv.py`, que baja el ZIP oficial
`2023_segundavuelta.zip` (mesa por mesa, publicado en el catálogo `datos.gob.ar`, **no enlazado**
desde la web normal de resultados — hay que ir al dataset CKAN
`resultados-provisionales-elecciones-20231`) y agrega mesa→circuito para producir el mismo raw
JSON+manifest que el importer de la API en vivo, así `load_circuito_categoria.py` no cambió.
Verificado contra el agregado oficial de San Isidro (201.163 votos positivos, coincide exacto).
Detalle completo — incluida la implicancia para "nivel mesa/escuela", que dejó de estar bloqueado
por falta de dato de mesa (el CSV lo tiene) y ahora sólo le falta el mapeo mesa→establecimiento —
en `docs/DATA_SOURCES.md`, sección "Ballotage 2023". Este importer es el que usar de ahora en más
si una elección futura no responde bien en la API en vivo — probarlo antes de asumir que el dato
no está publicado.

**Flujo de selección de elección — v3, reemplaza por completo a v2 (2026-08-11):** v2 (más
abajo en el historial de este archivo si hace falta arqueología) introdujo un selector de 6
"escenarios" (tarjetas grandes: Resultado/Evolución/Voto cruzado 2023/Voto cruzado 2025/
Continuidad/Interna PASO) para no obligar al usuario a razonar en términos de categoría+etapa.
El usuario lo probó y lo rechazó explícito: *"la posta no entendí los filtros que usaste para
seleccionar arriba, me parece que están al pedo"* — pidió en cambio poder **elegir elecciones
particulares directamente** y **compararlas con gráficos de torta**. Se sacaron
`ScenarioPicker.tsx` y `SeleccionPicker.tsx` por completo (borrados, no solo dejados de usar) y
se simplificó el modelo de selección a su forma más directa:

- `mapStore.ts`: ya no existe `Seleccion {categoria, etapa}` ni el concepto de "escenario" —
  el estado es directamente `actualId: string` / `baseId: string` (el id de `core.elecciones`,
  p.ej. `"PASO2023_INTENDENTE"`). `modo: "ver" | "comparar"` se mantiene (toggle simple, nunca
  fue parte de la queja). `invertir()` reemplaza al viejo swap manual de actual/base.
- `EleccionSelect.tsx` (nuevo, reemplaza a `SeleccionPicker.tsx`): combobox hecho a mano (mismo
  patrón que `MetricSelect.tsx` — sin `<select>` nativo) que lista **cada elección por su nombre
  real** (`"PASO 2023 - Intendente/a"`, `"Concejales 2025 - San Isidro (PARCIAL, no
  definitivo)"`...), agrupada por categoría (San Isidro primero vía `ORDEN_CATEGORIAS`,
  Presidente/a al final) y ordenada cronológicamente dentro de cada grupo. En modo "ver" hay una
  sola instancia; en "comparar", dos ("Desde"/"Hasta") + botón invertir — sin colapsables ni
  progressive disclosure, porque ya no hay nada complejo que esconder.
- **Cualquier par de elecciones es comparable ahora**, literalmente sin restricción de categoría
  — el usuario puede armar `PASO 2023 - Intendente/a → Concejales 2025` (categorías distintas,
  2 años de diferencia) desde los dos dropdowns sin que la UI necesite un preset dedicado para
  ese caso. El backend (`comparacion.py`) ya soportaba esto desde v2, no cambió.
- El aviso de interna (antes la tarjeta de escenario dedicada "Interna PASO") pasó a ser un
  banner contextual chico arriba de `MetricSelect` que aparece solo cuando la elección activa
  tiene listas cargadas (`data.features[...].detalle[...].listas.length > 1`) — la función en sí
  de "candidato individual dentro de una interna" (Lanús/Posse anidados en el combobox) no
  cambió nada, sigue en `MetricSelect.tsx`/`metricKeyForLista()`/`colors.ts`.
- Título/subtítulo de la página se simplificaron a `${nombreBase} → ${nombreActual}` en modo
  comparar — ya no hay lógica especial por escenario (`esCruce`, textos a medida por preset),
  porque ya no hay presets.
- `KpiHeader.tsx`, `CompareCandidatesBanner.tsx`, `RankingList.tsx`, `DetailPanel.tsx`,
  `MapView.tsx`, `colors.ts`: **sin cambios** en esta v3 — todos ya trabajaban sobre
  `data`/`metricKey`, no sobre el viejo modelo de selección (`MapView.tsx` sí se tocó después,
  ver v3.1 más abajo, pero por el modo Versus, no por esto).

**v3.1 — bug de dropdown cortado + donuts reemplazados por Versus en el mapa (2026-08-11, misma
sesión):** dos correcciones sobre v3, pedidas juntas por el usuario.

1. **Bug real: el combobox de `EleccionSelect` se veía cortado/roto.** Causa: su popover usa
   `position: absolute`, y el marco que lo contiene (`<div className="... overflow-hidden
   rounded-3xl ...">`, el mismo `overflow-hidden` que sostiene los bordes redondeados de cada
   sección — ver "integración estructural" más arriba) le recorta cualquier hijo que se salga de
   su caja, incluido un popover posicionado absoluto. `MetricSelect` tenía el mismo problema
   latente pero nunca se notó porque su botón vive más abajo en una columna alta (el mapa), con
   margen de sobra antes de tocar el borde real del marco — `EleccionSelect` está pegado arriba
   de todo, en un marco bajito, así que el corte se veía enseguida. Fix: `PopoverPortal.tsx`
   (nuevo) — saca el popover a un portal en `document.body` con `position: fixed`, siguiendo el
   rect del botón (`getBoundingClientRect`, recalculado en scroll/resize). El click-afuera-cierra
   de cada combobox ahora también chequea `esClickEnPopover()` (busca `[data-popover-portal]` en
   el `target`), porque el popover ya no es descendiente DOM de `rootRef` una vez portado.
   Aplicado a `EleccionSelect.tsx` y `MetricSelect.tsx` — cualquier combobox nuevo con popover
   debería usar este mismo componente desde el principio, no reaccionar cuando se corte.
2. **Donuts reemplazados por un modo "Versus" con mapa** — el usuario aclaró que "comparar" para
   él siempre significó poder elegir un candidato puntual (fuerza entera o una lista/interna
   puntual) de una elección y enfrentarlo 1 contra 1 contra otro, viendo quién gana en cada
   circuito — no comparar 2 elecciones completas por %. Se sacaron `ComparisonPieCharts.tsx` y
   `PieChart.tsx` (borrados). Se agregó un tercer modo, `"ver" | "versus" | "comparar"`:
   - `VersusPanel.tsx` (nuevo): dos `CandidatoSelect.tsx` (selector de UN candidato — fuerza o
     lista puntual, mismo pool de filas que `MetricSelect` vía `buildFuerzaRows()`, sacada de
     `MetricSelect.tsx` a función exportada para no duplicarla). Default al entrar: si la fuerza
     líder tuvo interna, arranca comparando sus 2 candidatos principales (Lanús vs. Posse) — es
     el caso de uso que pidió el usuario, no un default genérico.
   - `MapView.tsx` ganó un prop opcional `versus?: VersusConfig` (`{keyA, keyB, colorA, colorB,
     labelA, labelB}`) — cuando está presente, el relleno de CADA circuito es
     `duoColor(metricValue(A) - metricValue(B), maxAbs, colorA, colorB, dark)` en vez de la
     métrica única del store, y el popup del hover muestra "A: x% / B: y% / Gana X" en vez del
     popup normal. El resto del mapa (zoom, bounds, highlight) no cambió.
   - `colors.ts`: `duoColor()` (escala divergente con los colores REALES de A y B, no rojo/verde
     fijo como `swingColor` — acá no hay "sube/baja" genérico, hay "va ganando X o Y") y
     `shade()` (aclara/oscurece un hex) — necesaria porque 2 candidatos de la MISMA interna
     comparten el hex de su fuerza; sin esto el mapa quedaría de un solo color. Nunca se inventa
     un color sin relación con la marca, solo se varía el tono del mismo hex de base.
   - En ese momento se mantuvo el modo "comparar" (2 elecciones completas, swing por fuerza) —
     ver v3.2 más abajo, se terminó sacando también en la misma sesión. `KpiHeader` no se
     renderiza en modo "versus" (VersusPanel trae su propio resumen).
   - `mapStore.ts` sumó `versusAKey`/`versusBKey` (`string | null`, con sus setters) — se
     resetean a `null` cuando cambia `actualId` (candidatos de la elección vieja no son válidos
     para la nueva).

**v3.2 — 4 ajustes chicos, misma sesión (2026-08-11):**

1. **Se sacó el modo "comparar" (2 elecciones completas) de la UI por completo.** El usuario lo
   pidió explícito ("el modo comparar elimínalo") — con Versus ya cubriendo lo que en la práctica
   quería decir "comparar" (ver v3.1), el modo viejo quedó redundante. `Modo` en `mapStore.ts` es
   ahora `"ver" | "versus"` nomás; se sacaron `baseId`/`setBaseId`/`invertir` del store (ya no
   hay "Desde"). Se borró `CompareCandidatesBanner.tsx` (quedó sin ningún consumidor). El backend
   (`comparacion.py`, `api.comparacion()` en el frontend) se dejó intacto por si se retoma más
   adelante, simplemente no hay ningún botón que lo dispare hoy.
   - `RankingList.tsx`, `DetailPanel.tsx`, `MapView.tsx` leían `compareMode` haciendo
     `useMapStore((s) => s.modo === "comparar")` — con "comparar" afuera del type `Modo` eso ya
     no compila, así que quedó como `const compareMode = false;` (literal, comentado). Sus
     ramas condicionadas a `compareMode` quedan sin usarse en la práctica pero el código no se
     tocó más allá de eso — si se necesita, retomar desde ahí en vez de reescribir. No se hizo una
     purga más profunda por tiempo, no porque las ramas sean necesarias.
2. **Nombres de cargo sin el "/a" de género neutro** ("Intendente/a" → "Intendente",
   "Presidente/a" → "Presidente") — así vienen guardados en `core.elecciones.nombre` /
   `categoria_nombre`, no se tocó el dato. `nombreCargo()` (nuevo, `lib/format.ts`) hace el
   reemplazo literal (no un regex genérico — son los únicos 2 cargos con esa marca en este
   dataset) solo al mostrar: título de la página (`MapPage.tsx`) y cada opción de
   `EleccionSelect.tsx`. Si se agrega un cargo nuevo con el mismo patrón de nombre, sumarlo ahí.
3. **`EleccionSelect` agrupa por AÑO, no por categoría/cargo** (pedido explícito, invierte lo que
   decía v3 sobre "San Isidro primero por categoría"). Grupos "2023"/"2025" en vez de
   "Intendente"/"Concejales"/etc., orden cronológico. Dentro de un año, ordena por fecha real y
   usa `ORDEN_CATEGORIAS` solo como desempate si dos elecciones comparten fecha exacta — no como
   criterio principal.
4. **Bug real en `VersusPanel.tsx`: el texto de cada fila de circuito se volvía ilegible cerca de
   un empate.** Causa: usaba `duoColor()` (el color YA mezclado con blanco, pensado para el
   relleno de la barra) también como `color` del texto — para un margen chico eso da un gris casi
   blanco sobre fondo blanco. Fix: separar `barColor` (el diluido, para el fill de la barra) de
   `textColor` (`diff >= 0 ? colorA : colorB`, el color sólido del candidato que lidera ESE
   circuito, nunca atenuado). Regla para el futuro: `duoColor`/`swingColor` (cualquier función que
   mezcle hacia un neutro) sirve para superficies (fondos, barras, relleno de mapa) — nunca para
   `color` de texto, que necesita contraste garantizado contra el fondo real.

**Fotos de candidatos:** `backend/app/core/candidatos.py` mapea `(categoria_id, lista_numero)` y
`(categoria_id, nombre_fuerza)` → `{nombre, foto}`. DINE no da el nombre de la persona, solo el
nombre de fantasía de la lista — el mapeo es manual, verificado contra prensa (ver
`frontend/public/candidatos/LICENSES.md` para fuentes y licencias de cada foto, todas de
Wikimedia Commons con licencia libre). Deliberadamente incompleto: mejor sin foto que mal
atribuida a una persona real — varios candidatos locales de San Isidro (Posse, Ruffa, Meca,
Paulucci) tienen nombre verificado pero no foto disponible, se muestran con iniciales
(`CandidateAvatar.tsx`). Si se agrega una categoría/elección nueva, hay que sumar sus candidatos
a mano en `candidatos.py` — no hay forma de inferirlos de la API.

Backend FastAPI + DuckDB, frontend React + Vite + MapLibre con mapa real (calles de
OpenStreetMap). Diseño: violeta claro (#F3EDFB) como fondo principal, tarjetas blancas, violeta
oscuro (#30115E) para texto/acentos, tipografía Montserrat. Mapa restringido a San Isidro (sin
pan, solo zoom, botón para volver a la vista original).

**Pasada de calidad visual (2026-08-10):** el usuario pidió explícitamente alejarse de un look
"muy minimalista/muy IA" — específicamente sacar el `<select>` nativo de `MetricSelect.tsx` (una
de las "cajitas genéricas") y sumar más profundidad/carácter a cada componente, sin tocar la
paleta ni las reglas de UX ya cerradas (`[[san-isidro-ux-feedback]]`: tabs/pills para ≤4
opciones, ícono direccional + cero explícito en swing). Cambios, todos en
`frontend/src/`:
- `index.css`: sistema de elevación con sombras teñidas de violeta (`--shadow-xs` a `--shadow-xl`,
  variable `--shadow-color: 271 45% 22%` en HSL — nunca gris neutro puro) expuesto como utilities
  Tailwind v4 (`@utility shadow-elevation-*`). Fondo del body con un radial-gradient sutil (violeta
  arriba-izquierda, teal arriba-derecha) en vez de un color plano. Scrollbar afinado en tono
  violeta. `:focus-visible` con outline violeta.
- `MetricSelect.tsx`: reescrito de cero como combobox propio (sin dependencia externa — el
  proyecto no tiene Radix/Headless UI instalado) — botón con swatch de color + label + chevron,
  popover con grupos "General"/"Fuerzas políticas", swatch de color por fuerza, checkmark en la
  seleccionada, navegación por teclado (↑↓/Enter/Escape) y cierre por click-fuera. Si se necesita
  otro selector con muchas opciones en el futuro, este es el patrón a reusar (no está extraído a
  un componente compartido todavía porque solo tiene un consumidor).
- `MapPage.tsx`: header con isotipo propio (`BrandMark`, cuadrado violeta redondeado), los dos
  paneles principales (mapa / circuitos) envueltos en un `Panel` común con barra de título +
  ícono (antes eran `<div className="rounded-3xl border">` sin identidad), estados de
  carga/error en `StateCard` en vez de texto suelto.
- `PillTabs.tsx`, `KpiHeader.tsx`, `CompareCandidatesBanner.tsx`, `RankingList.tsx`,
  `DetailPanel.tsx`: mismo lenguaje de elevación (`shadow-elevation-*`) aplicado de forma
  consistente; `KpiHeader` sumó un ícono propio por KPI (electores/mesas/participación/cambios).
- Verificado en el navegador (modo Ver y modo Comparar, con el combobox abierto y una fuerza
  seleccionada) — capturas en la sesión, no se dejaron guardadas como archivo.

**Segunda pasada — integración estructural (2026-08-10, misma sesión):** el usuario aclaró que la
pasada anterior mejoró el detalle pero no el problema de fondo: "componentes con un fondo blanco
en un flex común... se siente muy separado". El pedido era estructural, no decorativo — dejar de
tener N tarjetas independientes (`rounded-3xl border shadow` cada una) apiladas con `mb-6`/`gap`
en la página, y pasar a que la app se lea como pocas superficies conectadas. Se rehizo
`MapPage.tsx` así:
- **Un solo marco** (`divide-y divide-line`, un `border`/`shadow` para todo el bloque) para
  controles (Modo/Categoría/Etapa o presets+Desde/Hasta) + tira de KPIs + banner de comparación —
  antes eran 3 tarjetas separadas (`Panel` de controles, `KpiHeader`, `CompareCandidatesBanner`),
  ahora son 3 secciones internas de una misma superficie, separadas solo por un divisor.
- **Otro solo marco** (`lg:divide-x`) para Mapa + Circuitos — antes 2 `Panel` independientes cada
  uno con su propio borde/sombra/radio flotando uno al lado del otro; ahora son 2 columnas de una
  misma superficie con un divisor vertical.
- `KpiHeader.tsx` dejó de ser un grid de tarjetas (`Kpi` con `border`+`bg-surface-2` cada una) y
  pasó a ser una tira horizontal (`divide-x`, sin fondo/borde propio por ítem) — vive embebida
  dentro del marco de controles, no es una tarjeta más.
- `CompareCandidatesBanner.tsx` perdió su wrapper propio (`rounded-3xl border bg-surface-2`) — el
  padre le da el fondo/borde. Las filas de fuerzas pasaron de "tarjeta individual por fuerza"
  (cada una con su `border`+`shadow`) a filas de una lista con `divide-y` (como una tabla), salvo
  la fila destacada (`fuerzaFoco`) que sigue teniendo tratamiento propio a propósito —
  diferenciarla es funcional, no decorativo.
- El componente `Panel` (título+ícono por tarjeta) se reemplazó por `ColumnHeader` (misma idea
  pero sin el `rounded-3xl border shadow` propio, porque ahora el borde/sombra lo pone el marco
  compartido, no cada columna).
- Regla para el futuro: si se agrega una sección nueva a esta página, primero preguntarse a qué
  marco pertenece (¿es "control/estado" o es "contenido/exploración"?) y agregarla como sección
  interna con `divide-y`/`divide-x` de un marco existente — no crear una tarjeta `rounded-3xl
  border shadow` nueva al mismo nivel que las 2 que ya existen. Eso es exactamente lo que el
  usuario pidió evitar.

## Exportaciones (2026-08-10)

Botones "CSV" / "GeoJSON" en el header del panel "Circuitos" (`MapPage.tsx`, `ExportButtons`).
100% client-side — usan los datos que ya trajo React Query, no hay endpoint de backend nuevo.
Lógica en `frontend/src/lib/export.ts`:
- **CSV**: formato largo, una fila por (circuito × fuerza), no una fila por circuito con una
  columna por fuerza — evita que la forma del archivo cambie según cuántas fuerzas compitieron, y
  es la forma que mejor se lleva con tablas dinámicas de Excel/Sheets. Delimitador `;` (no `,`):
  Excel en configuración regional es-AR usa la coma como separador decimal del sistema operativo
  e ignora/rompe el `,` como separador de columnas aunque el archivo sea `.csv` — con `;` abre
  bien de una. BOM UTF-8 al principio del archivo para que los acentos no se rompan al abrir en
  Excel.
- **GeoJSON**: el `CircuitosGeoJSON` que ya tiene el frontend, tal cual (`JSON.stringify`) — es
  literalmente el mismo shape que devuelve `/mapa/circuitos` y `/mapa/comparacion`, no hace falta
  transformarlo.
- JSON "pelado" no tiene botón propio — ya se puede ver/guardar directo desde la respuesta de la
  API (`/api/v1/mapa/circuitos?eleccion_id=...`), agregar un botón hubiera sido redundante.
- Nombre de archivo armado con `slugify()` a partir del nombre de la elección activa (o
  `base_vs_actual` en modo comparar).
- Excel real (`.xlsx`) y Parquet quedaron afuera — el CSV con `;` ya abre bien en Excel sin
  librerías nuevas, y no hubo pedido concreto de ninguno de los dos formatos binarios.

## Filtros del panel Circuitos (2026-08-10)

`CircuitFilterBar.tsx`, arriba del ranking: buscador por número de circuito + rango min/max de
participación (en modo comparar, filtra por swing de participación — mismo campo
`participacion_pct` reinterpretado, igual que el resto de la UI en ese modo). Estado en
`mapStore.ts` (`filtro: FiltroCircuitos`, `setFiltro`, `limpiarFiltro`) — no se resetea al
cambiar de elección o de métrica, es intencional (un analista filtrando "circuitos con baja
participación" probablemente lo quiere mantener mientras explora otras cosas). Lógica de match
en `lib/filtros.ts` (`circuitoPasaFiltro`), separada de `colors.ts` a propósito para no mezclar
el helper de filtro con las utilidades de color/clasificación que no dependen del store.

**Cómo se propaga (importante si se toca esto):** el filtro nunca borra un circuito del todo, solo
reduce qué aparece en 2 lugares y atenúa un tercero:
- `RankingList` recibe `filteredData` (no `data`) — la lista de filas Y el `maxV`/`maxAbs` que
  escala las barras se calculan sobre el subconjunto filtrado, no sobre los 10 circuitos.
- `DetailPanel` recibe **los dos**: `data` completo (para resolver `activeCircuito` — un hover en
  el mapa puede caer en un circuito filtrado y tiene que poder mostrarlo igual) y `filteredData`
  (solo para el agregado "San Isidro, N circuitos" cuando no hay ninguno seleccionado).
- `MapView` sigue pintando los 10 circuitos siempre (nunca deja agujeros en el mapa) pero recibe
  `idsFiltrados: Set<string> | null` y baja `fill-opacity` a 0.12 (vs. 0.72 normal) para los que
  no matchean, vía una property `fuera_de_filtro` inyectada en `computeFills()` y una expresión
  MapLibre `["case", ["get","fuera_de_filtro"], 0.12, 0.72]`.
- `filteredData`/`idsFiltrados` están memoizados con `useMemo([data, filtro])` en `MapPage.tsx` a
  propósito — `activeCircuito` cambia en cada hover del mapa y no tiene que recalcular el filtro
  ni retriggerear un repintado de MapView en cada movimiento del mouse.

## Datos parciales / no definitivos (2026-08-10)

Hasta ahora toda elección cargada tenía SIEMPRE electores/mesas/votantes/participación completos
por circuito (vienen de una fuente oficial con conteo real). Las primeras que no los tienen son
`SENADORES2025PBA_PARCIAL` y `CONCEJALES2025PBA_PARCIAL` (ver docs/DATA_SOURCES.md, sección
"Senadores Provinciales + Concejales (septiembre)" — ambas transcriptas a mano de capturas de una
app cuyo backend ya no está online: Senadores 2026-08-10, Concejales 2026-08-11, mismo patrón,
mismo loader — ver `backend/etl/load_concejales_pba_2025_parcial.py`). Esto obligó a que
`CircuitoProperties` (`frontend/src/lib/api.ts`) trate `mesas`, `electores`, `votantes`,
`positivos`, `blanco`, `nulos`, `participacion_pct` como `number | null`, y `FuerzaDetalle.votos`
también — antes eran `number` a secas.

**Si se agrega otra fuente parcial en el futuro, estos son los puntos que ya están preparados
(no hace falta re-descubrirlos):**
- `lib/format.ts` — `sumOrNull()` (suma tolerante a null: si TODOS los valores de un array son
  `null` devuelve `null` en vez de un `0` engañoso) y `fmtNum()` (formatea `null` como "—").
  Usado en `KpiHeader.tsx` y `DetailPanel.tsx` para los totales agregados.
- `lib/colors.ts` — `metricValue()` para la métrica "Participación" hace `?? 0` explícito: es un
  valor puramente numérico para colorear/ordenar, nunca se muestra como texto directamente, así
  que 0-como-placeholder ahí es seguro (documentado inline por qué).
- `DetailPanel.tsx`, función `aggregateAll()` — si el total de votos reales da 0 (todos `null`),
  cae a promediar el `%` entre circuitos en vez de dividir por un total en cero. Mismo patrón en
  `KpiHeader.tsx` para elegir el "líder" cuando no hay conteo de votos.
- `MetricSelect.tsx` — arma la lista de fuerzas seleccionables como la **unión** de
  `detalle[]` de TODOS los circuitos (con el mayor % visto de cada una para ordenar), no solo
  `features[0]`. Esto lo rompía una fuente parcial donde cada circuito trae un subconjunto
  distinto de fuerzas (p.ej. "top 3" de una tarjeta) — con datos completos da exactamente el
  mismo resultado que antes, así que quedó así para siempre, no es un caso especial.
- `core.resultados_circuito.votos` es nullable en el esquema (antes `NOT NULL`) — ver comentario
  en `database/schema.sql`. Nunca completar con `0` cuando no se sabe el conteo real: `0`
  significa "cero votos", no "dato desconocido".
- El nombre de la elección (`core.elecciones.nombre`) debe decir explícitamente "PARCIAL" o "no
  definitivo" cuando corresponda — es lo único que le avisa al usuario en el título de la página
  que estos números no son comparables 1:1 con el resto. No hay ningún indicador visual aparte
  de eso todavía (si se agrega una segunda fuente parcial, capaz vale la pena un badge propio en
  vez de depender solo del texto del título).

## Cómo cargar una elección/categoría nueva

Desde que hay más de una categoría (Presidente + Intendente), el patrón pasó a ser genérico en
vez de un script por combinación tipo+categoría:

1. `backend/importers/sources/dine/import_circuito_categoria.py --eleccion-id <ID> --anio <AAAA>
   --tipo-eleccion <PASO|GENERAL|BALLOTAGE> --categoria-id <N>` — descarga raw desde DINE, un
   archivo por circuito + manifest. Ver docs/DATA_SOURCES.md para el mapeo de `categoriaId` y
   qué categorías existen realmente para Buenos Aires (usar `/api/menu?año=<AAAA>` para
   verificar antes de asumir — Concejales, por ejemplo, no está).
   - **Si esto devuelve todo en cero a nivel circuito** (pasó con Ballotage 2023 — la API en vivo
     no sirve ese round a ese nivel para ningún distrito, no es un problema de San Isidro): antes
     de dar el dato por bloqueado, probar
     `backend/importers/sources/dine/import_from_bulk_csv.py`, que lee el ZIP mesa-por-mesa
     publicado en el catálogo `datos.gob.ar` (no enlazado desde la web normal de DINE, hay que
     buscarlo en el dataset CKAN `resultados-provisionales-elecciones-20231`) y agrega
     mesa→circuito al mismo formato raw — produce exactamente lo que este script produciría si
     funcionara. Ver docs/DATA_SOURCES.md, sección "Ballotage 2023", para el detalle completo y
     cómo se verificó contra el agregado oficial.
2. `backend/etl/load_circuito_categoria.py --eleccion-id <ID> --nombre "..." --tipo <...>
   --ambito <NACIONAL|PROVINCIAL|MUNICIPAL> --fecha AAAA-MM-DD --anio <AAAA> --categoria-nombre
   "..." [--comparable-id <otro-eleccion-id>]` — lee el raw y puebla `core.*` (incluyendo
   `core.resultados_circuito_lista`, el desglose de listas internas) +
   `marts.agregados_territoriales`. Idempotente (DELETE+INSERT por `eleccion_id`).
   - Si vas a linkear PASO↔Generales con `--comparable-id`, cargá primero la elección
     referenciada (la FK falla si no existe todavía).
   - Los scripts viejos `import_paso_2023_san_isidro.py` / `load_paso_2023_san_isidro.py` (y su
     par de Generales) quedan como están, funcionando — no hace falta migrarlos.
3. **Gotcha:** el upsert de `core.circuitos`/`core.municipios` (geometría, no cambia entre
   elecciones) debe ser `ON CONFLICT DO NOTHING`, nunca `DO UPDATE`. DuckDB implementa el UPDATE
   como delete+insert internamente, lo que rompe la FK de `core.resultados_circuito` en cuanto ya
   hay una elección previa cargada referenciando esas filas.
4. **Gotcha de schema:** si el cambio agrega una categoría/tabla nueva y toca un `CHECK` de una
   tabla que ya existe en el `.duckdb` (p.ej. agregar `'MUNICIPAL'` a `ambito`), DuckDB no lo va
   a aplicar solo (`CREATE TABLE IF NOT EXISTS` no altera tablas existentes, y DuckDB no soporta
   bien `ALTER TABLE` sobre `CHECK`). Más simple para una DB de dev local: borrar
   `database/san_isidro.duckdb` y re-correr todos los loaders existentes — es rápido y
   reproducible, todo el raw ya está en `data/raw/`.
5. **Gotcha de proceso backend:** si el backend está corriendo sin `--reload` (revisar con
   `ps aux | grep uvicorn`), un cambio en `app/repositories/*.py` no se refleja hasta reiniciarlo
   a mano. Arrancarlo con `--reload` (ver README.md) para no pisarse con esto de nuevo.

## Gotchas ya resueltos — no los vuelvas a pisar

- **Vite y MapLibre están pineados a propósito**: `vite@6.4.3` y `maplibre-gl@5.24.0` en
  `frontend/package.json`. Las versiones más nuevas (Vite 8.x, MapLibre 6.x) tienen un bug real de
  empaquetado del Web Worker de MapLibre que deja el mapa sin tiles. Si se actualiza, verificar el
  mapa antes de dar por bueno el upgrade.
- **Tailwind v4 dark mode**: nunca anides `@theme { ... }` dentro de un `@media`. Tailwind lo
  procesa como si fuera global igual, ignora el `@media`. Los overrides de tema van con
  `:root { --color-x: ...; }` normal dentro del `@media`, no con otro `@theme`. Ver
  `frontend/src/index.css` para el patrón correcto.
- **No hay dark mode automático**: se sacó a propósito (pedido explícito: blanco siempre, sin
  importar el sistema operativo del usuario). Si se quiere reintroducir, que sea un toggle manual,
  no `prefers-color-scheme`.
- **`.claude/launch.json` vive en `~/.claude/launch.json`** (carpeta home), no en este repo — ahí
  también está la config de otro proyecto del usuario ("treasurer-dev"). No lo pises, solo agregá
  entradas nuevas si hace falta.
- **Nivel de dato: circuito, no mesa.** Se investigó a fondo (ver DATA_SOURCES.md) y no se encontró
  fuente pública automatizable para el detalle mesa/escuela en Buenos Aires. No perder tiempo
  re-investigando esto sin una pista nueva concreta.
- **`PARTY_HEX` (`frontend/src/lib/colors.ts`) — las claves nunca llevan el prefijo "ALIANZA ".**
  El backend (`normalizar_nombre_fuerza`) ya lo saca antes de guardar `nombre_normalizado`, que es
  el nombre que de verdad llega al frontend — una clave `"ALIANZA X"` en este mapa nunca hace
  match y la fuerza cae en el gris de `PARTY_HEX_OTHER` en silencio (pasaba con Somos Buenos
  Aires, Potencia y Provincias Unidas hasta 2026-08-11). Si se agrega una fuerza nueva, la clave
  va con el nombre tal cual queda en `core.fuerzas_politicas.nombre_normalizado` — verificar con
  una query a esa tabla antes de asumir el nombre "de boletín".

## Cómo levantar todo

```bash
cd backend && source ../.venv/bin/activate && PYTHONPATH=. uvicorn app.main:app --port 8000 --reload
cd frontend && npm run dev
```

Abrir `http://localhost:5173`.
