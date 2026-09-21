# Tarea 2 — Fase 3: RAG híbrido (semántico + léxico BM25 + filtros estructurados)

**Actualización 2026-09-20 (tarde)**: se agregó fusión con BM25 después de detectar el problema
de recall descrito en la sección 2. Ver sección 5 para el resultado medido (Recall@5 pasó de 0.3
a **0.8**). Las secciones 2-4 se conservan tal cual se escribieron originalmente, como registro
honesto del proceso (no se reescribe la historia una vez resuelto el problema).

## 1. Arquitectura (actualizada)

`src/hybrid_index.py` (offline): embebe `tender_title + tender_description` de los 20,422
procesos (3 meses) con el **mismo modelo** de embeddings local de la Tarea 1
(`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`), para poder comparar
transferibilidad entre tareas.

`src/hybrid_engine.py` (online): `search()` aplica primero los **filtros estructurados**
(departamento, categoría, rango de monto, rango de fecha — condiciones exactas/rango, baratas)
sobre las 20,422 filas, y **después** combina DOS rankings sobre lo que ya pasó los filtros:
similitud semántica (embeddings) y coincidencia léxica (BM25, vía `rank_bm25`), fusionados por
**Reciprocal Rank Fusion (RRF, k=60)** — se fusionan posiciones de ranking, no puntajes, porque
similitud coseno (0-1) y puntaje BM25 (sin cota fija) no son comparables directamente.

## 2. Evaluación inicial (solo semántico) — resultado real, y era peor de lo esperado

Set de 10 preguntas (`eval/hybrid_questions.json`), construidas a partir de descripciones reales
verificadas por código antes de escribirlas (no de memoria — un primer intento tenía un `ocid`
inventado que resultó ser incorrecto al verificarlo, ver historial de esta sesión).

| Métrica | Resultado |
|---|---|
| Recall@1 | 0.2 |
| Recall@3 | 0.2 |
| Recall@5 | **0.3** |

Esto es notablemente peor que el Recall@5=0.8 obtenido en la Tarea 1 con el mismo modelo de
embeddings. **Caso concreto que expone el problema**: para la pregunta "mejoramiento y ampliación
del servicio de agua potable y alcantarillado...", el resultado top-1 fue un proyecto de
**"creación del servicio de práctica deportiva y/o recreativa"** — completamente ajeno al tema.

**Hipótesis de causa raíz**: las descripciones de procesos de contratación son texto muy distinto
al de una ley: están cargadas de códigos de ruta, siglas, nombres propios de localidades y
formato administrativo repetitivo, con poca estructura de "oración natural". Un modelo de
embeddings de propósito general (bueno para texto legal en prosa) parece discriminar peor este
tipo de texto. **No se investigó a fondo la causa por límite de tiempo de esta sesión** — queda
como limitación abierta y recomendación para trabajo futuro (ver sección 4).

## 3. Transferibilidad del umbral de la Tarea 1 — NO transferible

El umbral calibrado en la Tarea 1 (`similarity_threshold = 0.64`) fue probado tal cual sobre
estas 10 preguntas: **0 de 10** superan ese umbral (máximo observado: 0.6294). Además, se
comparó la similitud de los casos donde SÍ se acertó (0.598, 0.629) contra casos donde se
falló (hasta 0.628) — **se superponen**, igual que en la Tarea 1, pero aquí de forma más severa:
no existe un umbral que separe limpiamente aciertos de fallos, porque el problema no es solo de
umbral de abstención sino de **calidad del ranking semántico en sí**.

**Decisión tomada**: no tiene sentido calibrar un umbral de abstención "fino" cuando el problema
real es de recall. Se deja un umbral bajo y conservador (`0.35`, ver `src/hybrid_engine.py` uso
en el dashboard) que solo filtra consultas claramente sin relación alguna, y se compensa
mostrando más resultados (top 10, no top 3) en el dashboard para que el usuario pueda escanear
la lista en vez de confiar ciegamente en el primer resultado.

## 4. Recomendación de la sesión anterior (ya implementada, ver sección 5)

- ~~Agregar un componente léxico (BM25 o coincidencia de palabras clave) combinado con la
  similitud semántica~~ → hecho, ver sección 5.
- Probar un modelo de embeddings más grande o especializado sigue siendo una mejora posible no
  explorada.
- Ampliar el set de evaluación a más de 10 preguntas sigue pendiente, para confirmar que la
  mejora de la sección 5 no es un artefacto de esta muestra pequeña.

## 5. Fusión con BM25 — resultado medido (no solo la intuición)

Se implementó `rank_bm25.BM25Okapi` sobre el mismo corpus tokenizado (título + descripción,
minúsculas, `\w+`), fusionado con el ranking semántico por RRF (`src/hybrid_engine.py`).
Se corrió **la misma evaluación, mismas 10 preguntas**, comparando explícitamente antes/después
(`eval/run_hybrid_eval.py`, función `_run_recall(use_bm25=...)`):

| Métrica | Solo semántico (antes) | Semántico + BM25 (después) |
|---|---|---|
| Recall@1 | 0.2 | **0.5** |
| Recall@3 | 0.2 | **0.8** |
| Recall@5 | 0.3 | **0.8** |

**Verificación cualitativa, no solo la métrica**: se re-probó manualmente el caso que fallaba de
forma más vergonzosa ("mejoramiento y ampliación del servicio de agua potable...", que antes
devolvía un proyecto de canchas deportivas). Con el filtro de departamento=CUSCO aplicado, los 5
resultados ahora son genuinamente sobre agua potable en Cusco (ver `tender_description` real de
cada uno en el log de esta sesión). Los 2 casos que siguen sin encontrar el `ocid` exacto (de 10)
ahora devuelven resultados **temáticamente correctos** (ej. otro proyecto real de agua potable, o
una póliza de seguros real para la pregunta de seguros) — ya no fallan de forma disparatada,
solo no aciertan el proceso específico esperado.

**Por qué funcionó**: confirma la hipótesis de la sección 2 — el texto de licitaciones está
cargado de códigos, siglas y nombres propios que la coincidencia léxica exacta (BM25) captura
mucho mejor que un embedding de propósito general entrenado sobre prosa natural.

**Limitación que sigue abierta**: el set de evaluación sigue siendo de solo 10 preguntas; antes
de confiar en 0.8 como cifra definitiva convendría ampliarlo. No se hizo por tiempo.
