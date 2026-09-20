# Tarea 1 — Fase 1: Fuentes, extracción y limpieza

## 1. Verificación de fuentes (Día 1, antes de escribir código de RAG)

| Documento | Fuente oficial usada | URL | Fecha de publicación | Páginas | Verificación |
|---|---|---|---|---|---|
| Ley N.° 32069, Ley General de Contrataciones Públicas | Congreso de la República (texto consolidado) | https://leyes.congreso.gob.pe/Documentos/2021_2026/ADLP/Texto_Consolidado/32069-TXM.pdf | 2024-06-24 (publicada en El Peruano) | 91 | Se abrió el PDF con `pdfplumber` y se confirmó manualmente que la página 1 contiene el texto "PUBLICADA EL 24 DE JUNIO DE 2024 EN EL DIARIO OFICIAL EL PERUANO" y la firma final (pág. 91) corresponde a la Presidenta de la República. |
| D.S. N.° 001-2026-EF (modifica el Reglamento de la Ley 32069) | Reproducción del Diario Oficial El Peruano, vía construccion.org | https://cdn-web.construccion.org/normas/files/leycontrataciones/DS_001-2026-EF.pdf | 2026-01-08 | 16 | Se confirmó manualmente que la página 1 muestra "El Peruano / Jueves 8 de enero de 2026 NORMAS LEGALES 33" y el título "Decreto Supremo que modifica el Reglamento de la Ley N° 32069...". |

**Nota de honestidad de fuentes**: el D.S. 001-2026-EF se obtuvo de una reproducción de terceros (construccion.org) porque fue la fuente accesible por descarga directa al momento de ejecutar este pipeline (2026-09-20); el portal `gob.pe/mef` enlaza a la norma pero no ofrece un PDF descargable directo estable para automatizar. **Pendiente**: contrastar esta copia contra la versión de El Peruano (`busquedas.elperuano.pe`) si se requiere una fuente 100% primaria antes de la entrega final.

## 2. Extracción de texto

Script: [`src/extraction.py`](../tarea1_rag_normativo/src/extraction.py). Usa `pdfplumber`, con seguimiento de página (`doc_id`, `page`, `text` por línea de JSONL en `data/processed/`).

### Problema encontrado y cómo se resolvió

- **Síntoma**: el D.S. 001-2026-EF está diagramado a **dos columnas por página** (formato de Diario Oficial). Extraer con el orden de lectura por defecto de `pdfplumber` intercalaba el texto de la columna izquierda y derecha, generando párrafos incoherentes.
- **Diagnóstico**: se inspeccionaron las coordenadas `x0` de las palabras de una página (`extract_words()`) y se encontró un vacío claro en la distribución alrededor de `x≈220–240` sobre un ancho de página de `488.98pt`, confirmando el corte de columnas en el punto medio.
- **Primer intento de solución (falló parcialmente)**: partir cada página en dos `bbox` (izquierda/derecha) por el punto medio. Esto resolvió el orden de lectura del cuerpo, pero dejó residuos como `"34 NORMAS"` al inicio de página, porque el encabezado de El Peruano ("NORMAS LEGALES / Jueves 8 de enero de 2026 / El Peruano / 34") se imprime en una sola línea **a todo el ancho de la página** (top≈60–64pt) y el corte por columna partía esa línea a la mitad.
- **Solución final**: antes de partir en columnas, se recorta la franja superior completa (`top < 72pt`) donde vive ese encabezado, confirmado por inspección de `extract_words()` en las páginas 1, 2, 6 y 16 (el cuerpo de texto siempre empieza en `top≈80`). Ver `HEADER_BAND_TOP` en `extraction.py`.
- La Ley 32069 (texto consolidado del Congreso) es de una sola columna y no presentó este problema; solo tiene la línea "PUBLICADA EL..." una vez en la página 1, que no requiere limpieza recurrente.

### Reporte de calidad (generado automáticamente en `data/processed/quality_report.json`)

| Documento | Páginas | Caracteres/página (min–max, promedio) | Páginas vacías o casi vacías |
|---|---|---|---|
| ley_32069 | 91 | 810 – 2718 (prom. 2220.4) | ninguna |
| ds_001_2026_ef | 16 | 6275 – 7845 (prom. 6851.6) | ninguna |

No se detectaron páginas vacías en ninguno de los dos documentos, lo que indica que la extracción cubrió el 100% de las páginas con contenido recuperable.

### Pendiente de esta fase

- Aún no se ha resuelto la estrategia de "manejo de versiones" (Fase 3: identificar qué artículos del Reglamento quedaron modificados por el D.S. 001-2026-EF vs. el reglamento original que aún no se ha descargado — el D.S. 001-2026-EF **modifica un reglamento** que en sí mismo no ha sido indexado todavía). Esto se documentará y decidirá antes de avanzar a chunking/indexación.
