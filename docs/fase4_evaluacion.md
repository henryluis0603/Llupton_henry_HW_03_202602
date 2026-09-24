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

## 4. Comparación de embeddings: local vs. OpenAI `text-embedding-3-small` — completa

Ejecutada el 2026-09-23 (`eval/compare_embeddings.py`), construyendo **dos índices completos
sobre exactamente los mismos 307 fragmentos**, tal como exige el enunciado. Resultado real
(`eval/embeddings_comparison.json`), medido sobre las 15 preguntas dentro de dominio:

| Métrica | Local (`paraphrase-multilingual-MiniLM-L12-v2`) | OpenAI (`text-embedding-3-small`) |
|---|---|---|
| Dimensión del vector | 384 | 1536 |
| Recall@1 | 0.667 | **0.800** |
| Recall@3 | 0.800 | **1.000** |
| Recall@5 | 0.800 | **1.000** |
| Tiempo de indexación (307 fragmentos, desde cero) | 9.46 s | 6.61 s |
| Costo de indexación | $0.00 | $0.00174 |
| Latencia promedio por consulta | **0.032 s** | 0.610 s |
| Costo de las 15 consultas de evaluación | $0.00 | $0.000007 |
| **Costo total de esta comparación completa** | $0.00 | **$0.001747** |

### ¿Cuál elegirías, y por qué? (el precio solo no alcanza, tal como advierte el enunciado)

El precio es tan bajo ($0.0017 en total) que, mirado solo por costo, "usa OpenAI y ya" parece
obvio. Pero hay 3 factores que el precio no captura, y que sí importan para este proyecto
específico:

1. **Latencia: OpenAI es ~19 veces más lento por consulta** (0.61 s vs. 0.032 s) porque cada
   consulta requiere una ida y vuelta a internet. Para un asistente interactivo esto es
   perceptible; a mayor escala (más usuarios simultáneos) se vuelve un cuello de botella real.
2. **Dependencia de disponibilidad — vivida en carne propia en esta misma sesión**: al intentar
   correr esta comparación, la cuenta de OpenAI devolvió `insufficient_quota` (sin saldo) y bloqueó
   por completo la ejecución hasta cargar crédito manualmente. El modelo local **nunca puede
   fallar por un problema de facturación de un tercero** — no depende de que una cuenta externa
   tenga saldo, esté activa, o que el servicio esté disponible en ese momento (relevante para una
   demo en vivo o un despliegue sin presupuesto garantizado).
3. **Vector 4 veces más pesado** (1536 vs 384 dimensiones): a la escala de este proyecto (307
   fragmentos) es irrelevante, pero si el corpus creciera mucho, el índice OpenAI pesaría y
   tardaría más en buscar proporcionalmente.

**Contra estos 3 puntos, el argumento a favor de OpenAI es real y fuerte**: la mejora de recall
no es marginal — pasa de "encuentra la respuesta correcta 2 de cada 3 veces en el primer lugar"
(local) a "la encuentra siempre entre las 3 primeras" (OpenAI, Recall@3=1.0). Para un sistema que
cita normativa legal, donde una cita incorrecta o ausente es un problema serio (recordar la
restricción del enunciado: "un sistema que responde con confianza y de forma equivocada es peor
que no tener sistema"), esa mejora de precisión pesa mucho.

**Decisión para este proyecto**: se mantiene el modelo **local** como predeterminado en
`config.yaml` (`embeddings.primary: local`), priorizando costo cero, baja latencia y no depender
de un tercero para una demo académica — pero se documenta que si este sistema pasara a producción
real con usuarios que dependen de la exactitud de las citas legales, la mejora de Recall de
OpenAI (especialmente pasar de 0.667 a 0.800 en el primer resultado) justificaría los $0.0017 y
los 580 ms adicionales de latencia por consulta. No es una decisión de "cuál es mejor en
abstracto", sino de qué se prioriza en cada contexto de uso.

## 5. Costos de la evaluación

Cada llamada de generación durante esta fase quedó registrada en `logs/cost_log.jsonl`, con
proveedor `huggingface_local` y costo `$0.00` (real, no estimado — ver `docs/fase3_engine.md`,
sección 5).
