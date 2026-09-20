# Checklist completo — issue d2cml-ai/Data-Science-Python#187 (HW_03_202602)

Este documento recorre **todo** el enunciado del issue, punto por punto, y marca el estado real
de cada uno. Nada se marca "hecho" sin haber sido verificado con código/datos reales en esta
sesión (ver el resto de `docs/` para el detalle de cada verificación).

Leyenda: ✅ hecho y verificado · ⚠️ hecho con limitación real documentada · ❌ pendiente · 🧑 te
corresponde a ti (fuera del alcance de lo que un asistente puede hacer).

---

## Restricción global

> "Un sistema que responde con confianza y de forma equivocada es peor que no tener sistema."

✅ Aplicada activamente: se encontraron y corrigieron 2 alucinaciones/comportamientos engañosos
reales del motor de la Tarea 1 (citas no usadas mostradas como si respaldaran la respuesta;
mención inventada a "Chile") probando la app en vivo con el usuario — ver `docs/fase3_engine.md`.

---

## TAREA 1 — RAG Normativo (6.0 pts)

### Fase 1 — Fuentes, extracción, limpieza (1.0 pt) ✅

- [x] Ley N.° 32069 verificada desde fuente oficial (Congreso de la República).
- [x] D.S. N.° 001-2026-EF verificado (fuente: reproducción de El Peruano vía terceros —
      limitación declarada, ver `docs/fase1_extraccion.md` sección "Nota de honestidad").
- [x] Extracción de texto con seguimiento de página (`src/extraction.py`).
- [x] Eliminación de ruido de encabezados/pies de página (bug real de columnas del D.S.
      encontrado y corregido).
- [x] Reporte de calidad de extracción (`data/processed/quality_report.json`).

### Fase 2 — Chunking e indexación (1.0 pt) ✅

- [x] Tamaño de fragmento (2200 caract.) y overlap (300) determinados por comparación de
      evidencia real (distribución de longitud de 260 unidades legales), no arbitrarios.
- [x] Metadatos por fragmento: documento, versión/fecha, página (`src/chunking.py`).
- [x] Idempotencia y resumibilidad del índice (verificada: 2ª corrida reusa 307/307 embeddings).
- [x] Reporte de distribución de longitud de fragmentos (`data/processed/chunk_report.json`).
- [x] Bug real encontrado y corregido: `chunk_id` no único entre secciones.

### Fase 3 — Motor RAG (1.5 pts) ✅

- [x] Calibración de umbral de similitud usando el set de evaluación (0.64).
- [x] Estrategia de manejo de versiones documentada (`docs/fase3_engine.md`).
- [x] Limitación de alcance con ejemplos fuera de dominio documentados.
- [x] Cálculo de costos con tarifas por fecha de vigencia (`src/costs.py`, con auto-test).
- [x] Proceso offline (`build_index.py`) y online (`engine.py`) separados, función única
      `answer_query()` con salida estructurada.

### Fase 4 — Evaluación (1.5 pts) ⚠️

- [x] Set de 20 preguntas (15 dentro de dominio, 5 fuera) — `eval/questions.json`.
- [x] Recall@1/3/5 (0.667 / 0.800 / 0.800) y tasa de abstención (100% combinada, ver
      `docs/fase4_evaluacion.md`).
- ⚠️ **Comparación de embeddings local vs. OpenAI `text-embedding-3-small`: NO ejecutada.**
      Bloqueada por falta de `OPENAI_API_KEY`. Código listo en
      `eval/run_eval.py::compare_with_openai`, lanza error explícito en vez de simular un
      resultado. **Se resuelve si consigues una key y me la compartes vía `.env` (nunca en el
      chat) antes de la entrega.**

### Fase 5 — Interfaz Streamlit (1.0 pt) ✅

- [x] `streamlit run app.py` único, muestra respuesta, fragmentos citados, estado de abstención
      y costo de la consulta.
- [x] Probada en vivo con el usuario; 2 bugs reales encontrados y corregidos en esa prueba.

---

## TAREA 2 — Radar de Contrataciones (6.0 pts)

### Fase 1 — Adquisición (1.5 pts) ✅

- [x] Mínimo 3 archivos mensuales de 2026 reales (jun/jul/ago) descargados desde la API real del
      portal OECE (`contratacionesabiertas.oece.gob.pe/api/v1/files`, encontrada inspeccionando
      el bundle JS del portal).
- [x] `src/acquisition.py`: usa la API, con caché (no redescarga meses ya presentes) y throttling
      (2s entre descargas) — **probado en vivo contra la API real**, detectó un mes nuevo
      (2026-09) automáticamente.
- [x] "Una fila por proceso de contratación" lograda entendiendo el modelo OCDS
      (`records.csv`/`compiledRelease`, no `releases.csv`) — verificado: ocid único.

### Fase 2 — Validación (1.0 pt) ✅

- [x] Detección de duplicados, montos/descripciones faltantes, errores de ubicación,
      inconsistencias de codificación.
