# Fuentes de datos — hallazgos técnicos verificados

Este documento registra lo verificado empíricamente contra la API real de DINE (no la
documentación de apidocs.ar, que describe una versión anterior/paralela con datos de muestra
poco fiables para consultas amplias). Todo lo de abajo fue probado con `curl` contra endpoints
oficiales y contrastado con cifras públicas conocidas.

## API DINE — `resultados.mininterior.gob.ar/api`

Sin autenticación para lectura. Tres familias de endpoints relevantes:

### 1. `/resultado/totalizado` — agregados por distrito (confirmado, robusto)

```
GET /api/resultado/totalizado?año=2023&recuento=Provisorio&idEleccion=1&idCargo=1&idDistrito=2
```
- `idEleccion`: 1=PASO, 2=Generales, 3=Ballotage (a confirmar para 2do turno, no probado aún)
- `idCargo` = categoriaId (ver mapeo abajo)
- `idDistrito`: ordinal propio de este sistema, **no es el código INDEC**: 0=Argentina (total país),
  1=CABA, 2=Buenos Aires, 3=Catamarca, 4=Córdoba, 5=Corrientes, 6=Chaco, 7=Chubut, 8=Entre Ríos,
  9=Formosa, 10=Jujuy, 11=La Pampa, 12=La Rioja, 13=Mendoza, 14=Misiones, 15=Neuquén, 16=Río Negro,
  17=Salta, 18=San Juan, 19=San Luis, 20=Santa Cruz, 21=Santa Fe, 22=Santiago del Estero,
  23=Tierra del Fuego, 24=Tucumán (confirmado vía links `/resultados/2023/1/1/{n}` del propio frontend)
- Verificado: `idDistrito=2` (Buenos Aires) PASO 2023 Presidente → total 8.902.113 votos,
  coincide con resultados públicos conocidos.
- Devuelve el detalle completo por agrupación y lista (no solo top 2).

### 2. `/mapas?tipo=departamentos` — agregado + polígono por partido/municipio (confirmado)

```
GET /api/mapas?año=2023&recuento=Provisorio&idEleccion=1&idCargo=1&idDistrito=2&id_indra=02&tipo=departamentos&minimizado=true
```
- Devuelve un FeatureCollection GeoJSON con los 135 partidos de Buenos Aires.
- Cada feature trae `PROVINCIA`, `DPTO` (nombre), `INDEC_PD` (código INDEC completo, p.ej. `06756`
  para San Isidro), geometría del partido, y **solo** primera y segunda fuerza (`agrupacion`,
  `segunda_fuerza`) — no el detalle completo de todas las listas.
- Verificado para San Isidro: JxC 94.681 votos (49.67%), LLA 39.833 (20.90%) — consistente con lo
  esperado (San Isidro fue bastión PRO/JxC en 2023).
- `tipo=circuitos` / `tipo=secciones` **no funcionan** con los parámetros probados (siempre
  `{"mesanje":"Error al obtener el mapa"}`) — no hay nivel de circuito disponible por esta vía.
  El polígono de partido sirve para el mapa de San Isidro completo; el de circuito queda pendiente
  (ver `core.circuitos.geom = NULL` en el esquema, previsto en ARCHITECTURE.md §7).

### 3. `/resultados/getResultados` — consulta por circuito/mesa (confirmado, requiere IDs exactos)

Esta es la API documentada oficialmente en `/desarrollo` con ejemplo funcional. **Importante:**
solo devuelve datos correctos cuando se especifica `circuitoId` (o `circuitoId`+`mesaId`) — si se
la llama solo con `distritoId` o con `seccionProvincialId` sin acotar más, devuelve datos vacíos,
truncados a un subconjunto pequeño sin avisar, o directamente 503. **Nunca usar esta API sin
circuitoId explícito.**

```
GET /api/resultados/getResultados?anioEleccion=2023&tipoRecuento=1&tipoEleccion=1&categoriaId=1&distritoId=2&circuitoId=00890
```
- `circuitoId` debe ir **zero-padded a 5 caracteres** (`"890"` → `"00890"`; el circuito con sufijo
  de letra `"0892A"` ya viene así de 5 caracteres desde la fuente, sin padding adicional).
