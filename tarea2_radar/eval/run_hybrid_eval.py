"""Fase 3 (Tarea 2): evaluacion del RAG hibrido con 10 preguntas de
relevancia conocida, prueba de transferibilidad del umbral calibrado en
la Tarea 1 (0.64), y comparacion honesta ANTES/DESPUES de agregar fusion
con BM25 (ver docs/tarea2_fase3_rag_hibrido.md, seccion 4 -- no se asume
que agregar BM25 mejora las cosas, se mide).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from src.hybrid_engine import search  # noqa: E402

TASK1_THRESHOLD = 0.64  # ver tarea1_rag_normativo/config.yaml


def _run_recall(questions: list[dict], use_bm25: bool) -> dict:
    hits_at = {1: 0, 3: 0, 5: 0}
    top_similarities = []
    per_question = []

    for q in questions:
        results = search(q["question"], top_k=5, use_bm25=use_bm25, **q.get("filters", {}))
        top_sim = results[0]["similarity"] if results else 0.0
        top_similarities.append(top_sim)
        found_rank = next((i for i, r in enumerate(results) if r["ocid"] in q["expected_ocids"]), None)
        for k in (1, 3, 5):
            if found_rank is not None and found_rank < k:
                hits_at[k] += 1
        per_question.append(
            {
                "id": q["id"],
                "question": q["question"],
                "found_at_rank": found_rank,
                "top_similarity": round(top_sim, 4),
                "top3_ocids": [r["ocid"] for r in results[:3]],
            }
        )

    n = len(questions)
    return {
        "recall": {f"recall@{k}": round(v / n, 3) for k, v in hits_at.items()},
        "top_similarity_stats": {
            "min": round(min(top_similarities), 4),
            "max": round(max(top_similarities), 4),
            "mean": round(sum(top_similarities) / n, 4),
        },
        "n_above_task1_threshold": sum(1 for s in top_similarities if s >= TASK1_THRESHOLD),
        "n_questions": n,
        "per_question": per_question,
    }


def main():
    questions = json.loads((BASE_DIR / "eval" / "hybrid_questions.json").read_text(encoding="utf-8"))["questions"]

    only_semantic = _run_recall(questions, use_bm25=False)
    semantic_plus_bm25 = _run_recall(questions, use_bm25=True)

    n = only_semantic["n_questions"]
    report = {
        "comparacion_recall": {
            "solo_semantico": only_semantic["recall"],
            "semantico_mas_bm25": semantic_plus_bm25["recall"],
        },
        "solo_semantico": {k: v for k, v in only_semantic.items() if k != "per_question"},
        "semantico_mas_bm25": {k: v for k, v in semantic_plus_bm25.items() if k != "per_question"},
        "task1_threshold_transferability": {
            "threshold_probado": TASK1_THRESHOLD,
            "preguntas_que_superan_el_umbral_de_tarea1": f"{only_semantic['n_above_task1_threshold']}/{n}",
            "conclusion": (
                "NO transferible tal cual"
                if only_semantic["n_above_task1_threshold"] < n * 0.8
                else "Transferible razonablemente"
            ),
        },
        "per_question_semantico_mas_bm25": semantic_plus_bm25["per_question"],
        "per_question_solo_semantico": only_semantic["per_question"],
    }
    (BASE_DIR / "eval" / "hybrid_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["comparacion_recall"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
