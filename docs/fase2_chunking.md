# Tarea 1 — Fase 2: Chunking e indexación de metadatos

## 1. Cómo se detectan las unidades legales

En vez de trocear el texto en ventanas de caracteres arbitrarias desde el inicio, primero se
identificaron los **límites naturales del texto normativo**, que son los que un usuario citaría:

- Encabezados de artículo: `Artículo N.` (regex `Artículo\s+\d+[A-Za-zÀ-ÿ]*\.`).
- Encabezados ordinales de disposiciones complementarias: `PRIMERA.`, `SEGUNDA.`, ...,
  `VIGÉSIMA NOVENA.`, `ÚNICA.` (lista curada de 56 ordinales en español; se evitó un regex
  genérico de "palabra en mayúsculas + punto" porque generaba falsos positivos, p. ej. la sigla
  `UIT.` se detectó como límite en una primera prueba).

Con esto se detectaron **142 unidades** en la Ley 32069 y **118 unidades** en el D.S. 001-2026-EF
(260 en total).

## 2. Evidencia usada para decidir tamaño de fragmento y overlap

Se midió la distribución de longitud (en caracteres) de esas 260 unidades:

| Percentil | Caracteres |
|---|---|
| p50 (mediana) | 765 |
| p75 | 1373 |
| p85 | 1893 |
| p90 | 2410 |
| p95 | 3814 |
| p99 | 6391 |

Y se comparó qué porcentaje de unidades quedarían **intactas** (sin necesidad de sub-dividir)
bajo distintos tamaños candidatos de `chunk_size_chars`:

| chunk_size_chars | % de unidades intactas |
|---|---|
| 1500 | 78.5% |
| 1800 | 84.6% |
| 2000 | 85.8% |
| **2200** | **87.7%** |
| 2500 | 90.8% |

**Decisión: `chunk_size_chars = 2200`, `chunk_overlap_chars = 300` (≈14%)**, porque:

- Deja intacto (como un solo chunk, citable por su número de artículo) a casi 9 de cada 10
  fragmentos legales, sin diluir demasiado la señal semántica de cada embedding con contenido
  de más de un artículo.
- 2500 subía el porcentaje de unidades intactas solo 3 puntos más a costa de chunks bastante
  más largos en promedio, lo que en la práctica de RAG suele degradar la precisión de la
  búsqueda por similitud (embeddings de textos muy largos son menos discriminativos).
- El overlap de 300 caracteres solo se aplica a la minoría de artículos largos que sí se
  sub-dividen (ver más abajo), para no perder el contexto inmediatamente anterior al corte.

## 3. Resultado real tras aplicar la calibración

Ejecutado con `src/chunking.py` (ver `data/processed/chunk_report.json`):

| Documento | Unidades legales | Unidades sub-divididas | % intactas | Chunks finales |
|---|---|---|---|---|
| ley_32069 | 142 | 23 | 83.8% | 178 |
| ds_001_2026_ef | 118 | 9 | 92.4% | 129 |

El porcentaje real de unidades intactas (83.8% y 92.4%) es consistente con lo estimado en la
tabla de arriba (87.7% combinado), confirmando que la calibración fue razonable.

## 4. Metadatos por fragmento

Cada línea de `data/processed/<doc_id>_chunks.jsonl` incluye:

- `doc_id`, `version_label` (para poder distinguir versión/fecha de la norma, Fase 3),
- `page` (página de origen, heredada de la Fase 1),
- `unit_label` (p. ej. `"Artículo 42"` o `"DÉCIMA CUARTA"`) y `section` (p. ej.
  `"DISPOSICIONES COMPLEMENTARIAS FINALES"`, o `null` si el chunk es un artículo del cuerpo
  principal de la ley),
- `sub_index` / `n_sub_chunks` para saber si el fragmento es parte de un artículo largo partido.

## 5. Bug real encontrado al verificar la resumibilidad: `chunk_id` no era único

Al probar que `build_index.py` (Fase 3) reusa embeddings ya calculados en vez de recalcularlos,
la segunda corrida reportó **22 chunks "nuevos"** cuando debía reportar 0 (nada había cambiado).
Diagnóstico: el `chunk_id` original (`<doc_id>__<unit_label>__<sub_index>`) **no era único**,
porque los rótulos se repiten entre secciones distintas del mismo documento:

- Los ordinales de disposiciones (`PRIMERA`, `SEGUNDA`, ...) se repiten en `DISPOSICIONES
  COMPLEMENTARIAS FINALES`, `TRANSITORIAS`, `MODIFICATORIAS` y `DEROGATORIAS` — son secciones
  distintas, cada una con su propia numeración desde `PRIMERA`.
- Incluso el rótulo `Artículo 5` se repite: existe el `Artículo 5` del cuerpo principal
  ("Principios rectores de la contratación pública") **y** un `Artículo 5` dentro de las
  disposiciones transitorias ("Reactivación de la obra pública paralizada..."), que son dos
  provisiones completamente distintas.

Esto no solo rompía la resumibilidad: si dos fragmentos distintos colisionan en el mismo
`chunk_id`, el motor de consulta podría terminar citando el artículo equivocado (un riesgo serio
en un sistema que debe responder con citas verificables). **Solución**: el `chunk_id` ahora
incluye la sección (`section_slug`) y el offset de caracter donde empieza la unidad
(`<doc_id>__<section>__<unit_label>__<char_start>__<sub_index>`), lo que garantiza unicidad.
Verificado: 307 chunks totales, 307 `chunk_id` únicos, y una segunda corrida de `build_index.py`
reutiliza los 307 embeddings sin recalcular ninguno.

## 6. Idempotencia y resumibilidad

- `chunking.py` es determinista: mismo texto de entrada produce siempre el mismo
  `chunk_id` (`<doc_id>__<unit_label>__<sub_index>`) y el mismo contenido, y sobrescribe
  el archivo de salida completo en cada corrida (correr dos veces seguidas no duplica nada).
- La resumibilidad real (no recalcular embeddings de chunks que no cambiaron) se maneja en la
  Fase 3, en `build_index.py`, comparando `chunk_id` contra un índice ya existente antes de
  llamar al modelo de embeddings.
