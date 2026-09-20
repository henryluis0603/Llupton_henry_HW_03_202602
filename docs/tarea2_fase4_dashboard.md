# Tarea 2 — Fase 4: Dashboard

`app.py` — vistas mínimas exigidas por el enunciado: KPI header, mapa coroplético, caja de
preguntas (RAG híbrido), tabla clasificada, gráficos de distribución, panel de calidad. Filtros
de sidebar: departamento, categoría, rango de monto, fecha, similitud. Lee solo archivos
precomputados (`data/processed/*_clean.jsonl`, `data/outputs/risk_indicator.json`,
`data/processed/hybrid_index/`) — nunca recalcula validación/índice/riesgo al abrirse.

Probado en 2 rondas en vivo con el usuario (2026-09-20), con capturas reales de pantalla. Esto
encontró 3 problemas reales — ver `docs/tarea2_fase2_validacion.md` para los dos primeros
(nombre de comprador con carácter corrupto de la fuente). El tercero, propio de esta fase:

## Mapa coroplético — verificado, no era un bug, pero se mejoró

El usuario reportó que el mapa se veía como un solo color sólido en todo el país, sin
distinción visible entre departamentos. Se verificó paso a paso antes de asumir que era un bug:

1. Se recalcularon los conteos reales por departamento directamente desde
   `data/processed/*_clean.jsonl`: rango real de 142 (Tumbes) a 5,624 (Lima).
2. Se inspeccionó el `trace` de Plotly generado por la app: los 25 `locations` coinciden
   exactamente con los 25 `buyer_department` normalizados, y los `z` values coinciden con los
   conteos reales — **el enlace de datos al geojson es correcto, no hay bug de datos**.
3. Conclusión: el problema es puramente visual — con escala de color **lineal** y una
   distribución tan sesgada (Lima domina el rango), casi todos los demás departamentos caen en
   el tercio inferior de la escala y se ven con tonos muy parecidos entre sí.

**Mejora aplicada**: se cambió a escala logarítmica (`log10(n_procesos)`) para el color,
manteniendo el conteo real (`n_procesos`) visible en el hover. Verificado: el rango de valores
de color pasó de [142, 5624] (lineal, dominado por el outlier) a [2.15, 3.75] (logarítmico, con
mejor distribución visual entre departamentos).

## Caja de búsqueda semántica — aclaración de UX, no bug

Al probar "obras de agua potable en Cusco" con el filtro de departamento en "(Todos)", los
resultados devueltos fueron procesos reales de agua/saneamiento pero de **otros** departamentos
(Lima, Piura, Cajamarca, etc.), no de Cusco. Esto **no es un bug**: el filtro de departamento del
sidebar estaba en "(Todos)", así que mencionar "Cusco" dentro del texto libre de la pregunta solo
influye levemente en el ranking semántico (el modelo de embeddings puede o no priorizar esa
palabra), pero **no filtra estructuradamente** por departamento — para eso existe el selector de
la barra lateral, que si se aplica sí restringe los candidatos antes de la búsqueda semántica
(ver `src/hybrid_engine.py::search`, filtros estructurados primero).

Se agregó una aclaración explícita en la interfaz para que esto no sea confuso: escribir un
departamento en el texto no filtra, hay que usar el selector.
