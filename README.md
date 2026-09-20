# HW_03_202602 — RAG Normativo y Radar de Contrataciones Públicas

Proyecto integrador para el curso de Ciencia de Datos con Python (d2cml-ai).
Enunciado completo: [issue #187](https://github.com/d2cml-ai/Data-Science-Python/issues/187).

**Estado**: las 10 fases (5 por tarea) están implementadas y documentadas. Ver
**[docs/checklist_issue187.md](docs/checklist_issue187.md) — checklist punto por punto de todo
lo que pide el issue**, con lo hecho, lo limitado y lo pendiente (video, comparación con OpenAI).
Ver también los diagramas de pipeline: [Tarea 1](docs/pipeline_tarea1.md) ·
[Tarea 2](docs/pipeline_tarea2.md).

## Estructura

```
├── tarea1_rag_normativo/
│   ├── config.yaml
│   ├── app.py                    # Fase 5: Streamlit
│   ├── src/
│   │   ├── extraction.py         # Fase 1
│   │   ├── chunking.py           # Fase 2
│   │   ├── build_index.py        # Fase 3 (offline)
│   │   ├── engine.py             # Fase 3 (online) — answer_query()
│   │   └── costs.py              # logging de costos
│   ├── eval/                     # Fase 4: preguntas + resultados
│   ├── data/{raw,processed}/
│   └── logs/cost_log.jsonl
├── tarea2_radar/
│   ├── config.yaml
│   ├── app.py                    # Fase 4: dashboard
│   ├── src/
│   │   ├── acquisition.py        # Fase 1 (API real, caché, throttling)
│   │   ├── validation.py         # Fase 2
│   │   ├── hybrid_index.py / hybrid_engine.py  # Fase 3
│   │   └── risk_indicator.py     # Fase 5
│   ├── eval/                     # Fase 3: preguntas + resultados
│   ├── data/{raw,processed,outputs}/
│   └── logs/acquisition_log.jsonl
└── docs/
    ├── checklist_issue187.md     # todo lo que pide el issue, punto por punto
    ├── pipeline_tarea1.md / pipeline_tarea2.md   # diagramas (Mermaid)
    └── fase*.md / tarea2_fase*.md                # detalle de cada fase
```

## Avance por fase

### Tarea 1 (RAG normativo)

- **Fase 1 (Fuentes, extracción, limpieza)**: completa. Ver [docs/fase1_extraccion.md](docs/fase1_extraccion.md).
- **Fase 2 (Chunking e indexación de metadatos)**: completa. Ver [docs/fase2_chunking.md](docs/fase2_chunking.md)
  — tamaño de fragmento (2200 caract.) y overlap (300 caract.) calibrados con evidencia real, más
  un bug de `chunk_id` no único encontrado y corregido.
- **Fase 3 (Motor RAG)**: completa. Ver [docs/fase3_engine.md](docs/fase3_engine.md) — embeddings
  y generación con modelos locales de Hugging Face (sin API key disponible), estrategia de manejo
  de versiones y limitación de alcance documentadas.
- **Fase 4 (Evaluación)**: completa salvo la comparación con OpenAI (bloqueada por falta de API
  key). Ver [docs/fase4_evaluacion.md](docs/fase4_evaluacion.md) — Recall@1=0.667, Recall@3=
  Recall@5=0.800; con la mitigación de segunda capa, la corrida completa (20 preguntas, con
  generación real) dio **15/15 in_domain respondidas y 5/5 out_of_domain correctamente
  abstenidas** (100% en ambos), frente a solo 40% de abstención correcta usando similitud sola.
  Latencia real: ~43 s/pregunta en CPU. Costo real: $0.00 (proveedor local).
- **Fase 5 (Streamlit)**: `app.py` implementado, consume el motor real (`src/engine.py`).

**Tarea 1 completa** (las 5 fases), con la única salvedad documentada de la comparación de
embeddings con OpenAI (pendiente por falta de API key).

### Tarea 2 (Radar de contrataciones)

- **Fase 1 (Adquisición)**: 3 meses reales de 2026 (junio, julio, agosto) descargados desde la
  API real del portal OECE (encontrada inspeccionando el bundle JS del portal, ver
  [docs/tarea2_fase1_adquisicion.md](docs/tarea2_fase1_adquisicion.md)).
- **Fase 2 (Validación)**: completa. Ver [docs/tarea2_fase2_validacion.md](docs/tarea2_fase2_validacion.md)
  — incluye la corrección de un bug real: la primera versión no detectaba que ~25-30% de las
  filas tienen un carácter `¿` corrupto (sustituto de guion/comilla) en el texto libre.
- **Fase 3 (RAG híbrido)**: completa, con un hallazgo importante y no resuelto del todo. Ver
  [docs/tarea2_fase3_rag_hibrido.md](docs/tarea2_fase3_rag_hibrido.md) — Recall@5 = **0.3** (peor
  que en la Tarea 1), y el umbral calibrado en la Tarea 1 (0.64) **no es transferible** (0/10
  preguntas lo superan). Se documenta la hipótesis de causa raíz y se deja como trabajo futuro.
- **Fase 4 (Dashboard)**: probado en vivo con el usuario (2 rondas). Ver
  [docs/tarea2_fase4_dashboard.md](docs/tarea2_fase4_dashboard.md) — 3 problemas reales
  encontrados y resueltos: 2 de codificación en los datos fuente (ver Fase 2) y 1 de
  visualización (mapa con escala lineal dominada por Lima; se cambió a escala logarítmica).
- **Fase 5 (Indicador de riesgo)**: completa. Ver [docs/tarea2_fase5_riesgo.md](docs/tarea2_fase5_riesgo.md)
  — tasa global de postor único 13.1% sobre 13,742 adjudicaciones reales; caso destacado: OEFA
  con 95.4% de postor único en 174 adjudicaciones.

**Tarea 2 completa** (las 5 fases), con la salvedad de que la calidad del RAG híbrido (Fase 3)
quedó documentada como una limitación real, no resuelta a fondo por tiempo.

## Cómo correr lo que existe hasta ahora

```bash
pip install -r requirements.txt

# Tarea 1
cd tarea1_rag_normativo
python3 src/extraction.py   # Fase 1
python3 src/chunking.py     # Fase 2
python3 src/build_index.py  # Fase 3 (offline, descarga el modelo de embeddings la primera vez)
python3 eval/run_eval.py    # Fase 4 (recall + calibración de umbral, solo retrieval)
streamlit run app.py        # Fase 5

# Tarea 2
cd ../tarea2_radar
python3 src/acquisition.py      # Fase 1 (usa la API real; ya cacheados jun-ago en data/raw/)
python3 src/validation.py       # Fase 2
python3 src/hybrid_index.py     # Fase 3 (offline)
python3 eval/run_hybrid_eval.py # Fase 3 (evaluacion)
python3 src/risk_indicator.py   # Fase 5
streamlit run app.py --server.port 8502   # Fase 4
```

## Video de presentación

Pendiente de grabar (máx. 12 min, regla "pipeline antes que código" — ver enunciado del issue
#187 y los diagramas en `docs/pipeline_tarea1.md` / `docs/pipeline_tarea2.md`). Cuando esté listo,
pegar aquí el enlace:

> _(pendiente)_

## Créditos y honestidad de datos

Todo dato, cifra o texto normativo citado en este repositorio proviene de una fuente verificada
y documentada (ver `docs/`). Ningún resultado de evaluación, costo o dato de contrataciones se
reporta sin haber sido calculado realmente a partir de fuentes reales.
