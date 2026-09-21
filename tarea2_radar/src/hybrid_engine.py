"""Fase 3 (Tarea 2): motor de consulta hibrido (semantico + lexico BM25 +
filtros estructurados), reusando el indice de embeddings de hybrid_index.py.

`search()` aplica primero los filtros ESTRUCTURADOS (condiciones
exactas/rango, baratas) sobre las 20,422 filas, y luego combina DOS
rankings sobre lo que paso el filtro:

  1. Semantico: similitud coseno con el mismo modelo de embeddings de la
     Tarea 1.
  2. Lexico (BM25): coincidencia de palabras clave, mejor para texto
     administrativo con codigos, siglas y nombres propios.

Se combinan por Reciprocal Rank Fusion (RRF, k=60) en vez de promediar
puntajes, porque similitud coseno (0-1) y puntaje BM25 (sin cota superior
fija) no son comparables directamente sin normalizar de forma arbitraria.

## Por que se agrego esto

Hallazgo real (ver docs/tarea2_fase3_rag_hibrido.md): con SOLO similitud
semantica, Recall@5 = 0.3 sobre 10 preguntas de relevancia conocida (peor
que el 0.8 de la Tarea 1). Caso concreto: "agua potable y alcantarillado"
devolvia como primer resultado un proyecto de canchas deportivas. La
hipotesis fue que los titulos/descripciones de contrataciones (cargados
de codigos de ruta, siglas, nombres de localidades) son peor manejados
por un modelo de embeddings de proposito general que por coincidencia
lexica. Este modulo prueba esa hipotesis con BM25 real (ver
eval/run_hybrid_eval.py para el resultado medido, no solo la intuicion).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
INDEX_DIR = BASE_DIR / "data" / "processed" / "hybrid_index"

RRF_K = 60
_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)

_STATE = {}


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower().replace("¿", " "))


def _load_state():
    if _STATE:
        return _STATE
    embeddings = np.load(INDEX_DIR / "embeddings.npy")
    metadata = [json.loads(l) for l in (INDEX_DIR / "metadata.jsonl").open(encoding="utf-8")]
    from sentence_transformers import SentenceTransformer

    build_report = json.loads((INDEX_DIR / "build_report.json").read_text(encoding="utf-8"))
    model = SentenceTransformer(build_report["model_name"])

    from rank_bm25 import BM25Okapi

    corpus_tokens = [_tokenize(f"{r['tender_title']} {r['tender_description']}") for r in metadata]
    bm25 = BM25Okapi(corpus_tokens)

    _STATE.update(embeddings=embeddings, metadata=metadata, model=model, bm25=bm25)
    return _STATE


def _passes_structured_filters(row: dict, department, category, min_amount, max_amount, date_from, date_to) -> bool:
    if department and row.get("buyer_department") != department:
        return False
    if category and row.get("main_category") != category:
        return False
    amount = row.get("amount_pen")
    try:
        amount = float(amount) if amount not in (None, "") else None
    except ValueError:
        amount = None
    if min_amount is not None and (amount is None or amount < min_amount):
        return False
    if max_amount is not None and (amount is None or amount > max_amount):
        return False
    date_pub = (row.get("date_published") or "")[:10]
    if date_from and (not date_pub or date_pub < date_from):
        return False
    if date_to and (not date_pub or date_pub > date_to):
        return False
    return True


def search(
    question: str,
    department: str | None = None,
    category: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    top_k: int = 10,
    similarity_threshold: float = 0.0,
    use_bm25: bool = True,
) -> list[dict]:
    state = _load_state()
    candidate_idx = [
        i
        for i, row in enumerate(state["metadata"])
        if _passes_structured_filters(row, department, category, min_amount, max_amount, date_from, date_to)
    ]
    if not candidate_idx:
        return []

    q_vec = state["model"].encode([question.replace("¿", " ")], normalize_embeddings=True)[0]
    sub_embeddings = state["embeddings"][candidate_idx]
    sims = sub_embeddings @ q_vec  # similitud coseno, una por candidato

    # Ranking semantico (posicion, no puntaje) entre los candidatos
    sem_order = np.argsort(-sims)
    sem_rank = np.empty(len(candidate_idx), dtype=int)
    sem_rank[sem_order] = np.arange(len(candidate_idx))

    if use_bm25:
        bm25_scores_all = state["bm25"].get_scores(_tokenize(question))
        bm25_scores = bm25_scores_all[candidate_idx]
        bm25_order = np.argsort(-bm25_scores)
        bm25_rank = np.empty(len(candidate_idx), dtype=int)
        bm25_rank[bm25_order] = np.arange(len(candidate_idx))
        rrf_score = 1.0 / (RRF_K + sem_rank + 1) + 1.0 / (RRF_K + bm25_rank + 1)
    else:
        rrf_score = 1.0 / (RRF_K + sem_rank + 1)

    final_order = np.argsort(-rrf_score)[:top_k]
    results = []
    for pos in final_order:
        sim = float(sims[pos])
        if sim < similarity_threshold:
            continue
        row = dict(state["metadata"][candidate_idx[pos]])
        row["similarity"] = round(sim, 4)
        row["rrf_score"] = round(float(rrf_score[pos]), 5)
        results.append(row)
    return results
