"""Fase 3 (Tarea 2): indexacion (offline) para el RAG hibrido.

Indexa `tender_title + tender_description` de cada proceso (uno por
`ocid`, los 3 meses de data/processed/*_clean.jsonl), reusando el MISMO
modelo de embeddings local que la Tarea 1 (ver tarea1_rag_normativo/config.yaml)
para poder evaluar la transferibilidad del umbral calibrado alli
(Fase 4 de esta tarea).

Normalizacion para busqueda (NO para el dato mostrado al usuario): el
caracter '¿' usado como sustituto corrupto de guion/comilla (ver
docs/tarea2_fase2_validacion.md, seccion 1.1) se reemplaza por un espacio
SOLO en el texto que se embebe, para no confundir al modelo de embeddings
con un signo de interrogacion falso en medio de la oracion. El texto
mostrado en el dashboard sigue siendo el original (no se inventa el
caracter correcto).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
INDEX_DIR = PROCESSED_DIR / "hybrid_index"
MONTHS = ["2026_06", "2026_07", "2026_08"]

# Mismo modelo que Tarea 1 (tarea1_rag_normativo/config.yaml -> embeddings.local_model)
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _load_all_processes() -> list[dict]:
    rows = []
    for month in MONTHS:
        path = PROCESSED_DIR / f"{month}_clean.jsonl"
        with path.open(encoding="utf-8") as f:
            rows.extend(json.loads(line) for line in f)
    return rows


def _text_for_embedding(row: dict) -> str:
    text = f"{row['tender_title']} {row['tender_description']}"
    return text.replace("¿", " ").strip()


def build_index() -> dict:
    rows = _load_all_processes()
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [_text_for_embedding(r) for r in rows]
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True, batch_size=64)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDEX_DIR / "embeddings.npy", np.array(vectors, dtype="float32"))
    with (INDEX_DIR / "metadata.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    report = {"model_name": EMBEDDING_MODEL, "n_processes_indexed": len(rows), "embedding_dim": int(vectors.shape[1])}
    (INDEX_DIR / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build_index(), ensure_ascii=False, indent=2))
