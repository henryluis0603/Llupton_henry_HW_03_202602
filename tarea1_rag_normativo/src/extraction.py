"""Extracción de texto de las fuentes normativas (Fase 1, Tarea 1).

Procesa los PDF crudos en data/raw/ y produce, por documento:
  - data/processed/<doc_id>.jsonl   (una linea por pagina: {doc_id, page, text})
  - un resumen agregado en data/processed/quality_report.json

Decisiones documentadas (ver docs/fase1_extraccion.md para el detalle):
  - La Ley 32069 (texto consolidado del Congreso) es de una sola columna.
  - El D.S. 001-2026-EF (publicado en El Peruano) es a dos columnas por
    pagina; extraerlo con el orden de lectura por defecto de pdfplumber
    intercala las dos columnas y produce texto incoherente. Se extrae
    cada columna por separado (izquierda, luego derecha) usando el punto
    medio del ancho de pagina como corte.
  - Se eliminan encabezados/pies de pagina repetidos de El Peruano
    ("El Peruano / <fecha> NORMAS LEGALES <n>" y variantes) via regex,
    porque son ruido de diagramacion, no contenido normativo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import pdfplumber

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

# Ruido de diagramacion de El Peruano que se repite en cada pagina del
# Diario Oficial. Confirmado por inspeccion manual de las paginas del
# D.S. 001-2026-EF (ver docs/fase1_extraccion.md).
EL_PERUANO_HEADER_FOOTER_PATTERNS = [
    r"El Peruano\s*/\s*[A-Za-zÁÉÍÓÚáéíóú]+\s+\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚáéíóú]+\s+de\s+\d{4}\s*NORMAS LEGALES\s*\d*",
    r"\d+\s*NORMAS LEGALES\s*[A-Za-zÁÉÍÓÚáéíóú]+\s+\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚáéíóú]+\s+de\s+\d{4}\s*/?\s*El Peruano",
]


@dataclass
class SourceSpec:
    doc_id: str
    file_name: str
    version_label: str
    two_column: bool


SOURCES = [
    SourceSpec(
        doc_id="ley_32069",
        file_name="ley_32069_congreso.pdf",
        version_label="Texto consolidado, publicado 2024-06-24 (Congreso de la Republica)",
        two_column=False,
    ),
    SourceSpec(
        doc_id="ds_001_2026_ef",
        file_name="ds_001_2026_ef_construccion_org.pdf",
        version_label="D.S. N.deg 001-2026-EF, publicado 2026-01-08 (El Peruano)",
        two_column=True,
    ),
]


def _clean_noise(text: str) -> str:
    for pattern in EL_PERUANO_HEADER_FOOTER_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Franja superior (0 a HEADER_BAND_TOP puntos) donde El Peruano imprime el
# encabezado "NORMAS LEGALES / <dia> de <mes> de <año> / El Peruano" a todo
# lo ancho de la pagina. Si no se recorta ANTES de partir en columnas, el
# corte por punto medio parte esa linea a la mitad y deja residuos como
# "34 NORMAS" pegados al inicio del texto (bug detectado por inspeccion
# manual, ver docs/fase1_extraccion.md). Valor confirmado en paginas 1, 2,
# 6 y 16 del D.S. 001-2026-EF (texto de cuerpo empieza recien en top~80).
HEADER_BAND_TOP = 72.0


def _extract_two_column_page(page: "pdfplumber.page.Page") -> str:
    body = page.within_bbox((0, HEADER_BAND_TOP, page.width, page.height))
    mid_x = page.width / 2
    left = body.within_bbox((0, HEADER_BAND_TOP, mid_x, page.height))
    right = body.within_bbox((mid_x, HEADER_BAND_TOP, page.width, page.height))
    left_text = left.extract_text() or ""
    right_text = right.extract_text() or ""
    return (left_text + "\n" + right_text).strip()


def extract_document(spec: SourceSpec) -> dict:
    pdf_path = RAW_DIR / spec.file_name
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"No se encontro {pdf_path}. Descargar manualmente la fuente oficial "
            f"antes de correr la extraccion (ver docs/fase1_extraccion.md)."
        )

    pages_out = []
    empty_pages = []
    char_counts = []

    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            raw_text = _extract_two_column_page(page) if spec.two_column else (page.extract_text() or "")
            text = _clean_noise(raw_text)
            char_counts.append(len(text))
            if len(text) < 20:
                empty_pages.append(i)
            pages_out.append({"doc_id": spec.doc_id, "page": i, "text": text})

    out_path = PROCESSED_DIR / f"{spec.doc_id}.jsonl"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in pages_out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "doc_id": spec.doc_id,
        "source_file": spec.file_name,
        "version_label": spec.version_label,
        "two_column": spec.two_column,
        "n_pages": n_pages,
        "empty_or_near_empty_pages": empty_pages,
        "min_chars_per_page": min(char_counts) if char_counts else 0,
        "max_chars_per_page": max(char_counts) if char_counts else 0,
        "avg_chars_per_page": round(sum(char_counts) / len(char_counts), 1) if char_counts else 0,
        "output_file": str(out_path.relative_to(PROCESSED_DIR.parents[1])),
    }


def main() -> None:
    report = {"sources": [extract_document(spec) for spec in SOURCES]}
    report_path = PROCESSED_DIR / "quality_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
