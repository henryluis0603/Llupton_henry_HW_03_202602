"""Fase 3 (Tarea 2): motor de consulta hibrido (semantico + filtros
estructurados), reusando el indice de embeddings de hybrid_index.py.

`search(question, department=None, category=None, min_amount=None,
max_amount=None, date_from=None, date_to=None, top_k=10)` aplica primero
los filtros ESTRUCTURADOS (condiciones exactas/rango, baratas de calcular)
sobre las 20,422 filas, y luego el filtro SEMANTICO (similitud coseno)
solo sobre lo que paso los filtros -- evita gastar computo semantico en
filas que ya no califican, y evita falsos positivos semanticos fuera del
rango pedido (ej. "obras en Cusco" no debe devolver procesos de Lima solo
porque el texto es semanticamente parecido).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
INDEX_DIR = BASE_DIR / "data" / "processed" / "hybrid_index"

_STATE = {}


def _load_state():
    if _STATE:
        return _STATE
    embeddings = np.load(INDEX_DIR / "embeddings.npy")
    metadata = [json.loads(l) for l in (INDEX_DIR / "metadata.jsonl").open(encoding="utf-8")]
    from sentence_transformers import SentenceTransformer

    build_report = json.loads((INDEX_DIR / "build_report.json").read_text(encoding="utf-8"))
    model = SentenceTransformer(build_report["model_name"])
    _STATE.update(embeddings=embeddings, metadata=metadata, model=model)
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
    sims = sub_embeddings @ q_vec

    order = np.argsort(-sims)[:top_k]
    results = []
    for rank in order:
        sim = float(sims[rank])
        if sim < similarity_threshold:
            continue
        row = dict(state["metadata"][candidate_idx[rank]])
        row["similarity"] = round(sim, 4)
        results.append(row)
    return results
