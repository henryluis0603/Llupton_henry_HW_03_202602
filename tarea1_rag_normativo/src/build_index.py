"""Fase 3 (Tarea 1) — proceso OFFLINE de indexacion.

Separado del motor de consulta (engine.py, proceso ONLINE) como pide el
enunciado. Lee los chunks de data/processed/<doc_id>_chunks.jsonl y
calcula embeddings con la interfaz comun de src/embeddings.py (local o
OpenAI, mismo codigo, solo cambia `provider`), y guarda el indice en
data/processed/index/ (local) o data/processed/index_openai/ (OpenAI) --
la Fase 4 (evaluacion) compara ambos indices, construidos con exactamente
los mismos fragmentos, tal como exige el enunciado.

Idempotencia / resumibilidad: antes de embeber, se compara el conjunto de
chunk_id contra los que ya existen en el indice guardado. Solo se embeben
los chunks nuevos o cuyo texto cambio (se guarda un hash del texto por
chunk_id); los demas se reusan tal cual. Correr este script dos veces
seguidas sin cambios no vuelve a llamar al modelo de embeddings -- esto
importa especialmente para el proveedor OpenAI, donde cada llamada tiene
un costo real (aunque sea de centavos).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import yaml
from dotenv import load_dotenv

from . import costs, embeddings

BASE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BASE_DIR / "data" / "processed"

load_dotenv(BASE_DIR.parent / ".env")


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


def _load_existing_index(index_dir: Path) -> tuple[dict, np.ndarray | None]:
    meta_path = index_dir / "metadata.jsonl"
    emb_path = index_dir / "embeddings.npy"
    if not meta_path.exists() or not emb_path.exists():
        return {}, None
    existing = {}
    with meta_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            existing[row["chunk_id"]] = {"row": i, "text_hash": row["text_hash"], "meta": row}
    embeddings_arr = np.load(emb_path)
    return existing, embeddings_arr


def build_index(config_path: Path = BASE_DIR / "config.yaml", provider: str = "local") -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    doc_ids = [s["doc_id"] for s in config["sources"]]
    model_name = config["embeddings"]["local_model"] if provider == "local" else config["embeddings"]["openai_model"]
    index_dir = PROCESSED_DIR / ("index" if provider == "local" else "index_openai")

    chunks = _load_all_chunks(doc_ids)
    for c in chunks:
        c["text_hash"] = _text_hash(c["text"])

    existing, existing_embeddings = _load_existing_index(index_dir)

    to_embed = [c for c in chunks if existing.get(c["chunk_id"], {}).get("text_hash") != c["text_hash"]]
    reused = len(chunks) - len(to_embed)

    backend = None
    new_vectors = {}
    t0 = time.time()
    if to_embed:
        backend = embeddings.get_backend(provider, model_name)
        vecs = backend.encode([c["text"] for c in to_embed])
        for c, v in zip(to_embed, vecs):
            new_vectors[c["chunk_id"]] = v
    indexing_time_seconds = round(time.time() - t0, 2)

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

    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "embeddings.npy", np.array(final_vectors, dtype="float32"))
    with (index_dir / "metadata.jsonl").open("w", encoding="utf-8") as f:
        for m in final_meta:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    cost_usd = 0.0
    if provider == "openai" and backend is not None and backend.total_tokens_used:
        record = costs.log_call(
            provider="openai",
            model=model_name,
            call_type="embedding",
            input_tokens=backend.total_tokens_used,
            output_tokens=0,
            note=f"build_index: {len(to_embed)} chunks nuevos",
        )
        cost_usd = record.usd_cost

    report = {
        "provider": provider,
        "model_name": model_name,
        "embedding_dim": dim,
        "n_chunks_total": len(chunks),
        "n_chunks_newly_embedded": len(to_embed),
        "n_chunks_reused_from_previous_index": reused,
        "indexing_time_seconds": indexing_time_seconds,
        "cost_usd_this_run": cost_usd,
    }
    (index_dir / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import sys

    provider_arg = sys.argv[1] if len(sys.argv) > 1 else "local"
    print(json.dumps(build_index(provider=provider_arg), ensure_ascii=False, indent=2))
