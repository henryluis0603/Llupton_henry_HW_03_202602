# Tarea 1 — Fase 3: Motor RAG

## 1. Arquitectura (dos procesos separados, como pide el enunciado)

- **Offline**: `src/build_index.py`. Lee `data/processed/<doc_id>_chunks.jsonl`, calcula embeddings
  con el modelo local y guarda `data/processed/index/{embeddings.npy, metadata.jsonl}`. Es
  idempotente/resumible (ver `docs/fase2_chunking.md`, secciones 5 y 6).
- **Online**: `src/engine.py`, expone una única función `answer_query(question)` con salida
  estructurada (`answer`, `abstained`, `citations`, `top_similarity`, `cost_usd`, `latency_s`).

## 2. Por qué Hugging Face local y no OpenAI

Al momento de construir el motor (2026-09-20) no se disponía de una `OPENAI_API_KEY`, así que se
optó por modelos 100% locales. **Actualización 2026-09-23**: se consiguió una key y se ejecutó la
comparación obligatoria de embeddings (ver `docs/fase4_evaluacion.md`, sección 4); se decidió
mantener el modelo local como predeterminado incluso con la key disponible, por costo, latencia e
independencia de un tercero — no por falta de acceso. La generación (LLM que redacta la
respuesta) sigue siendo local porque el enunciado no exige comparar modelos de generación, solo
de embeddings. Se probaron y confirmaron en esta máquina (CPU/MPS, 17GB RAM):

- **Embeddings**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dim,
  multilingüe, incluye español).
- **Generación**: `Qwen/Qwen2.5-1.5B-Instruct`. Prueba real: respondió correctamente en español
  ("La capital de Perú es Lima.") en ~3 segundos por consulta.

La arquitectura (`config.yaml`) deja ambos como configurables, con OpenAI como alternativa si en
el futuro se dispone de la key — no se hardcodeó un solo proveedor.

## 3. Estrategia de manejo de versiones

El corpus indexado tiene dos instrumentos legales de distinta naturaleza, no dos versiones del
mismo texto:

