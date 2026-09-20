# Tarea 2 — Fase 2: Validación de calidad

Script: `tarea2_radar/src/validation.py`. Corre sobre los 3 meses descargados (Fase 1) y produce
`data/processed/{mes}_clean.jsonl` + `data/processed/quality_report.json`.

## Resultado real (corregido el 2026-09-20 dos veces — ver secciones 1.1 y 1.2)

| Mes | Filas | Duplicados | Montos faltantes | Descripción/título faltante | Errores de ubicación | Problemas de codificación | Tasa de recuperación |
|---|---|---|---|---|---|---|---|
| 2026-06 | 7,303 | 0 | 0 | 0 | 0 | **1,828 (25.0%)** | 100%* |
| 2026-07 | 6,567 | 0 | 0 | 0 | 0 | **1,762 (26.8%)** | 100%* |
| 2026-08 | 6,552 | 0 | 0 | 0 | 0 | **1,971 (30.1%)** | 100%* |

*La "tasa de recuperación" mide filas utilizables (con `ocid` único), no filas sin ningún
problema de calidad — por eso sigue en 100% aunque haya problemas de codificación: la fila
sigue siendo usable para el radar, solo tiene un carácter corrupto en el texto libre.

### 1.1. Bug real en la primera versión de esta validación

La primera corrida de `validation.py` reportó **0 problemas de codificación** en los 3 meses,
porque `_has_encoding_issue()` solo buscaba los patrones clásicos `�` y `"Ã"` (mojibake
UTF-8/Latin-1 típico). Al revisar manualmente títulos y descripciones reales para preparar las
preguntas de evaluación de la Fase 3, se encontró que el carácter `¿` aparece **usado como
sustituto corrupto de un guion o una comilla de apertura**, no como signo de interrogación real.
Ejemplos reales:

- `"Adquisición de dos sistemas de videowall para Pagos Minoristas y GTI ¿ Local Carabaya"`
  (debería ser un guion: `"... GTI - Local Carabaya"`).
- `"EJECUCIÓN DE LA OBRA IOARR: ¿RENOVACION DE PUENTE; ..."` (probablemente una comilla de
  apertura corrupta).

**Verificación de la hipótesis**: de las 1,821 filas de junio con `¿`, **1,820 no tienen un `?`
de cierre correspondiente** — una pregunta real en español siempre lleva ambos signos, así que
la ausencia del cierre confirma que es corrupción de codificación en el sistema de origen
(SEACE/OECE), no contenido real. **No se puede recuperar con certeza** cuál era el carácter
original (guion, comilla u otro) para cada caso, así que se cuenta el problema y **no se intenta
adivinar** el texto correcto — eso sería inventar datos. Se corrigió `_has_encoding_issue()` para
detectar este patrón (`¿` sin `?` de cierre) y se volvió a correr la validación completa.

**Lección aplicada**: esto confirma por qué la instrucción del usuario de "no saltarse problemas"
importa en la práctica — un "0 problemas" que suena demasiado bien ameritaba revisión manual
antes de darlo por bueno, y en efecto había un problema real sin detectar.

### 1.2. Segundo bug real, encontrado probando el dashboard con el usuario (2026-09-20)

Al revisar el panel "Indicador de riesgo" del dashboard en vivo, el usuario me mostró un nombre
de comprador con una barra invertida rara: `UNIDAD EJECUTORA 022 \"PROYECTO DE TRANSFORMACIÓN...`.
Se rastreó hasta el **archivo fuente** (`records.csv`, publicado por OECE): el campo crudo
contiene la secuencia de bytes `\""` (una barra invertida seguida de **dos** comillas) en vez del
escape estándar de CSV (`""`, sin la barra). El módulo `csv` de Python reduce las dos comillas a
una (regla estándar), pero la barra invertida sobrante queda como carácter literal en el texto
parseado — es un **defecto real de publicación del propio OECE**, no un bug de este pipeline.

A diferencia del caso de `¿` (sección 1.1), **este sí se puede corregir con certeza**: ningún
nombre de entidad, título o descripción contiene legítimamente una barra invertida pegada a una
comilla, así que `_fix_stray_backslash_quote()` la elimina de forma segura. Afecta **7 filas de
20,422** (5 en junio, 2 en julio, 0 en agosto) en `buyer_name`/`tender_title`/`tender_description`.
Se cuenta como "problema de codificación" (antes de corregir) y se corrige en el dato final.

**Patrón que se repite en esta sesión**: ambos bugs de codificación (`¿` y `\"`) se encontraron
**probando la interfaz real con el usuario**, no en la validación automática por sí sola — la
validación automática solo detecta lo que se le dice explícitamente que busque.

### Verificación de los otros indicadores (sin cambios)

- Se inspeccionaron filas reales de la muestra (ver `data/processed/2026_06_clean.jsonl`) y se
  confirmó que `amount_pen`, `buyer_department` y `tender_title` tienen contenido real y
  coherente (ej. `"JUNIN | 3231949.99 | LP-ABR-7-2026-MDLL/C-1"`).
- Se midió por separado (sin usar `title` como respaldo) que `tender/description` y
  `tender/title` están vacíos en **0 de 7,303** filas de junio 2026.
- Los 25 valores distintos de departamento del comprador encontrados coinciden exactamente con
  los 25 departamentos oficiales del Perú, ya en mayúsculas y sin variantes — por eso
  `location_errors_unnormalizable = 0`. La función `normalize_department()` igual incluye manejo
  defensivo de acentos/mayúsculas y alias conocidos (Lima Metropolitana, Lima Provincias, Callao)
  por si meses futuros traen variantes distintas.

**No se reporta esto como "no hay nada que validar"**: el pipeline de validación existe y corre
sobre cualquier mes nuevo; simplemente estos 3 meses de origen oficial no tenían los problemas
típicos (duplicados, montos vacíos, mojibake) que sí son comunes en fuentes de datos abiertos
menos curadas.

## Duplicados entre meses (ocid repetido en más de un archivo)

`n_ocid_appearing_in_multiple_months = 0` para los 3 meses descargados. Se documenta la política
para cuando sí ocurra (un proceso puede republicarse en OCDS al cambiar de estado): no se
deduplica automáticamente; el dashboard (Fase 4) debe decidir explícitamente quedarse con la
versión de fecha de publicación más reciente si esto aparece en meses futuros.

## Pendiente de esta fase

- Ejecutar la misma validación sobre más meses si se agregan al radar, para confirmar que la
  calidad excepcional de estos 3 meses no es un caso particular.