- [x] Normalización de departamento del comprador a los 25 oficiales.
- [x] Reporte de calidad con tasas de recuperación (`data/processed/quality_report.json`).
- [x] **2 bugs reales corregidos**: (1) la primera versión no detectaba ~25-30% de filas con
      codificación corrupta (`¿` usado como guion/comilla, no recuperable con certeza); (2) un
      defecto de publicación de OECE en `records.csv` (`\""` en vez de `""`) dejaba una barra
      invertida literal en 7 nombres de comprador — encontrado probando el dashboard en vivo con
      el usuario, corregido con certeza (sin ambigüedad, a diferencia del caso 1). Ver
      `docs/tarea2_fase2_validacion.md`.

### Fase 3 — RAG híbrido (1.5 pts) ⚠️

- [x] Índice de descripciones de procesos + filtros estructurados (departamento, categoría,
      monto, fecha) aplicados antes de la búsqueda semántica.
- [x] Evaluación con 10 preguntas de relevancia conocida (`eval/hybrid_questions.json`).
- [x] Prueba de transferibilidad del umbral de la Tarea 1: **NO transferible** (0/10 lo superan).
- ⚠️ **Recall@5 = 0.3 (limitación real, no resuelta a fondo por tiempo)** — documentado con
      hipótesis de causa raíz y recomendaciones en `docs/tarea2_fase3_rag_hibrido.md`.

### Fase 4 — Dashboard (1.5 pts) ✅

- [x] Vistas mínimas: KPI header, mapa coroplético (geojson real de los 25 departamentos), caja
      de preguntas, tabla clasificada, gráficos de distribución, panel de calidad.
- [x] Filtros de sidebar: departamento, categoría, rango de monto, fecha, similitud.
- [x] Lectura de archivos precomputados (no recalcula validación/índice/riesgo al abrir).
- [x] Probado con lógica ejecutada directamente en Python (sin errores) — **pendiente que el
      usuario confirme visualmente en el navegador** (`http://localhost:8502`).

### Fase 5 — Indicador de riesgo (0.5 pts) ✅

- [x] % de adjudicación a postor único por departamento y comprador.
- [x] Top 10 compradores con umbral mínimo de procesos (5).
- [x] Advertencia explícita: "señala necesidad de investigación, no prueba irregularidad" (en el
      documento y en el dashboard).

---

## Presentación (8.0 pts)

- [x] Diagramas de pipeline listos para el video: `docs/pipeline_tarea1.md`,
      `docs/pipeline_tarea2.md` (Mermaid, se renderizan en GitHub).
- 🧑 **Video de 12 min**: no lo puedo grabar yo. Los diagramas, números reales (Recall, costos,
      latencia) y hallazgos de esta sesión están listos para que armes el guion con la regla
      "pipeline antes que código".
- 🧑 **Demos en vivo**: las dos apps están corriendo (`localhost:8501` y `:8502`) para que las
      grabes.

---

## Deliverables checklist (estructura del repo pedida)

- [x] `README.md` con setup, estado por fase y resultados.
- [x] `requirements.txt`.
- [x] `.env.example` (solo nombres, sin credenciales).
- [x] `tarea1_rag_normativo/`: `config.yaml`, `build_index.py`, `app.py`, `src/` (extraction,
      chunking=embedding/index, engine, costs), `eval/`, `data/{raw,processed}/`, `logs/`.
- [x] `tarea2_radar/`: `config.yaml`, `app.py`, `src/` (acquisition, validation, hybrid_index,
      risk_indicator=metrics), `data/{raw,processed,outputs}/`, `logs/`.
- [x] `docs/` con diagramas de pipeline y documentación de cada fase.
- [x] Tabla de verificación de fuentes (Tarea 1, Fase 1) — `docs/fase1_extraccion.md`.
- [x] Reporte de calidad de extracción — `data/processed/quality_report.json` (Tarea 1).
- [x] Set de evaluación con resultados — `eval/questions.json` + `eval/results*.json` (Tarea 1).
- ⚠️ Tabla de comparación de embeddings — pendiente (sin API key).
- [x] Reporte de calidad de datos (Tarea 2) — `data/processed/quality_report.json`.
- [x] Log de costos con llamadas reales — `tarea1_rag_normativo/logs/cost_log.jsonl`.
- 🧑 **Video (enlazado en el README)** — pendiente que lo grabes y me pases el link para agregarlo.

---

## Bonos de innovación (no implementados, quedan como oportunidad si hay tiempo)

- ❌ Bot de Telegram (Tarea 1).
- ❌ Workflow de evaluación en GitHub Actions (Tarea 1).
- ❌ Comparación con BM25 (Tarea 1) — **recomendado especialmente para la Tarea 2**, ya que
      podría mitigar el problema de Recall@5=0.3 encontrado en el RAG híbrido.
- ❌ Despliegue público (Tarea 1).
- ❌ Actualización programada vía API (Tarea 2) — la base ya existe en `src/acquisition.py`,
      faltaría solo un cron/scheduler.
- ❌ Indexación de documentos de licitación (Tarea 2).
- ❌ Indicadores de riesgo adicionales (Tarea 2).
- ❌ Vínculo Tarea 1 ↔ Tarea 2.
