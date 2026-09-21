"""Fase 4 (Tarea 1): comparacion OBLIGATORIA de embeddings (enunciado):
"Build two indexes with exactly the same fragments" (local vs.
text-embedding-3-small de OpenAI), reportando por cada uno: Recall@k,
tiempo de indexacion, costo en USD, latencia promedio de consulta, y
dimension del vector.

Requiere OPENAI_API_KEY en .env. Si no esta, falla con un error
explicito (ver src/embeddings.py) en vez de simular numeros.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR.parent / ".env")

from src import build_index, costs, embeddings  # noqa: E402

ONLY_IN_DOMAIN = True  # Recall@k solo tiene sentido sobre las 15 preguntas in_domain


def _load_index(index_dir: Path):
    emb = np.load(index_dir / "embeddings.npy")
    meta = [json.loads(l) for l in (index_dir / "metadata.jsonl").open(encoding="utf-8")]
    return emb, meta


def _evaluate(provider: str, model_name: str, questions: list[dict]) -> dict:
    build_report = build_index.build_index(provider=provider)
    index_dir = BASE_DIR / "data" / "processed" / ("index" if provider == "local" else "index_openai")
    emb, meta = _load_index(index_dir)

    backend = embeddings.get_backend(provider, model_name)

    hits_at = {1: 0, 3: 0, 5: 0}
    latencies = []
    query_tokens_used = 0

    for q in questions:
        t0 = time.time()
        q_vec = backend.encode([q["question"]])[0]
        latencies.append(time.time() - t0)
        if provider == "openai":
            query_tokens_used += backend.total_tokens_used  # acumulado, se resta abajo

        sims = emb @ q_vec
        order = np.argsort(-sims)[:5]
        found_rank = next(
            (
                rank
                for rank, i in enumerate(order)
                if meta[i]["doc_id"] == q["expected_doc_id"] and meta[i]["unit_label"] == q["expected_unit_label"]
            ),
            None,
        )
        for k in (1, 3, 5):
            if found_rank is not None and found_rank < k:
                hits_at[k] += 1

    n = len(questions)
    query_cost_usd = 0.0
    if provider == "openai" and backend.total_tokens_used:
        record = costs.log_call(
            provider="openai",
            model=model_name,
            call_type="embedding",
            input_tokens=backend.total_tokens_used,
            output_tokens=0,
            note=f"compare_embeddings: {n} preguntas de evaluacion",
        )
        query_cost_usd = record.usd_cost

    return {
        "provider": provider,
        "model": model_name,
        "vector_dimension": build_report["embedding_dim"],
        "recall@1": round(hits_at[1] / n, 3),
        "recall@3": round(hits_at[3] / n, 3),
        "recall@5": round(hits_at[5] / n, 3),
        "indexing_time_seconds": build_report["indexing_time_seconds"],
        "indexing_cost_usd": build_report["cost_usd_this_run"],
        "avg_query_latency_seconds": round(sum(latencies) / len(latencies), 4),
        "query_cost_usd_this_eval": query_cost_usd,
        "total_cost_usd": round(build_report["cost_usd_this_run"] + query_cost_usd, 6),
    }


def main():
    config = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))
    all_questions = json.loads((BASE_DIR / "eval" / "questions.json").read_text(encoding="utf-8"))["questions"]
    in_domain = [q for q in all_questions if q["domain"] == "in_domain"]

    local_result = _evaluate("local", config["embeddings"]["local_model"], in_domain)
    openai_result = _evaluate("openai", config["embeddings"]["openai_model"], in_domain)

    report = {"local": local_result, "openai": openai_result}
    (BASE_DIR / "eval" / "embeddings_comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