- Ley N.° 32069 (cuerpo general, publicada 2024-06-24).
- D.S. N.° 001-2026-EF (modifica artículos específicos del *Reglamento* de esa ley — un tercer
  documento, el Reglamento en sí, que **no está indexado** porque no es una fuente obligatoria
  según el enunciado del issue #187).

Política aplicada en `engine.py`:

1. Cada cita expone siempre `version_label` (con fecha) y `section`, para que la respuesta nunca
   mezcle contenido de ambos instrumentos sin decir de cuál proviene.
2. En caso de empate de similitud (diferencia < 0.02) entre dos candidatos, se prefiere el de
   fecha de publicación más reciente.
3. **Limitación declarada explícitamente**: como el Reglamento original (D.S. N.° 009-2025-EF)
   no está indexado, el motor no puede confirmar si un artículo del Reglamento distinto a los
   que modifica el D.S. 001-2026-EF sigue vigente tal cual o fue modificado por otra norma. Esto
   se documenta aquí en vez de simular una respuesta con falsa certeza.

## 4. Limitación de alcance (scope) — hallazgo real, no simulado

Ver `docs/fase4_evaluacion.md` para el detalle numérico. Resumen: la similitud coseno del modelo
de embeddings local **no separa perfectamente** preguntas dentro y fuera de dominio — 3 de 5
preguntas fuera de dominio superan el umbral calibrado de similitud (0.64) y llegarían a la etapa
de generación. Por eso el motor tiene una **segunda capa de abstención**: el prompt de generación
instruye explícitamente al modelo a responder "No tengo información suficiente..." si el contexto
recuperado no contiene la respuesta, y `engine.py` detecta esa frase para corregir el campo
`abstained` y **no mostrar citas** cuando el modelo se abstuvo (antes de esta corrección, el
motor mostraba citas junto a una respuesta de abstención, lo cual sería engañoso). Prueba real:
las 3 preguntas fuera de dominio que pasan el filtro de similitud fueron correctamente rechazadas
por esta segunda capa (ver `docs/fase4_evaluacion.md`, sección 3).

## 5. Bugs reales encontrados probando la app con el usuario (2026-09-20)

Al probar `app.py` en vivo, el usuario preguntó "¿Cuáles son los principios rectores de la
contratación pública?". La respuesta fue correcta, pero el panel de "Fragmentos citados" mostraba
**5 artículos**, y al revisar su contenido real se encontró que **4 de los 5 no tienen relación
con la pregunta** (Artículo 9 = actores del proceso, PRIMERA = prevalencia de normas, OCTAVA =
profesionalización de compradores, Artículo 46 = elaboración del requerimiento). Solo el
Artículo 5 era el correcto. Causa: `engine.py` mostraba como "citas" **todos** los fragmentos que
pasaban el umbral de similitud y se le pasaban al LLM como contexto, sin verificar si el LLM
realmente los había usado en la respuesta final — mostrar fuentes no usadas como si respaldaran
la respuesta es exactamente el tipo de falsa confianza que este proyecto busca evitar.

**Corrección 1 (citas)**: se agregó `_filter_actually_used()` en `engine.py`, que solo conserva
en `citations` los fragmentos cuyo número de artículo (o rótulo de disposición) aparece
literalmente mencionado en el texto de la respuesta generada. Si el modelo no cita ningún número
explícito, se muestra únicamente el fragmento de mayor similitud (no los 5). Verificado: la misma
pregunta ahora solo cita `Artículo 5`.

Al investigar esto más a fondo (probando la misma pregunta con una redacción ligeramente distinta,
"¿Qué principios **rigen** la contratación pública **según la ley**?"), se encontró un problema
más serio y reproducible: el modelo (`Qwen2.5-1.5B-Instruct`) generó una respuesta que terminaba
con la frase inventada **"Estos principios guían la forma y contenido de las contrataciones
públicas en Chile."** — el corpus es 100% normativa peruana; no hay ninguna mención a Chile en
ningún documento indexado. Se confirmó que es reproducible (se repitió el experimento y dio el
mismo resultado). Se descartó que fuera un bug de indexación (se verificó que el `chunk_id` y el
texto de cada fragmento citado correspondían correctamente al artículo real, comparando contra
`data/processed/ley_32069_chunks.jsonl`); es una alucinación genuina del modelo de generación,
favorecida por el contexto ruidoso (fragmentos poco relevantes mezclados con el correcto).

**Corrección 2 (alucinación de jurisdicción)**: se agregó una tercera capa de abstención en
`answer_query()` que detecta menciones a otros países hispanohablantes (Chile, Colombia, México,
Argentina, etc.) en la respuesta generada y, si aparecen, **descarta la respuesta y fuerza
abstención** en vez de mostrarla. Esto es un paliativo barato, no una solución de fondo: un
modelo de 1.5B parámetros puede seguir fallando de otras formas que este chequeo específico no
detecta (ver limitación abajo). Verificado: la pregunta reformulada ahora se abstiene en vez de
mostrar la respuesta con el error de país.

**Limitación que queda abierta, declarada explícitamente**: estas dos correcciones son
mitigaciones puntuales a problemas ya observados, no una garantía general de que el modelo local
de 1.5B parámetros no alucine de otras maneras no cubiertas por estos chequeos (por ejemplo,
inventar un número de artículo que no existe, o mezclar cifras). Si hay tiempo antes de la
entrega, se recomienda probar `Qwen2.5-3B-Instruct` (más grande, mejor seguimiento de
instrucciones) y comparar la tasa de alucinación con un set de preguntas reformuladas más amplio.

## 6. Costos

`src/costs.py` calcula el costo real de cada llamada. Con el proveedor local activo, el costo es
**$0.00 por diseño** (no se inventa un costo estimado para simular un gasto que no ocurrió). La
fórmula de precios de OpenAI (con tabla de tarifas por fecha de vigencia, para modelar
"time-based pricing") está implementada y verificada con un auto-test (`python3 src/costs.py`),
lista para cuando se configure una API key real. Cada llamada de generación queda registrada en
`logs/cost_log.jsonl`.
