"""Fase 3 (Tarea 1) — proceso OFFLINE de indexacion.

Separado del motor de consulta (engine.py, proceso ONLINE) como pide el
enunciado. Lee los chunks de data/processed/<doc_id>_chunks.jsonl, calcula
embeddings con el modelo local de Hugging Face configurado en config.yaml,
y guarda el indice en data/processed/index/.

Idempotencia / resumibilidad: antes de embeber, se compara el conjunto de
chunk_id contra los que ya existen en el indice guardado. Solo se embeben
los chunks nuevos o cuyo texto cambio (se guarda un hash del texto por
chunk_id); los demas se reusan tal cual. Correr este script dos veces
seguidas sin cambios no vuelve a llamar al modelo de embeddings.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BASE_DIR / "data" / "processed"
INDEX_DIR = PROCESSED_DIR / "index"


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_all_chunks(doc_ids: list[str]) -> list[dict]:
    chunks = []
    for doc_id in doc_ids:
        path = PROCESSED_DIR / f"{doc_id}_chunks.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Falta {path}. Correr chunking.py antes de build_index.py.")
        with path.open(encoding="utf-8") as f:
            chunks.extend(json.loads(line) for line in f)
    return chunks


def _load_existing_index() -> tuple[dict, np.ndarray | None]:
    meta_path = INDEX_DIR / "metadata.jsonl"
    emb_path = INDEX_DIR / "embeddings.npy"
    if not meta_path.exists() or not emb_path.exists():
        return {}, None
    existing = {}
    with meta_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            existing[row["chunk_id"]] = {"row": i, "text_hash": row["text_hash"], "meta": row}
    embeddings = np.load(emb_path)
    return existing, embeddings


def build_index(config_path: Path = BASE_DIR / "config.yaml") -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    doc_ids = [s["doc_id"] for s in config["sources"]]
    model_name = config["embeddings"]["local_model"]

    chunks = _load_all_chunks(doc_ids)
    for c in chunks:
        c["text_hash"] = _text_hash(c["text"])

    existing, existing_embeddings = _load_existing_index()

    to_embed = [c for c in chunks if existing.get(c["chunk_id"], {}).get("text_hash") != c["text_hash"]]
    reused = len(chunks) - len(to_embed)

    from sentence_transformers import SentenceTransformer

    new_vectors = {}
    if to_embed:
        model = SentenceTransformer(model_name)
        vecs = model.encode([c["text"] for c in to_embed], show_progress_bar=False, normalize_embeddings=True)
        for c, v in zip(to_embed, vecs):
            new_vectors[c["chunk_id"]] = v

    dim = None
    if new_vectors:
        dim = next(iter(new_vectors.values())).shape[0]
    elif existing_embeddings is not None:
        dim = existing_embeddings.shape[1]

    final_meta = []
    final_vectors = []
    for c in chunks:
        if c["chunk_id"] in new_vectors:
            vec = new_vectors[c["chunk_id"]]
        else:
            vec = existing_embeddings[existing[c["chunk_id"]]["row"]]
        final_meta.append({k: v for k, v in c.items() if k != "text_hash"} | {"text_hash": c["text_hash"]})
        final_vectors.append(vec)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDEX_DIR / "embeddings.npy", np.array(final_vectors, dtype="float32"))
    with (INDEX_DIR / "metadata.jsonl").open("w", encoding="utf-8") as f:
        for m in final_meta:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    report = {
        "model_name": model_name,
        "embedding_dim": dim,
        "n_chunks_total": len(chunks),
        "n_chunks_newly_embedded": len(to_embed),
        "n_chunks_reused_from_previous_index": reused,
    }
    (INDEX_DIR / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build_index(), ensure_ascii=False, indent=2))
