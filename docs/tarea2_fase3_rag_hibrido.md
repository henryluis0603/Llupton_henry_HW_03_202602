# Tarea 2 — Fase 3: RAG híbrido (semántico + filtros estructurados)

## 1. Arquitectura

`src/hybrid_index.py` (offline): embebe `tender_title + tender_description` de los 20,422
procesos (3 meses) con el **mismo modelo** de embeddings local de la Tarea 1
(`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`), para poder comparar
transferibilidad entre tareas.

`src/hybrid_engine.py` (online): `search()` aplica primero los **filtros estructurados**
(departamento, categoría, rango de monto, rango de fecha — condiciones exactas/rango, baratas)
sobre las 20,422 filas, y **después** la similitud semántica solo sobre lo que ya pasó los
filtros. Esto evita que la búsqueda semántica devuelva resultados fuera del departamento o rango
pedido solo porque el texto es parecido.

## 2. Evaluación — resultado real, y es peor de lo esperado

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

## 4. Recomendación para trabajo futuro (no implementada en esta sesión, por tiempo)

- Probar un modelo de embeddings más grande o especializado en texto administrativo/multilingüe.
- Agregar un componente léxico (BM25 o coincidencia de palabras clave) combinado con la
  similitud semántica (búsqueda híbrida en el sentido "semántica + léxica", no solo "semántica +
  filtros estructurados" como está ahora) — esto es justamente uno de los bonos de innovación
  mencionados en el enunciado para la Tarea 1, y aplicaría igual de bien aquí.
- Ampliar el set de evaluación a más de 10 preguntas para confirmar que 0.3 de Recall@5 no es un
  artefacto de esta muestra pequeña.
