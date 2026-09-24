# Guion del video de presentación (máx. 12 min)

Sigue la estructura sugerida por el propio issue #187 y la regla obligatoria: **"el video debe
explicar el pipeline completo de ambas tareas antes de mostrar una sola línea de código."**
No es un guion para leer palabra por palabra — son ideas y datos reales para que hables con tus
propias palabras, con los números exactos ya calculados para que no tengas que improvisarlos.

**Antes de grabar**: ten abiertas 2 pestañas del navegador (`localhost:8501` y `localhost:8502`,
si no están corriendo avísame y las levanto de nuevo) y este repo en tu editor.

---

## 0:00–1:00 — Contexto del problema (1 min)

**Qué mostrar**: tu cara/slide simple con el título, o el README del repo.

**Qué decir**:
- "Este proyecto integra dos tareas de RAG (Retrieval-Augmented Generation) aplicadas a
  contratación pública peruana: un asistente normativo (Ley 32069 y su modificatoria) y un radar
  de datos de contrataciones abiertas."
- "La restricción central de todo el proyecto, que cito textual del enunciado: **'un sistema que
  responde con confianza y de forma equivocada es peor que no tener sistema.'** Esa frase guio
  cada decisión — vas a ver ejemplos concretos de esto más adelante, no es solo una frase bonita."
- "Todo lo que van a ver corre con datos y APIs 100% reales: documentos legales oficiales, datos
  abiertos de contrataciones descargados en vivo, y un motor de IA corriendo en mi propia laptop."

---

## 1:00–3:00 — Pipeline de la Tarea 1: RAG Normativo (2 min)

**Qué mostrar**: abre `docs/pipeline_tarea1.md` en el editor (o en GitHub, donde el diagrama
Mermaid se renderiza visualmente) y sigue el diagrama con el cursor mientras hablas.

**Qué decir** (sigue el diagrama de arriba a abajo):
1. "El pipeline tiene dos procesos separados, como pide el enunciado: uno **offline** de
   indexación, y uno **online** de consulta."
2. **Offline**: "Primero extraigo el texto de los dos documentos oficiales — la Ley 32069 y el
   D.S. 001-2026-EF — con seguimiento de página. Después los trocéo en fragmentos de 2200
   caracteres con 300 de superposición; ese tamaño no lo elegí a ojo, lo calibré midiendo la
   distribución real de longitud de 260 artículos y disposiciones del texto legal. Con ese
   tamaño, el 87.7% de los artículos quedan intactos sin partirse a la mitad."
3. **Online**: "Cuando alguien pregunta, el sistema busca los fragmentos más similares por
   embeddings, y si la similitud no supera un umbral calibrado (0.64), se abstiene en vez de
   inventar una respuesta."
4. **Las 3 capas de abstención** (esto es importante, muéstralo con calma): "Aquí es donde se
   aplica la restricción del enunciado. Descubrí, probando la app en vivo, que la similitud sola
   NO bastaba: dejaba pasar preguntas fuera de dominio. Así que agregué una segunda capa: el
   propio modelo de lenguaje se niega a responder si el contexto no alcanza. Y agregué una
   tercera capa: detecté que el modelo, con una pregunta reformulada, alucinó que la Ley 32069
   era de **Chile** — así que agregué un chequeo que descarta cualquier respuesta que mencione un
   país que no sea Perú."
5. "El resultado final, midiendo las 20 preguntas de evaluación con generación real: 15 de 15
   preguntas válidas respondidas, y 5 de 5 preguntas fuera de dominio correctamente rechazadas.
   100% en ambos, frente a solo 40% de abstención correcta usando solo similitud."

---

## 3:00–4:30 — Pipeline de la Tarea 2: Radar de Contrataciones (1.5 min)

**Qué mostrar**: `docs/pipeline_tarea2.md`.

**Qué decir**:
1. "Para el radar, primero encontré la API real del portal de datos abiertos de OECE — no estaba
   documentada públicamente, la ubiqué inspeccionando el código de la propia página web."
2. "Descargué 3 meses reales de 2026 (junio a agosto), los validé — encontrando y corrigiendo 2
   problemas reales de codificación en los datos que publica el propio Estado — y construí un
   motor de búsqueda híbrido: filtros estructurados (departamento, categoría, monto, fecha)
   combinados con búsqueda semántica."
3. "El dashboard nunca recalcula nada al abrirse — solo lee archivos ya procesados, tal como pide
   el enunciado."
4. "También calculé un indicador de riesgo: qué porcentaje de contrataciones se adjudican a un
   solo postor, por departamento y por comprador — con la advertencia explícita de que esto
   señala necesidad de investigar, no prueba irregularidad."

---

## 4:30–6:30 — Decisiones técnicas con números reales (2 min)

**Qué mostrar**: puedes tener abierto `docs/fase4_evaluacion.md` y `docs/tarea2_fase3_rag_hibrido.md`,
o simplemente decir los números en cámara — están todos aquí abajo, no necesitas memorizarlos.

