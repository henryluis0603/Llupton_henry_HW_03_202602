"""Fase 2 (Tarea 1): chunking e indexación de metadatos.

Estrategia (evidencia en docs/fase2_chunking.md):
  1. Se detectan los limites naturales del texto normativo: encabezados de
     "Articulo N." y encabezados ordinales de disposiciones complementarias
     ("PRIMERA.", "SEGUNDA.", ..., "UNICA."). Cada unidad resultante es un
     fragmento con significado juridico propio (se puede citar por su
     numero de articulo).
  2. Se midio la distribucion de longitud de esas 260 unidades (ambos
     documentos): mediana 765 caracteres, p90 2410, p95 3814.
  3. CHUNK_SIZE_CHARS=2200 se eligio porque deja intacto (sin sub-dividir)
     al 87.7% de las unidades legales, y solo sub-divide la cola larga
     (articulos muy extensos, ej. Art. 100 "Criterios para la aplicacion
     de sanciones por OECE"). Partir mas chico (ej. 1500) hubiera cortado
     a la mitad muchos articulos de tamaño normal (78.5% intactos).
  4. OVERLAP_CHARS=300 (~14% del chunk) se usa SOLO al sub-dividir un
     articulo largo, para que el fragmento siguiente conserve contexto
     del corte anterior (evita perder el sujeto de una oracion partida).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

CHUNK_SIZE_CHARS = 2200
OVERLAP_CHARS = 300

ORDINALS = [
    "PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA", "SÉPTIMA", "SETIMA",
    "OCTAVA", "NOVENA", "DÉCIMA", "DECIMA", "UNDÉCIMA", "UNDECIMA", "DUODÉCIMA", "DUODECIMA",
    "DÉCIMA TERCERA", "DECIMA TERCERA", "DÉCIMA CUARTA", "DECIMA CUARTA",
    "DÉCIMA QUINTA", "DECIMA QUINTA", "DÉCIMA SEXTA", "DECIMA SEXTA",
    "DÉCIMA SÉPTIMA", "DECIMA SETIMA", "DÉCIMA OCTAVA", "DECIMA OCTAVA",
    "DÉCIMA NOVENA", "DECIMA NOVENA", "VIGÉSIMA", "VIGESIMA",
    "VIGÉSIMA PRIMERA", "VIGESIMA PRIMERA", "VIGÉSIMA SEGUNDA", "VIGESIMA SEGUNDA",
    "VIGÉSIMA TERCERA", "VIGESIMA TERCERA", "VIGÉSIMA CUARTA", "VIGESIMA CUARTA",
    "VIGÉSIMA QUINTA", "VIGESIMA QUINTA", "VIGÉSIMA SEXTA", "VIGESIMA SEXTA",
    "VIGÉSIMA SÉPTIMA", "VIGESIMA SETIMA", "VIGÉSIMA OCTAVA", "VIGESIMA OCTAVA",
    "VIGÉSIMA NOVENA", "VIGESIMA NOVENA", "TRIGÉSIMA", "TRIGESIMA", "ÚNICA", "UNICA",
]
ORD_PATTERN = re.compile(r"\n(" + "|".join(sorted(ORDINALS, key=len, reverse=True)) + r")\.\s")
ART_PATTERN = re.compile(r"Artículo\s+\d+[A-Za-zÀ-ÿ]*\.")
SECTION_HEADER_PATTERN = re.compile(
    r"\n(DISPOSICIONES? COMPLEMENTARIAS? (?:FINALES?|TRANSITORIAS?|MODIFICATORIAS?|DEROGATORIAS?))\n"
)


@dataclass
class Unit:
    label: str
    section: str | None
    start: int
    end: int
    text: str


def _load_pages(doc_id: str) -> tuple[str, list[tuple[int, int]]]:
    """Devuelve (texto_completo, lista de (offset_inicio, numero_de_pagina))."""
    pages = [json.loads(line) for line in (PROCESSED_DIR / f"{doc_id}.jsonl").open(encoding="utf-8")]
    full_parts = []
    offset_page = []
    cursor = 0
    for p in pages:
        offset_page.append((cursor, p["page"]))
        full_parts.append(p["text"])
        cursor += len(p["text"]) + 1  # +1 por el '\n' de union
    return "\n".join(full_parts), offset_page


def _page_for_offset(offset_page: list[tuple[int, int]], pos: int) -> int:
    page = offset_page[0][1]
    for start, pg in offset_page:
        if start <= pos:
            page = pg
        else:
            break
    return page


def _current_section(full: str, pos: int) -> str | None:
    last = None
    for m in SECTION_HEADER_PATTERN.finditer(full, 0, pos + 1):
        last = m.group(1)
    return last


def _find_units(full: str) -> list[Unit]:
    points = []
    for m in ART_PATTERN.finditer(full):
        points.append((m.start(), m.group().rstrip(".")))
    for m in ORD_PATTERN.finditer("\n" + full):
        points.append((m.start(), m.group(1)))
    points.sort()

    units = []
    for i, (pos, label) in enumerate(points):
        end = points[i + 1][0] if i + 1 < len(points) else len(full)
        section = _current_section(full, pos)
        units.append(Unit(label=label, section=section, start=pos, end=end, text=full[pos:end].strip()))
    return units


def _split_long_unit(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE_CHARS:
        return [text]
    parts = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE_CHARS, len(text))
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space > start:
                end = space
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)
    return parts


def chunk_document(doc_id: str, version_label: str) -> dict:
    full, offset_page = _load_pages(doc_id)
    units = _find_units(full)

    chunks = []
    for unit in units:
        sub_texts = _split_long_unit(unit.text)
        section_slug = re.sub(r"\W+", "_", unit.section).strip("_") if unit.section else "CUERPO_PRINCIPAL"
        label_slug = unit.label.replace(" ", "_")
        for sub_idx, sub_text in enumerate(sub_texts):
            chunks.append(
                {
                    # unit.start se incluye para garantizar unicidad: los
                    # rotulos "Articulo N" y los ordinales ("PRIMERA", ...)
                    # SE REPITEN entre secciones distintas (cuerpo principal
                    # vs. disposiciones finales/transitorias/modificatorias),
                    # y sin esto dos fragmentos distintos podian colisionar
                    # en el mismo chunk_id (bug real detectado al verificar
                    # la resumibilidad del indice, ver docs/fase2_chunking.md).
                    "chunk_id": f"{doc_id}__{section_slug}__{label_slug}__{unit.start}__{sub_idx}",
                    "doc_id": doc_id,
                    "version_label": version_label,
                    "section": unit.section,
                    "unit_label": unit.label,
                    "page": _page_for_offset(offset_page, unit.start),
                    "sub_index": sub_idx,
                    "n_sub_chunks": len(sub_texts),
                    "n_chars": len(sub_text),
                    "text": sub_text,
                }
            )

    out_path = PROCESSED_DIR / f"{doc_id}_chunks.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    n_units = len(units)
    n_split = sum(1 for u in units if len(u.text) > CHUNK_SIZE_CHARS)
    lens = [c["n_chars"] for c in chunks]
    return {
        "doc_id": doc_id,
        "n_legal_units": n_units,
        "n_units_split_into_multiple_chunks": n_split,
        "pct_units_intact": round((n_units - n_split) / n_units * 100, 1) if n_units else 0,
        "n_chunks_final": len(chunks),
        "min_chunk_chars": min(lens) if lens else 0,
        "max_chunk_chars": max(lens) if lens else 0,
        "avg_chunk_chars": round(sum(lens) / len(lens), 1) if lens else 0,
        "output_file": str(out_path.relative_to(PROCESSED_DIR.parents[1])),
    }


def main() -> None:
    import yaml

    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    report = {
        "chunk_size_chars": CHUNK_SIZE_CHARS,
        "chunk_overlap_chars": OVERLAP_CHARS,
        "documents": [chunk_document(s["doc_id"], s["version_label"]) for s in config["sources"]],
    }
    report_path = PROCESSED_DIR / "chunk_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
