"""Fase 4 (Tarea 1): evaluacion con el set de 20 preguntas.

Calcula, usando SOLO retrieval (sin generacion, para que correr esto no
dependa del modelo de lenguaje ni tome minutos por pregunta):
  - Recall@1 / Recall@3 / Recall@5 sobre las 15 preguntas in_domain
    (¿aparece el articulo esperado entre los top-k recuperados?).
  - La distribucion de similitud maxima obtenida para las preguntas
    in_domain vs. las out_of_domain, que es la evidencia real usada para
    calibrar `engine.similarity_threshold` en config.yaml (Fase 3).

Limitacion declarada explicitamente (no se inventa el dato): la
comparacion de embeddings "modelo local vs. OpenAI text-embedding-3-small"
que pide el enunciado NO se pudo ejecutar en este proyecto porque no hay
una OPENAI_API_KEY configurada (ver docs/fase4_evaluacion.md). El codigo
para esa comparacion (`compare_with_openai`) esta escrito y listo, pero
lanza un error explicito si se intenta correr sin la key, en vez de
simular un resultado.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import yaml

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_index():
    embeddings = np.load(BASE_DIR / "data" / "processed" / "index" / "embeddings.npy")
    metadata = [json.loads(l) for l in (BASE_DIR / "data" / "processed" / "index" / "metadata.jsonl").open(encoding="utf-8")]
    return embeddings, metadata


def _retrieve_raw(question: str, embed_model, embeddings, metadata, top_k=5):
    q_vec = embed_model.encode([question], normalize_embeddings=True)[0]
    sims = embeddings @ q_vec
    order = np.argsort(-sims)[:top_k]
    return [(metadata[i], float(sims[i])) for i in order]


def compare_with_openai(*_args, **_kwargs):
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "No hay OPENAI_API_KEY en el entorno. La comparacion de embeddings local vs. "
            "text-embedding-3-small no se puede ejecutar honestamente sin la key real. "
            "Ver docs/fase4_evaluacion.md, seccion 'Comparacion de embeddings pendiente'."
        )
    raise NotImplementedError("Implementar llamada real a la API de OpenAI cuando se tenga la key.")


def main():
    config = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))
    from sentence_transformers import SentenceTransformer

    embed_model = SentenceTransformer(config["embeddings"]["local_model"])
    embeddings, metadata = _load_index()

    questions = json.loads((BASE_DIR / "eval" / "questions.json").read_text(encoding="utf-8"))["questions"]

    per_question = []
    in_domain_top_sims = []
    out_domain_top_sims = []
    hits_at = {1: 0, 3: 0, 5: 0}
    n_in_domain = 0

    for q in questions:
        results = _retrieve_raw(q["question"], embed_model, embeddings, metadata, top_k=5)
        top_sim = results[0][1]
        row = {
            "id": q["id"],
            "domain": q["domain"],
            "question": q["question"],
            "top_similarity": round(top_sim, 4),
            "top5": [
                {"doc_id": m["doc_id"], "unit_label": m["unit_label"], "similarity": round(s, 4)}
                for m, s in results
            ],
        }
        if q["domain"] == "in_domain":
            n_in_domain += 1
            in_domain_top_sims.append(top_sim)
            ranks = [
                i for i, (m, _) in enumerate(results)
                if m["doc_id"] == q["expected_doc_id"] and m["unit_label"] == q["expected_unit_label"]
            ]
            found_rank = ranks[0] if ranks else None
            row["expected"] = {"doc_id": q["expected_doc_id"], "unit_label": q["expected_unit_label"]}
            row["found_at_rank"] = found_rank  # 0-indexed, None si no aparece en top-5
            for k in (1, 3, 5):
                if found_rank is not None and found_rank < k:
                    hits_at[k] += 1
        else:
            out_domain_top_sims.append(top_sim)
        per_question.append(row)

    recall = {f"recall@{k}": round(v / n_in_domain, 3) for k, v in hits_at.items()}

    # Calibracion del umbral: se busca un valor que separe las similitudes
    # maximas de las preguntas in_domain (deberian ser altas, porque su
    # respuesta SI esta en el corpus) de las out_of_domain (deberian ser
    # mas bajas, porque su respuesta NO esta en el corpus).
    # Rango amplio (0.30-0.90): un rango mas angosto (se probo 0.20-0.60
    # primero) dejaba fuera el verdadero optimo (~0.64), y el script elegia
    # un umbral degenerado que nunca abstiene. Ver docs/fase4_evaluacion.md.
    threshold_candidates = np.round(np.arange(0.30, 0.91, 0.01), 2)
    best_threshold, best_score = None, -1
    for t in threshold_candidates:
        correctly_answered = sum(1 for s in in_domain_top_sims if s >= t)
        correctly_abstained = sum(1 for s in out_domain_top_sims if s < t)
        score = correctly_answered + correctly_abstained
        if score > best_score:
            best_score, best_threshold = score, float(t)

    abstention_rate_out_domain_at_best = sum(1 for s in out_domain_top_sims if s < best_threshold) / len(out_domain_top_sims)
    coverage_in_domain_at_best = sum(1 for s in in_domain_top_sims if s >= best_threshold) / len(in_domain_top_sims)

    report = {
        "recall": recall,
        "in_domain_top_similarity": {
            "min": round(min(in_domain_top_sims), 4),
            "max": round(max(in_domain_top_sims), 4),
            "mean": round(sum(in_domain_top_sims) / len(in_domain_top_sims), 4),
            "values": [round(s, 4) for s in in_domain_top_sims],
        },
        "out_domain_top_similarity": {
            "min": round(min(out_domain_top_sims), 4),
            "max": round(max(out_domain_top_sims), 4),
            "mean": round(sum(out_domain_top_sims) / len(out_domain_top_sims), 4),
            "values": [round(s, 4) for s in out_domain_top_sims],
        },
        "calibrated_similarity_threshold": best_threshold,
        "coverage_in_domain_at_threshold": round(coverage_in_domain_at_best, 3),
        "abstention_rate_out_domain_at_threshold": round(abstention_rate_out_domain_at_best, 3),
        "per_question": per_question,
        "openai_embeddings_comparison": "NO EJECUTADA: falta OPENAI_API_KEY (ver docs/fase4_evaluacion.md)",
    }

    out_path = BASE_DIR / "eval" / "results.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "per_question"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