- Sin `mesaId`, agrega todas las mesas del circuito (confirmado: circuito 00890 → 11 mesas, 3.547
  electores, con desglose completo por agrupación y lista).
- Con `mesaId` agrega una sola mesa (confirmado con el ejemplo oficial de la doc: circuito 000039
  de CABA, mesa 1244 → 347 electores, desglose por lista).
- **Pendiente/no resuelto:** no encontramos un endpoint que liste los `mesaId` válidos por
  circuito. La documentación de DINE menciona una exportación CSV masiva ("incluye todas las
  mesas del ámbito de la consulta") accesible desde el botón "Descargar CSV" de cada página de
  resultados, pero no se pudo capturar la URL real del endpoint subyacente vía el navegador
  (no se registró la request de red, probablemente por manejo de descarga vía blob/JS en vez de
  navegación). **Fast-follow:** repetir esta captura con DevTools reales o probar variantes de
  `/api/resultado/csv` (ruta que sí existe — devuelve 409 en vez de 404 — pero no encontramos aún
  la combinación de parámetros que acepta).

### Mapeo `categoriaId` (= `idCargo`) confirmado desde el frontend (año 2023)

| categoriaId | Cargo |
|---|---|
| 1 | Presidente/a |
| 2 | Senadores/as nacionales |
| 3 | Diputados/as nacionales |
| 4 | Gobernador/a |
| 5 | Senadores/as provinciales |
| 6 | Diputados/as provinciales |
| 7 | Intendente/a |
| 8 | Parlamento Mercosur nacional |
| 9 | Parlamento Mercosur regional |
| 10 | Concejal |

## Circuitos electorales de San Isidro (confirmado, fuente oficial separada)

La API de DINE no tiene un endpoint público para enumerar circuitos por partido. Se resolvió con
el dataset oficial **"Circuitos Electorales PBA"** (Poder Judicial de la Nación, publicado en el
portal de datos abiertos de la Provincia de Buenos Aires):

- Catálogo: https://catalogo.datos.gba.gob.ar/dataset/circuitos-electorales
- CSV: https://catalogo.datos.gba.gob.ar/dataset/4fe68b69-c788-4c06-ac67-26e4ebc7416b/resource/43d4314f-c540-4b00-8c41-1104141bda19/download/circuitos-electorales-pba.csv
- También disponible en XLSX y en ZIP con geometrías (.shp/.geojson/.kml, EPSG:4326).
- Guardado en `data/raw/geo_source/circuitos-electorales-pba.csv`.

**Circuitos de San Isidro** (`municipio_id=06756`, `indec_municipio=756`): 887, 888, 889, 890,
891, 892, 0892A, 893, 894, 895 (10 circuitos).

Suma de electores de estos 10 circuitos en PASO 2023 (categoría Presidente): **≈272.157**
(235.891 de los 9 circuitos numéricos + 36.266 de 0892A), del orden correcto para el padrón de
San Isidro.

## Nivel mesa (escuela) — investigación adicional, sin resolver

Se dedicó una segunda ronda de investigación específicamente a esto. Hallazgos:

- La Cámara Nacional Electoral (CNE, `old.pjn.gov.ar/cne/secelec/document/otros/`) publica, para
  varias provincias, un PDF tipo "Ubicaciones de Mesa" / "Guía de Locales de Votación" con
  exactamente el formato necesario: circuito, establecimiento, domicilio, cantidad de mesas,
  mesa desde/hasta. Confirmado para Salta, La Rioja, Santa Fe, y otras — **no encontrado para
  Buenos Aires** pese a probar ~20 variantes de nombre de archivo. Buenos Aires parece no publicar
  un equivalente consolidado en esa carpeta (posiblemente por su tamaño: ~38.000 mesas en 135
  municipios, contra unos pocos miles en provincias chicas).
- Los archivos con prefijo `2-` (Buenos Aires) que sí existen ahí (`2-SAN ISIDRO.pdf`,
  `2-AVELLANEDA.pdf`) resultaron ser **certificados de escrutinio en blanco** (el acta que llena
  cada presidente de mesa), no listados de establecimientos. Confirmamos de paso el código de
  sección electoral de San Isidro: **106**, y la lista de agrupaciones que compitieron en la
  Legislativa Nacional 2025.
- `padron.gba.gob.ar` (consulta de padrón bonaerense) es una herramienta de temporada — solo
  activa durante el período electoral y solo para consulta individual (no es un listado
  navegable de escuelas/circuitos), por lo que no aplica aquí ni sería apropiado usarla así aunque
  estuviera activa.
- El botón "Descargar CSV" del sitio de DINE, pese a que la documentación oficial dice que
  incluye "todas las mesas del ámbito de la consulta", no generó ninguna request de red
  interceptable (con `fetch`/`XHR` parcheados) — sugiere que arma el CSV en el cliente a partir de
  datos ya cargados (que a nivel distrito no incluyen mesas), no que consulte mesa por mesa.

**Conclusión:** con las fuentes públicas indexadas y accesibles hoy, no se pudo armar de forma
automática el mapeo mesa→escuela para San Isidro. El circuito (10 zonas) sigue siendo el nivel de
detalle real disponible para PASO 2023. Alternativas para cerrar esto en el futuro, en orden de
preferencia: (1) pedir directamente a la Junta Electoral PBA o a la Secretaría Electoral de
Buenos Aires el archivo equivalente (probablemente lo tengan, solo no está en esa carpeta pública
indexada); (2) revisar si el escrutinio definitivo — no el provisorio que usa esta API — publica
telegramas escaneados por mesa con la escuela impresa, y extraer de ahí; (3) aceptar circuito como
grano definitivo para 2023 y solo perseguir mesa-nivel para las elecciones 2025 en adelante, donde
puede haber mejores fuentes (la Boleta Única Papel cambió el sistema de telegramas).

**Actualización 2026-08-10 — sí hay datos a nivel MESA, falta el mapeo a escuela:** investigando
Ballotage 2023 (ver sección "Ballotage 2023" más abajo) apareció una fuente que no se había
encontrado antes: los ZIP de `datos.gob.ar` (`2023_generales_1.zip`, `2023_segundavuelta.zip`,
etc., no enlazados desde la web normal de DINE, solo desde el catálogo CKAN) traen el resultado
**mesa por mesa** (columna `mesa_id`, `mesa_electores`) de toda la elección, no solo circuito.
Sigue faltando el mapeo `mesa_id → establecimiento/domicilio` (lo que esta sección de arriba no
pudo resolver) para poder mostrar "por escuela" en el mapa, pero el techo real ya no es "no hay
dato de mesa" — es "hay voto por mesa pero no sabemos en qué escuela vota cada mesa". Si se
retoma esto, arrancar buscando esa tabla de equivalencia en vez de re-investigar el nivel de
voto, que ya está resuelto.

**Resuelto 2026-08-22 — mapeo mesa→escuela cargado, para 2025 en adelante:** el ZIP de
`elecciones_legislativas_2025.zip` (mismo dataset que carga Diputados Nacionales 2025, ver
sección de abajo) trae un archivo separado, `localesDeVotacionyMesas.csv`, que 2023 nunca tuvo:
nombre de escuela, dirección y localidad por `mesa_id` (778 mesas de San Isidro, 125 escuelas
únicas). Cruza limpio contra el CSV de resultados por `mesa_id` (**ojo:** `mesa_id` NO es único
en toda la provincia, se reinicia por circuito en otros municipios — hay que restringir a los
circuitos de San Isidro ANTES de armar el cruce, no después, o se pisa el mapeo con mesas de
otro lado). El archivo no trae lat/lon, así que se geocodificó cada escuela contra Nominatim
(1 req/seg): 104/125 con una sola pasada + reintento (el símbolo "N°" de la fuente rompe el
parser de Nominatim — sacarlo resuelve la mayoría; el resto son direcciones "entre calles" sin
altura o con abreviaturas que Nominatim no resuelve, se dejaron sin geocodificar en vez de
adivinar). Implementado en
`backend/importers/sources/dine/import_locales_votacion.py` (bronze, con cache de geocoding
entre corridas) + `backend/etl/load_locales_votacion.py` (puebla `core.establecimientos` +
`core.mesas`, tablas que ya estaban en el schema esperando esto). Expuesto en
`GET /api/v1/mapa/establecimientos?eleccion_id=...` y como capa de puntos en el mapa
(`MapView.tsx`) — **solo geografía + mesas/electores por ahora, no voto por escuela** (eso
necesitaría cargar `core.resultados_mesa`, que sigue vacía; el dato ya está en el mismo CSV de
resultados si se retoma esto). Solo cubre elecciones 2025 en adelante — 2023 sigue sin esta
fuente, ver más arriba.

## Concejales — no publicado por DINE para Buenos Aires (confirmado)

DINE expone un endpoint `/api/menu?año={anio}` que arma los propios filtros del sitio
(categoría → distrito → sección provincial → sección), útil para verificar qué combinaciones
tienen datos reales antes de gastar tiempo adivinando parámetros contra `getResultados`. Para
2023 (`PASO` y `Generales`), el cargo **CONCEJAL (categoriaId=10)** solo tiene distritos
`Catamarca` (PASO) y `Ciudad Autónoma de Buenos Aires` + `Catamarca` (Generales) — **Buenos
Aires no está**, ni en PASO ni en Generales. Confirmado también de forma negativa contra
`getResultados` (circuito 00890, categoriaId 10 y un rango 10-25: siempre 0 agrupaciones) y
contra `/api/mapas?tipo=departamentos&idCargo=10` (0 features). Concejales es una categoría
100% provincial/municipal — cada provincia corre esa elección con su propia junta electoral, y
la de Buenos Aires evidentemente no le pasó esos datos a DINE en 2023. Para conseguirlos habría
que ir a la Junta Electoral de la Provincia de Buenos Aires, la misma fuente ya pendiente de
investigar para la elección provincial 2025 (ver más abajo) — sin API pública documentada.

**Decisión del usuario:** no perseguir esta fuente por ahora — Intendente y Concejales van en
la misma boleta ("lista sábana") en 2023, así que el % de cada fuerza es prácticamente el mismo
entre ambas categorías. Los datos de Intendente (con desglose de listas internas) cubren la
necesidad real.

## Ballotage 2023 — la API en vivo no sirve circuito, pero el CSV masivo sí (resuelto 2026-08-10)

Intento de cargar la Segunda Vuelta (19/11/2023, Presidente/a) con el patrón genérico
(`import_circuito_categoria.py`, que usa `/resultados/getResultados`). `idEleccion=3` ("Segunda
Vuelta") sí existe en `/api/menu?año=2023` con cargo Presidente/a y distrito Buenos Aires
listado — pero **`/resultados/getResultados` devuelve `mesasTotalizadas: 0` y arrays vacíos para
tipoEleccion=3 en absolutamente todos los circuitos probados**, tanto de San Isidro (00887,
00888, 00890, 00892) como de un circuito de control fuera de Buenos Aires (CABA 000039, con y
sin `mesaId`) — no es un problema de San Isidro puntual, ese endpoint en vivo simplemente no
sirve resultados de Ballotage a nivel circuito para ningún distrito. `/resultado/totalizado` y
`/mapas?tipo=departamentos` sí devuelven Ballotage, pero solo agregado (provincia completa o
partido/municipio completo, sin desglose de circuito).

**La solución fue no usar la API en vivo para esto.** DINE publica por separado, en el catálogo
de datos abiertos (`datos.gob.ar`, CKAN — **no enlazado desde la página normal de
resultados**, hay que ir al dataset "Resultados Provisionales Elecciones 2023" del Ministerio
del Interior, `datos.gob.ar/api/3/action/package_show?id=resultados-provisionales-elecciones-20231`),
un ZIP por ronda con el resultado completo **mesa por mesa** de todo el país:

- PASO: `https://www.argentina.gob.ar/sites/default/files/dine-resultados/2023-PROVISORIOS_PASO.zip`
- Generales: `https://www.argentina.gob.ar/sites/default/files/2023_generales_1.zip` (~1GB
  descomprimido, sí está enlazado desde la web normal de DINE)
- **Segunda Vuelta: `https://www.argentina.gob.ar/sites/default/files/2023_segundavuelta.zip`**
  (~120MB descomprimido — bastante más chico, tiene sentido, la Segunda Vuelta es 1 sola
  categoría con 2 agrupaciones en vez de las ~10 categorías simultáneas de una Generales)

Cada CSV adentro (`ResultadosElectorales_2023_SegundaVuelta.csv`, mismo patrón para las otras
rondas) trae una fila por (mesa, agrupación, tipo de voto) con columnas `distrito_id`,
`circuito_id` (zero-padded igual que la API en vivo), `mesa_id`, `mesa_electores`, `cargo_id`,
`cargo_nombre`, `agrupacion_id`, `agrupacion_nombre`, `votos_tipo`
(`POSITIVO`/`EN BLANCO`/`NULO`/`IMPUGNADO`/`RECURRIDO`), `votos_cantidad`. Agregando mesa→circuito
(sumar `votos_cantidad` por circuito+agrupación, sumar `mesa_electores` una vez por mesa, contar
mesas distintas) se reconstruye exactamente el mismo shape que ya usa el resto del proyecto.
**Verificado:** la suma de votos positivos de los 10 circuitos de San Isidro dio **201.163**,
idéntico al agregado oficial de `/mapas?tipo=departamentos` (130.059 LLA + 71.104 UP) — confirma
que el filtro/agregación es correcto, no hay fuga ni doble conteo.

Implementado en `backend/importers/sources/dine/import_from_bulk_csv.py` — descarga el ZIP,
agrega mesa→circuito, y escribe el mismo formato raw (un JSON por circuito + `_manifest.json`)
que `import_circuito_categoria.py`, así `load_circuito_categoria.py` corre sin cambios sobre
cualquiera de las 2 fuentes. Ballotage 2023 (Presidente/a, San Isidro) ya está cargado
(`eleccion_id=BALLOTAGE2023`, `--comparable-id GENERALES2023`).

**Implicancia para el futuro — nivel mesa/escuela:** estos mismos ZIPs son **mesa por mesa**, no
circuito. La plataforma sigue agregando a circuito porque eso es lo que carga el loader hoy, pero
la fuente para bajar a mesa (el bloqueo histórico documentado más abajo) puede estar resuelta acá
mismo — falta el mapeo mesa→escuela/establecimiento (domicilio), que estos CSV no traen. Antes de
retomar "Nivel mesa" como blocked, revisar si esta misma fuente sirve.

## Intendente/a — funciona igual que Presidente, con un plus: listas internas

`categoriaId=7` sí está disponible para Buenos Aires (confirmado vía `/api/menu`, distritos
`[2, 3]` = Buenos Aires + Catamarca) y responde igual que Presidente en `getResultados`
(circuito por circuito). La diferencia útil: cada `agrupacion` en `valoresTotalizadosPositivos`
trae un array `listas` (`nombre`, `numero`, `votos`) con el desglose de precandidatos internos
de la PASO — esto es lo que permite diferenciar, por ejemplo, los 2 candidatos a intendente que
tuvo JxC en San Isidro 2023 ("Con Vocación Por El Cambio San Isidro" vs. "Falta Menos Para Vivir
Sin Miedo"). En Generales normalmente hay 1 lista por fuerza (el candidato que ganó la interna),
pero se carga la misma estructura para no tener un caso especial — ver
`core.resultados_circuito_lista` en el schema.

**Ojo con "electores"/"mesas" por categoría:** para un mismo circuito, `cantidadElectores` y
`mesasTotalizadas` pueden diferir levemente (o no tan levemente: hasta ~30% en algunos
circuitos de San Isidro) entre Presidente e Intendente. Es un artefacto de cómo DINE totaliza
el recuento rápido/provisorio — cada categoría de un mismo telegrama puede haberse cargado a un
ritmo distinto en 2023 — no un error de la carga. No asumir que dos categorías de la misma
elección tienen exactamente el mismo universo de mesas computadas.

## Elecciones 2025 — dos elecciones separadas, San Isidro

2025 tuvo dos elecciones distintas para San Isidro (Kicillof separó el calendario provincial del
nacional): **7 de septiembre** (provincial — Senadores Provinciales por la 1ra Sección, Concejales
por San Isidro) y **26/28 de octubre** (nacional — Diputados/as Nacionales por la provincia de
Buenos Aires, vía DINE). Investigado 2026-08-10.

### Diputados Nacionales (octubre) — CARGADA (2026-08-11), id `DIPUTADOS2025`

Igual que Ballotage 2023: la API en vivo de DINE (`/resultados/getResultados`) devuelve vacío a
nivel circuito para `categoriaId=3` (Diputado Nacional) año 2025, pero el CSV masivo mesa-por-mesa
sí lo tiene — dataset `elecciones_legislativas_2025` en `datos.gob.ar`
(`https://datos.mininterior.gob.ar/dataset/947e871a-650e-4b63-8939-ecb29acb717c/resource/a24110fb-bfcf-47a6-8aa7-2e53dab9caf5/download/elecciones_legislativas_2025.zip`,
~13.5MB, el CSV adentro sin comprimir pesa ~458MB). Se cargó con `import_from_bulk_csv.py` sin
cambios (mismo generalizado que ya usa Ballotage — `distrito_id="2"` = Buenos Aires,
`cargo_nombre="DIPUTADO NACIONAL"`, `--categoria-id 3`), 15.560 filas mesa-nivel matcheadas
para los 10 circuitos de San Isidro, después `load_circuito_categoria.py --tipo GENERAL
--ambito NACIONAL --fecha 2025-10-26`. Sin PASO (no hubo instancia PASO nacional en 2025), así
que es una elección de una sola ronda, sin `--comparable-id`.

**Fuerzas nuevas que aparecieron en esta elección** (no estaban en 2023): JxC ya no compitió
como marca única a nivel nacional — se dividió, y el sello PRO se presentó como "PROPUESTA
FEDERAL PARA EL CAMBIO" (le fue chico en San Isidro, ~2% — LLA y UP dominan la categoría acá).
Se agregó color propio en `PARTY_HEX` (`frontend/src/lib/colors.ts`) para esa fuerza; el resto
de las fuerzas chicas (Frente Patriota Federal, Liber.Ar, Nuevos Aires, etc., todas <1.5%)
quedan en el gris de `PARTY_HEX_OTHER`, mismo criterio que siempre.

**Sin candidato individual mapeado en `candidatos.py` todavía** — a diferencia de Presidente/
Intendente, no se verificó contra prensa quién encabezó cada lista de diputados por la 1ra
sección para esta carga. Mismo criterio de "mejor sin foto/nombre que mal atribuido": la
categoría anda bien igual (usa el nombre de fuerza, `CandidateAvatar` cae a iniciales) — si se
necesita, sumarlo a mano ahí como cualquier categoría nueva.

**Bonus en este mismo ZIP:** trae un archivo nuevo, `localesDeVotacionyMesas.csv` (16.5MB), que
los datasets de 2023 no tenían — nombre de escuela, dirección, localidad por mesa. No trae
`circuito_id` directo (solo `seccion_id`), pero se puede cruzar por `mesa_id` contra
`resultados2025.csv` (que sí tiene circuito) para armar mesa→circuito→escuela. Relevante para
"Nivel mesa/escuela" (ver esa sección más arriba) — para 2025 en adelante, no para 2023.

### Senadores Provinciales + Concejales (septiembre) — techo real: municipio, no circuito

Se investigó a fondo (varias rondas, incluyendo pedido explícito del usuario de revisar de nuevo
porque debería ser público). Conclusión, confirmada por **3 fuentes independientes**:

1. **PDFs oficiales de escrutinio definitivo** (`juntaelectoral.gba.gov.ar`) — Concejales sí
   tiene desglose por distrito (`escrutinio-definitivo-2025/concejales/2025106.pdf` para San
   Isidro — código de distrito 106), con todas las fuerzas, electores, mesas y candidatos
   electos. Senadores Provinciales **solo existe a nivel de toda la 1ra Sección** (24 municipios
   juntos, `secciones.php?seccion=1` → `resultados/2025sec1.pdf`) — nunca por distrito.
2. **La página de resultados históricos del sitio** (`distritoEstadisticasHistoricas.php?anio=2025&did=106`)
   — mismo techo: Concejales por distrito, Senadores solo agregado de sección.
3. **El árbol de datos interno de la app oficial "Elecciones Bonaerenses 2025"** (recuperado de
   Wayback Machine, `resultados.eleccionesbonaerenses.gba.gob.ar/backend-difu/nomenclator/getNomenclator`
   — 11.8MB, el nomenclador que arma toda la jerarquía geográfica). Confirma que el nivel
   "Circuito" (l=50) está definido en el esquema pero **no tiene un solo nodo poblado** para
   Senadores (`elec=5`) ni Concejales (`elec=7`) en San Isidro — el árbol salta directo de
   Municipio (l=40) a Colegio (l=60). No es que no se haya publicado en algún lado que no se
   encontró: el sistema que la Junta Electoral usó para tabular estas categorías **nunca las
   agregó por circuito**, solo por colegio/mesa y por municipio/sección.

El backend de esa app (`resultados.eleccionesbonaerenses.gba.gob.ar` y
`api.eleccionesbonaerenses.gba.gob.ar`, ambos CloudFront) está dado de baja desde después de la
elección — confirmado por DNS (CNAME a una distribución ya eliminada, sin registro A). Wayback
Machine solo capturó 163 URLs de esa app en total, ninguna con los resultados finales de San
Isidro por colegio/mesa (las que sí capturó son de la noche de la elección, con votos en cero, o
del nivel Sección nada más).

**Dato cargado igual, con salvedades explícitas — `SENADORES2025PBA_PARCIAL`:** el usuario
todavía tenía la app instalada en su teléfono (mostraba un estado cacheado, ya que el backend
real está caído) y mandó capturas de pantalla con el desglose por circuito de Senadores
Provinciales que la app sí mostraba en su momento — confirma que la app llegó a tener esa
granularidad aunque el sistema no la conserve hoy. Se transcribió a mano
(`backend/etl/load_senadores_pba_2025_parcial.py`) con limitaciones marcadas explícitamente:
- "Escrutado" entre 93,93% y 100% según circuito (no es el definitivo).
- Solo top 3 fuerzas por tarjeta (nunca suma 100%, faltan las chicas).
- Sin electores/mesas/participación/blanco/nulos por circuito.
- `votos` queda `NULL` (solo hay %) — requirió aflojar `core.resultados_circuito.votos` a
  nullable (antes `NOT NULL`), ver comentario en `database/schema.sql`.

El nombre de la elección incluye "(PARCIAL, no definitivo)" a propósito, visible en el título de
la página — nunca se debe cargar un dato así sin que se note en la UI que es distinto a las
demás. Ver CLAUDE.md, sección "Datos parciales / no definitivos", para el detalle de cómo el
frontend maneja los campos en `null` sin romperse.

**Concejales San Isidro (septiembre) — cargado igual, con las mismas salvedades —
`CONCEJALES2025PBA_PARCIAL` (2026-08-11):** el PDF oficial definitivo tiene el desglose completo
(fuerzas, %, electores, mesas) pero solo a nivel San Isidro completo, no por circuito — mismo
techo que Senadores. El usuario mandó capturas nuevas de la misma app ("Elecciones Bonaerenses
2025") con el desglose de Concejales por circuito, top 3 fuerzas por tarjeta igual que Senadores.
Se transcribió a mano en `backend/etl/load_concejales_pba_2025_parcial.py`, mismas limitaciones
que Senadores (Escrutado no uniforme entre 93,93%-100%, solo top 3 fuerzas, sin electores/mesas/
participación/blanco/nulos, `votos` NULL).

Diferencia con Senadores: aparece una fuerza nueva y puramente local, **"ACCION VECINAL SAN
ISIDRO ES DISTINTO"** — compite solo por Concejal en San Isidro, no está en la boleta de
Senadores de la 1ra Sección (24 municipios), así que no tiene un código de alianza provincial ya
conocido en este proyecto. Se le asignó el id `local2025106_accion_vecinal` (no un número
`pba22XX` como las demás) para no aparentar un código oficial verificado que no se confirmó. Los
otros 2 (`pba2206` LLA, `pba2200` Fuerza Patria/Unión por la Patria) se reusan tal cual del loader
de Senadores — son códigos de alianza a nivel PBA, no cambian entre categorías de una misma
elección.