**Tabla 1 — Comparación de embeddings (Tarea 1, obligatoria por el enunciado)**:

| | Local | OpenAI `text-embedding-3-small` |
|---|---|---|
| Recall@1/3/5 | 0.667 / 0.8 / 0.8 | 0.8 / 1.0 / 1.0 |
| Latencia por consulta | 0.032 s | 0.61 s |
| Costo total (307 fragmentos + 15 consultas) | $0.00 | $0.0017 |

"OpenAI da mejor precisión, pero es 19 veces más lento y depende de un tercero — de hecho, en
esta misma sesión la cuenta se quedó sin saldo y bloqueó todo hasta que cargué crédito. Decidí
mantener el modelo local por defecto: para este proyecto, la latencia y la independencia pesan
más que una mejora de precisión que cuesta centavos pero introduce una dependencia externa."

**Tabla 2 — Mejora del RAG híbrido (Tarea 2)**:

| | Solo semántico | + BM25 (búsqueda por palabras clave) |
|---|---|---|
| Recall@5 | 0.3 | 0.8 |

"El primer intento fallaba feo: buscar 'agua potable' devolvía un proyecto de canchas
deportivas. Diagnostiqué que el texto de licitaciones —lleno de códigos y siglas— lo maneja mal
un modelo de embeddings genérico. Agregar coincidencia por palabras clave lo resolvió."

---

## 6:30–9:30 — Demostración en vivo de las apps (3 min)

**Qué mostrar y decir** (Tarea 1, `localhost:8501`, ~1.5 min):
1. Haz una pregunta real: *"¿Cuáles son los principios rectores de la contratación pública?"*
2. Mientras carga (tarda ~40 segundos en CPU — dilo en voz alta: "esto corre en mi laptop, sin
   ningún servidor externo, por eso tarda"), explica que se ve la respuesta, las citas exactas
   usadas (no todas las recuperadas, solo las que el modelo realmente usó), la similitud, el
   costo ($0.00) y la latencia.
3. Prueba una pregunta fuera de dominio (ej. "¿cuál es la tasa del IGV?") y muestra cómo se
   abstiene en vez de inventar.

**Qué mostrar y decir** (Tarea 2, `localhost:8502`, ~1.5 min):
1. Muestra el KPI header y el mapa (menciona que usa escala logarítmica porque Lima domina el
   resto del país en cantidad de procesos).
2. Usa la caja de búsqueda: *"obras de agua potable en Cusco"* con el filtro de departamento en
   Cusco, y muestra que los resultados son reales y coherentes.
3. Muestra el panel de indicador de riesgo y lee la advertencia en voz alta.

---

## 9:30–10:30 — Código (solo lo esencial, 1 min)

El enunciado pide mostrar **solo 2 o 3 partes que sustenten tus decisiones**, no un recorrido
completo. Recomendación concreta, abre estos 2 archivos:

1. `tarea1_rag_normativo/src/engine.py` — busca la función `answer_query` y señala las 3 capas de
   abstención (el filtro de similitud, la detección de rechazo del LLM, el chequeo de país). Di:
   "esto no estaba planeado desde el inicio, lo agregué después de encontrar los problemas reales
   probando la app."
2. `tarea2_radar/src/hybrid_engine.py` — señala la función `search()` y la fusión RRF entre
   semántica y BM25.

---

## 10:30–12:00 — Hallazgos, limitaciones y costos (1.5 min)

**Qué decir** (esto es lo que más peso tiene según la rúbrica — "findings and limitations"):

- "Durante el proyecto encontré y corregí 7 bugs reales, no simulados: 2 en la extracción/chunking
  de los documentos legales, 2 en el motor RAG (citas mal mostradas y una alucinación real del
  modelo), y 3 en los datos de contrataciones y el dashboard."
- "La limitación más importante que dejo documentada: no comparé modelos de **generación** con
  GPT, porque el enunciado solo exige comparar embeddings — la generación sigue siendo 100% local."
- "Costo total de todo el proyecto: $0.0017 USD en la comparación de embeddings, y $0.00 en todo
  lo demás — el motor de producción corre completamente gratis."
- Cierra con una reflexión honesta: "el hallazgo que más me marcó fue que un sistema puede sonar
  convincente y estar completamente equivocado — como cuando el modelo dijo que la ley era de
  Chile. Ese es exactamente el riesgo que este proyecto buscaba enfrentar de frente, no evitar."

---

## Checklist antes de grabar

- [ ] Ambas apps corriendo (avísame si no).
- [ ] Ensayar la pregunta de la demo al menos una vez (recuerda: ~40s de espera, no cortes en
      edición como si fuera instantáneo — es parte de la honestidad del proyecto).
- [ ] Tener a la mano las 2 tablas de números (arriba) por si te trabas.
- [ ] Grabar en tandas (offline/online de T1, T2, demo, código, cierre) y editar después — no
      hace falta una sola toma continua de 12 minutos.
