# Diagrama de pipeline — Tarea 1 (RAG Normativo)

Este diagrama es el que debe mostrarse en el video **antes** de cualquier línea de código
(regla "pipeline antes que código", ver enunciado del issue #187).

```mermaid
flowchart TD
    subgraph OFFLINE["Proceso OFFLINE (indexación)"]
        A["Fuentes oficiales\nLey 32069 (Congreso)\nD.S. 001-2026-EF (El Peruano)"] -->|"src/extraction.py"| B["Texto por página (JSONL)\ncon limpieza de encabezados"]
        B -->|"src/chunking.py"| C["Fragmentos (chunks)\npor artículo/disposición\n2200 car., overlap 300"]
        C -->|"src/build_index.py"| D[("Índice de embeddings\nembeddings.npy + metadata.jsonl\n(idempotente/resumible)")]
    end

    subgraph ONLINE["Proceso ONLINE (consulta)"]
        E["Pregunta del usuario"] --> F["Embedding de la pregunta\n(modelo local HF)"]
        F --> G{"Similitud coseno\n>= umbral 0.64?"}
        D -.->|"búsqueda"| G
        G -->|"No"| H["Abstención (capa 1)\n'No tengo información suficiente'"]
        G -->|"Sí"| I["Generación con LLM local\n(Qwen2.5-1.5B-Instruct)\n+ contexto recuperado"]
        I --> J{"¿Menciona país\nfuera de Perú?\n(capa 3, anti-alucinación)"}
        J -->|"Sí"| H
        J -->|"No"| K{"¿Respuesta dice\n'no tengo información'?\n(capa 2)"}
        K -->|"Sí"| H
        K -->|"No"| L["Respuesta final\n+ citas realmente usadas\n+ costo + latencia"]
        L --> M["src/costs.py\nlogs/cost_log.jsonl"]
    end

    N["app.py (Streamlit)"] --> E
    L --> N
    H --> N
```

## Notas para el video

- El proceso **offline** (arriba) se corre una sola vez (o cuando cambian las fuentes); el
  **online** (abajo) corre en cada pregunta del usuario.
- Las **3 capas de abstención** (similitud, detección de rechazo del LLM, detección de
  alucinación de país) son el resultado de bugs reales encontrados probando la app en vivo — ver
  `docs/fase3_engine.md` y `docs/fase4_evaluacion.md` para el detalle de cada una.
- Evaluación (no está en este diagrama por claridad): `eval/run_eval.py` mide Recall@k sobre el
  índice, y `eval/results_full_generation.json` mide la tasa de abstención combinada end-to-end.
