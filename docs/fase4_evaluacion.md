# Tarea 1 — Fase 4: Evaluación

## 1. Set de evaluación

`eval/questions.json`: 20 preguntas, **15 dentro de dominio** (redactadas a partir del texto real
extraído en Fase 1/2, con el artículo correcto anotado como ground truth) y **5 fuera de dominio**
(temas legales peruanos reales pero ajenos a los dos documentos indexados: laboral, tributario,
societario).

## 2. Recall@k (solo retrieval, sin generación)

Ejecutado con `eval/run_eval.py` sobre las 15 preguntas in_domain:

| Métrica | Valor |
|---|---|
| Recall@1 | 0.667 (10/15) |
| Recall@3 | 0.800 (12/15) |
| Recall@5 | 0.800 (12/15) |

Interpretación honesta: en 3 de 15 preguntas, el artículo correcto **no aparece ni siquiera en
el top-5**. Esto es evidencia de que el modelo de embeddings local (384 dim, propósito general)
tiene margen de mejora para este dominio específico; no se reporta como si fuera perfecto.

## 3. Calibración del umbral de similitud — dos problemas reales encontrados

### 3.1. Bug en el rango de búsqueda del umbral

La primera corrida de `run_eval.py` probó umbrales solo en el rango `0.20–0.60` y "calibró"
`similarity_threshold = 0.20` — un umbral degenerado que nunca abstiene (porque 0.20 es más bajo
que cualquier similitud observada). Al graficar manualmente la similitud máxima de cada pregunta
se vio que el verdadero punto de cruce entre las distribuciones in/out-of-domain estaba cerca de
**0.64**, fuera del rango buscado. Se corrigió el rango a `0.30–0.90` (ver comentario en
`eval/run_eval.py`).

### 3.2. Las distribuciones de similitud se superponen (hallazgo real, no un bug de código)

| | mínimo | máximo | promedio |
|---|---|---|---|
| Similitud máxima, preguntas **in_domain** | 0.656 | 0.840 | 0.750 |
| Similitud máxima, preguntas **out_of_domain** | 0.623 | 0.789 | 0.697 |

Una pregunta fuera de dominio ("¿Qué requisitos exige la Ley General de Sociedades...?") obtuvo
similitud **0.789**, más alta que 6 de las 15 preguntas in_domain. **No existe un umbral que
separe perfectamente ambos grupos** con este modelo de embeddings sobre este corpus.

Con `similarity_threshold = 0.64` (el que maximiza aciertos combinados sobre la grilla
0.30–0.90):

- **100%** de las preguntas in_domain superan el umbral (cobertura total, no se pierde ninguna
  respuesta real por el filtro de similitud).
- Solo **40%** (2 de 5) de las preguntas fuera de dominio son rechazadas por similitud sola.

### 3.3. Mitigación de segunda capa (medida, no solo propuesta)

Como el filtro de similitud no basta, `engine.py` agrega una segunda capa: el prompt de
generación instruye explícitamente al modelo a responder "No tengo información suficiente..." si
el contexto recuperado no contiene la respuesta. Se probó end-to-end con las 3 preguntas fuera de
dominio que sí superan el umbral de similitud (despido laboral, Ley General de Sociedades,
prescripción tributaria): **las 3 fueron correctamente rechazadas** por el modelo de generación
(ver `eval/results_full_generation.json`). Al detectar la corrección, se ajustó `engine.py` para
que el campo `abstained` refleje también este rechazo de segunda capa (antes solo miraba el
filtro de similitud) y para que no se muestren citas junto a una respuesta de abstención.

**Tasa de abstención combinada (similitud + generación), medida sobre las 20 preguntas completas**
(`eval/results_full_generation.json`, corrida end-to-end real con generación, no solo retrieval):

| | Similitud sola | Similitud + segunda capa (generación) |
|---|---|---|
| Preguntas in_domain respondidas (de 15) | 15/15 (100%) | **15/15 (100%)** |
| Preguntas out_of_domain correctamente abstenidas (de 5) | 2/5 (40%) | **5/5 (100%)** |

Es decir: la segunda capa cerró por completo el hueco que dejaba la similitud sola en este set de
20 preguntas, sin sacrificar ninguna respuesta válida. Esto no significa que el problema esté
resuelto en general — son solo 5 preguntas fuera de dominio de prueba; con un set más grande
podrían aparecer casos donde el LLM local también se equivoque. Se recomienda ampliar el set de
evaluación fuera de dominio antes de la entrega final si hay tiempo.

**Costo real de esta corrida completa**: `$0.00` (proveedor local, ver sección 5). **Latencia
promedio real**: 42.7 segundos por pregunta (CPU, sin aceleración GPU dedicada) — este es un
límite de usabilidad real a tener en cuenta para la demo en video: las respuestas en la interfaz
Streamlit tardan bastante y conviene mostrarlo con ese tiempo de espera visible, no cortarlo en
edición como si fuera instantáneo.

## 4. Comparación de embeddings: local vs. OpenAI `text-embedding-3-small` — PENDIENTE

El enunciado pide comparar el modelo local contra `text-embedding-3-small` de OpenAI. **Esto no
se pudo ejecutar** porque no hay una `OPENAI_API_KEY` disponible en este proyecto (ver decisión
documentada el 2026-09-20). El código (`eval/run_eval.py::compare_with_openai`) está escrito y
listo, pero lanza un error explícito en vez de simular un resultado si se intenta correr sin la
key. **Queda pendiente**: correr esta comparación si el usuario consigue una API key antes de la
entrega, y actualizar esta sección con los números reales.

## 5. Costos de la evaluación

Cada llamada de generación durante esta fase quedó registrada en `logs/cost_log.jsonl`, con
proveedor `huggingface_local` y costo `$0.00` (real, no estimado — ver `docs/fase3_engine.md`,
sección 5).
