# Diagrama de pipeline — Tarea 2 (Radar de Contrataciones)

```mermaid
flowchart TD
    subgraph ADQUISICION["Fase 1 — Adquisición"]
        A["API real del portal OECE\ncontratacionesabiertas.oece.gob.pe/api/v1/files"] -->|"src/acquisition.py\n(caché + throttling)"| B["ZIP mensuales OCDS\n(records.csv, com_parties.csv,\ncom_awards.csv, ...)"]
    end

    subgraph VALIDACION["Fase 2 — Validación"]
        B -->|"src/validation.py"| C["Detección: duplicados,\nmontos/desc. faltantes,\nubicación, codificación"]
        C --> D[("data/processed/\n*_clean.jsonl\n(1 fila por ocid)")]
        C --> E["quality_report.json"]
    end

    subgraph RAG_HIBRIDO["Fase 3 — RAG híbrido"]
        D -->|"src/hybrid_index.py"| F[("Índice de embeddings\n(título + descripción)")]
        G["Pregunta + filtros\n(depto, categoría, monto, fecha)"] --> H["1. Filtros ESTRUCTURADOS\n(sobre 20,422 filas)"]
        D -.-> H
        H --> I["2. Similitud semántica\n(solo sobre lo filtrado)"]
        F -.-> I
        I --> J["Top-k resultados\n+ similitud"]
    end

    subgraph RIESGO["Fase 5 — Indicador de riesgo"]
        D -->|"src/risk_indicator.py"| K["% postor único\npor departamento y comprador"]
        L["com_awards.csv"] -.-> K
        K --> M[("data/outputs/\nrisk_indicator.json")]
    end

    subgraph DASHBOARD["Fase 4 — Dashboard (solo lee precomputado)"]
        D --> N["app.py (Streamlit)"]
        E --> N
        M --> N
        J -.->|"caja de búsqueda"| N
        N --> O["KPIs · Mapa coroplético\nTabla · Distribuciones\nPanel de calidad · Riesgo"]
    end
```

## Notas para el video

- El dashboard **nunca recalcula** validación, índice ni indicador de riesgo al abrirse — solo
  lee los archivos ya generados por las fases 2, 3 y 5 (ver enunciado: "Precomputed file reading,
  no real-time rebuilding").
- **Limitación real y medida** que conviene mostrar en el video sin maquillar: el Recall@5 del
  RAG híbrido es 0.3 (peor que en la Tarea 1), y el umbral de similitud de la Tarea 1 (0.64) **no
  transfiere** a este corpus — ver `docs/tarea2_fase3_rag_hibrido.md`.
- El indicador de riesgo es una **señal para investigar, no una prueba de irregularidad** (esto
  debe decirse explícitamente en el video, tal como lo exige el enunciado).
