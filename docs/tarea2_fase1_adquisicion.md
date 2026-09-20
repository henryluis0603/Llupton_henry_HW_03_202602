# Tarea 2 — Fase 1: Adquisición de datos (OECE)

## 1. Cómo se encontró la fuente real (no trivial)

El enunciado pide usar la API del portal de Contrataciones Abiertas del OECE. El portal
(`https://contratacionesabiertas.oece.gob.pe/`) es una SPA en Angular; sus rutas HTML no exponen
directamente los archivos de descarga a herramientas que no ejecutan JavaScript. Se ubicó la API
real inspeccionando el bundle JS de la aplicación (`main.*.js`) en busca de rutas `"/api/..."`
usadas por el propio frontend, en vez de adivinar una URL:

```
grep -oE '"/api[a-zA-Z0-9/_-]*"' main.js
# -> "/api", "/api/v1/file/", "/api/v1/files", "/api/v1/records", "/api/v1/releases"
```

`GET https://contratacionesabiertas.oece.gob.pe/api/v1/files` devuelve un JSON real con la lista
de archivos mensuales disponibles y sus URLs de descarga directa por formato (csv/xlsx/json), por
ejemplo:

```json
{"id": "seace_v3-2026-08",
 "files": {"csv": "https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/csv/2026/08/", ...}}
```

Al consultarla (2026-09-20) devolvió 5 meses disponibles: 2026-05 a 2026-09.

## 2. Archivos descargados

Se descargaron los **3 meses completos más recientes que no fueran el mes en curso** (septiembre
2026 está incompleto porque es el mes actual): **junio, julio y agosto de 2026**, en formato CSV
(`data/raw/2026_0{6,7,8}/`), ~10-12 MB comprimidos cada uno.

| Mes | Tamaño ZIP | Filas en `records.csv` |
|---|---|---|
| 2026-06 | 12.4 MB | 7,304 (7,303 + encabezado) |
| 2026-07 | 10.8 MB | 6,568 |
| 2026-08 | 8.7 MB | 6,553 |

## 3. "Una fila por proceso de contratación" (modelo OCDS)

Cada mes trae varias tablas CSV (releases.csv, records.csv, y tablas relacionadas de items,
awards, contracts, parties, etc. — resultado de aplanar el JSON anidado del estándar OCDS).
Se usó **`records.csv`** (no `releases.csv`) porque `records.csv` contiene el `compiledRelease`
— la versión consolidada más reciente de cada proceso — con **una fila por `ocid`** (Open
Contracting ID, el identificador único de un proceso de contratación). Se verificó
empíricamente: 7,303 filas y 7,303 valores únicos de `ocid` en el archivo de junio 2026 (sin
duplicados). `releases.csv`, en cambio, tiene una fila por cada *evento* del proceso (convocado,
adjudicado, contratado...), por lo que no serviría directamente para "una fila por proceso".

## 4. Ubicación del comprador

El campo de departamento del comprador **no está en `records.csv`**; está en `com_parties.csv`
(la tabla de participantes), en las columnas `compiledRelease/parties/0/roles` y
`compiledRelease/parties/0/address/department`. Se filtran las filas cuyo `roles` contiene
`"buyer"` (7,303 de ellas en junio 2026, exactamente una por `ocid`) para obtener el
departamento real de la entidad contratante — ver `src/validation.py::_load_buyer_departments`.

## 5. Actualizaciones vía API con throttling y caché — implementado y probado

`src/acquisition.py` automatiza la descarga:
1. Consulta `GET /api/v1/files` para saber qué meses hay disponibles.
2. Descarga solo los meses que **todavía no existen** en `data/raw/` (caché real basada en si la
   carpeta del mes ya existe y tiene contenido — no vuelve a descargar lo ya presente).
3. Aplica una espera de 2 segundos entre descargas (throttling) para no golpear el portal.
4. Descomprime cada ZIP mensual automáticamente.
5. Registra cada corrida en `logs/acquisition_log.jsonl`.

**Prueba real (2026-09-20)**: se corrió el script contra la API en vivo. El portal ya tenía
disponibles **2 meses adicionales** a los usados en este proyecto (2026-05 y 2026-09, este último
publicado desde la primera consulta de esta sesión). El script:
- Detectó correctamente que **jun/jul/ago ya estaban en caché** y no los volvió a descargar.
- Descargó automáticamente **may y sep 2026** (que no eran los usados por el resto del pipeline).

**Decisión**: se eliminaron esos 2 meses de prueba (`2026_05`, `2026_09`) después de confirmar
que el script funciona, para mantener el alcance documentado de este proyecto en 3 meses
(jun-ago 2026) — la validación, el índice híbrido y el dashboard están construidos y probados
específicamente sobre esos 3. Si se quisiera ampliar el radar a 5 meses, correspondería re-correr
`validation.py`, `hybrid_index.py` y `risk_indicator.py` sobre el set ampliado (no se hizo por
alcance/tiempo de esta sesión, ver `logs/acquisition_log.jsonl` para el registro de la prueba).

## 6. Limpieza de archivos crudos no usados (antes del primer commit)

Cada ZIP mensual del OCDS trae ~20 tablas CSV (releases, items, contratos, documentos,
identificadores adicionales, tasas de cambio, etc.). Este proyecto **solo lee 3 de esas tablas**
por mes: `records.csv` (una fila por proceso), `com_parties.csv` (departamento del comprador) y
`com_awards.csv` (adjudicaciones, para el indicador de riesgo). Antes de subir el repo a git, se
eliminaron las ~17 tablas restantes por mes (no usadas por ningún script) y los ZIP originales
(ya extraídos y redundantes) — esto bajó el peso de `tarea2_radar/` de 330 MB a 125 MB sin afectar
la reproducibilidad: se verificó que `validation.py` sigue corriendo correctamente después de la
limpieza. Si se necesitara alguna de esas tablas más adelante (ej. `com_ten_documents.csv` para
indexar documentos de licitación, uno de los bonos de innovación), se puede volver a descargar
con `src/acquisition.py` borrando primero la carpeta del mes correspondiente (para que no quede
en caché).
