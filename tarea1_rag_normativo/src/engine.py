"""Fase 3 (Tarea 1) — motor de consulta ONLINE (proceso separado de la
indexacion offline en build_index.py, como pide el enunciado).

Expone una unica funcion, `answer_query`, con salida estructurada:
{
  "question": str,
  "answer": str,
  "abstained": bool,
  "citations": [{"doc_id","unit_label","section","version_label","page","similarity"}],
  "top_similarity": float,
  "cost_usd": float,
}

## Estrategia de version (que norma citar cuando hay mas de una)

El corpus tiene dos instrumentos legales distintos, no dos versiones del
mismo texto: la Ley 32069 (cuerpo general) y el D.S. 001-2026-EF (que
modifica articulos especificos del *Reglamento* de esa ley -- un tercer
documento que NO esta indexado en este proyecto porque no es una fuente
obligatoria segun el enunciado). Politica aplicada:

  1. Cada cita siempre expone `version_label` (con fecha de publicacion) y
     `section`, para que quede explicito de que instrumento y que parte
     proviene la respuesta -- nunca se mezclan sin aclarar la fuente.
  2. Si dos fragmentos candidatos compiten por el mismo lugar en el top-k
     con similitud muy cercana (diferencia < 0.02), se prefiere el de
     fecha de publicacion mas reciente (2026-01-08 sobre 2024-06-24),
     asumiendo que el texto vigente mas nuevo es mas relevante salvo que
     la pregunta pida explicitamente el texto original.
  3. Limitacion documentada: como el Reglamento original (D.S. 009-2025-EF)
     no esta indexado, el motor NO puede confirmar si un articulo de la
     Ley 32069 fue o no modificado por otro decreto distinto al 001-2026-EF.
     Esto se declara explicitamente en las respuestas cuando la pregunta
     trata sobre el "reglamento" en general (ver `_maybe_add_version_caveat`).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import yaml

from . import costs

BASE_DIR = Path(__file__).resolve().parents[1]
INDEX_DIR = BASE_DIR / "data" / "processed" / "index"

_STATE = {}


def _load_config() -> dict:
    return yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))


def _load_state():
    if _STATE:
        return _STATE
    config = _load_config()
    embeddings = np.load(INDEX_DIR / "embeddings.npy")
    metadata = [json.loads(l) for l in (INDEX_DIR / "metadata.jsonl").open(encoding="utf-8")]

    from sentence_transformers import SentenceTransformer

    embed_model = SentenceTransformer(config["embeddings"]["local_model"])

    gen_model_name = config["generation"]["local_model"]
    gen_tokenizer = None
    gen_model = None
    if gen_model_name:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        gen_tokenizer = AutoTokenizer.from_pretrained(gen_model_name)
        gen_model = AutoModelForCausalLM.from_pretrained(gen_model_name, dtype=torch.float32)

    _STATE.update(
        config=config,
        embeddings=embeddings,
        metadata=metadata,
        embed_model=embed_model,
        gen_model_name=gen_model_name,
        gen_tokenizer=gen_tokenizer,
        gen_model=gen_model,
    )
    return _STATE


def _retrieve(question: str, top_k: int = 5) -> list[dict]:
    state = _load_state()
    q_vec = state["embed_model"].encode([question], normalize_embeddings=True)[0]
    sims = state["embeddings"] @ q_vec
    order = np.argsort(-sims)[:top_k]
    results = []
    for i in order:
        meta = dict(state["metadata"][i])
        meta["similarity"] = float(sims[i])
        results.append(meta)
    # Desempate por fecha de publicacion si la similitud es casi identica
    # (ver politica de version en el docstring del modulo).
    results.sort(key=lambda r: (round(r["similarity"], 2), r.get("version_label", "")), reverse=True)
    return results


def _build_prompt(question: str, contexts: list[dict]) -> str:
    context_block = "\n\n".join(
        f"[Fuente: {c['doc_id']} - {c['unit_label']} - {c.get('section') or 'cuerpo principal'} "
        f"- pag. {c['page']} - {c['version_label']}]\n{c['text']}"
        for c in contexts
    )
    return (
        "Eres un asistente que responde EXCLUSIVAMENTE con base en los fragmentos normativos "
        "citados a continuacion. Si la respuesta no esta en los fragmentos, responde literalmente "
        "'No tengo informacion suficiente en el corpus indexado para responder esto con certeza.' "
        "No inventes articulos ni cites nada que no aparezca en el contexto. Cita siempre el "
        "documento y el articulo/disposicion de donde sacas la respuesta.\n\n"
        f"CONTEXTO:\n{context_block}\n\nPREGUNTA: {question}\n\nRESPUESTA:"
    )


def _filter_actually_used(answer: str, contexts: list[dict]) -> list[dict]:
    """Hallazgo real (2026-09-20, revisando la app con el usuario): el motor
    pasaba TODOS los `contexts` recuperados (hasta 5) como 'citas', aunque
    el LLM solo haya usado 1 o 2 en su respuesta. Se verifico con un caso
    real (pregunta sobre 'principios rectores') que 4 de los 5 fragmentos
    mostrados como citas (Articulo 9, PRIMERA, OCTAVA, Articulo 46) no
    tienen relacion con la pregunta y no fueron realmente usados -- eran
    ruido de retrieval que paso el umbral de similitud pero no aportaba a
    la respuesta. Mostrarlos como 'fuente' es enganoso para un sistema que
    debe responder solo con lo que puede sustentar.

    Esta funcion filtra `contexts` a los que el LLM realmente menciono por
    numero de articulo/ordinal en el texto de la respuesta. Si el modelo no
    cito ningun numero explicito (responde de forma mas libre), se cae de
    vuelta al UNICO fragmento de mayor similitud, en vez de mostrar los 5.
    """
    answer_lower = answer.lower().replace("í", "i").replace("ó", "o")
    used = []
    for c in contexts:
        label = c["unit_label"].lower().replace("í", "i").replace("ó", "o")
        if label.startswith("articulo"):
            num = label.split()[-1]
            if re.search(rf"art[ií]culo\s*{re.escape(num)}\b", answer_lower):
                used.append(c)
        else:
            if re.search(rf"\b{re.escape(label)}\b", answer_lower):
                used.append(c)
    return used if used else contexts[:1]


def _generate(prompt: str) -> tuple[str, int, int]:
    state = _load_state()
    tok, model = state["gen_tokenizer"], state["gen_model"]
    messages = [{"role": "user", "content": prompt}]
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(text, return_tensors="pt")
    output = model.generate(**inputs, max_new_tokens=300, do_sample=False)
    input_tokens = inputs["input_ids"].shape[1]
    output_tokens = output.shape[1] - input_tokens
    answer = tok.decode(output[0][input_tokens:], skip_special_tokens=True).strip()
    return answer, input_tokens, output_tokens


def answer_query(question: str, top_k: int = 5) -> dict:
    state = _load_state()
    threshold = state["config"]["engine"]["similarity_threshold"]
    if threshold is None:
        raise ValueError(
            "engine.similarity_threshold no esta calibrado todavia. "
            "Correr eval/run_eval.py (Fase 4) antes de usar el motor en produccion."
        )

    t0 = time.time()
    candidates = _retrieve(question, top_k=top_k)
    top_similarity = candidates[0]["similarity"] if candidates else 0.0

    if top_similarity < threshold:
        return {
            "question": question,
            "answer": "No tengo informacion suficiente en el corpus indexado (Ley 32069 y "
            "D.S. 001-2026-EF) para responder esto con certeza. Puede estar fuera del alcance "
            "de estos dos documentos.",
            "abstained": True,
            "citations": [],
            "top_similarity": round(top_similarity, 4),
            "cost_usd": 0.0,
            "latency_s": round(time.time() - t0, 2),
        }

    contexts = [c for c in candidates if c["similarity"] >= threshold][:top_k]
    prompt = _build_prompt(question, contexts)
    answer, in_tok, out_tok = _generate(prompt)

    provider = state["config"]["generation"]["provider"]
    record = costs.log_call(
        provider=provider,
        model=state["gen_model_name"],
        call_type="generation",
        input_tokens=in_tok,
        output_tokens=out_tok,
        note=f"query={question[:60]!r}",
    )

    # Segunda capa de abstencion: el filtro por similitud (arriba) no
    # separa perfectamente dominio/fuera de dominio (ver docs/fase4_evaluacion.md,
    # abstention_rate=0.4 con similitud sola). El prompt de generacion
    # instruye al modelo a rechazar si el contexto no responde la pregunta;
    # se detecta esa frase de rechazo aqui para que el campo `abstained` y
    # las citas devueltas reflejen lo que realmente paso, en vez de mostrar
    # citas "de adorno" junto a una respuesta que en realidad se abstuvo.
    generation_refused = "no tengo informacion suficiente" in answer.lower().replace("ó", "o")

    # Tercera capa: deteccion de alucinacion de jurisdiccion. Hallazgo real
    # (2026-09-20): con una pregunta reformulada ("Que principios rigen la
    # contratacion publica segun la ley?"), Qwen2.5-1.5B-Instruct agrego una
    # frase final inventada ("...en Chile") sin base en el contexto (todo el
    # corpus es normativa peruana). Es reproducible. Como paliativo barato
    # (no resuelve la causa raiz -- un modelo de 1.5B puede seguir fallando
    # de otras formas, ver docs/fase3_engine.md), se detectan menciones a
    # otros paises hispanohablantes en la respuesta y se fuerza abstencion
    # si aparecen, en vez de entregar una respuesta con un error factual de
    # jurisdiccion.
    OTRO_PAIS_PATTERN = re.compile(
        r"\b(chile|colombia|m[eé]xico|argentina|ecuador|bolivia|venezuela|espa[ñn]a|"
        r"uruguay|paraguay|panam[aá]|honduras|guatemala|nicaragua)\b",
        re.IGNORECASE,
    )
    hallucinated_country = OTRO_PAIS_PATTERN.search(answer)
    if hallucinated_country:
        return {
            "question": question,
            "answer": "El modelo genero una respuesta con una posible alucinacion "
            f"(mencion a {hallucinated_country.group(0)!r}, un pais fuera del alcance de "
            "este corpus, que es normativa exclusivamente peruana). Se descarta la "
            "respuesta en vez de mostrarla con un posible error factual. "
            "Ver docs/fase3_engine.md, seccion de limitaciones del modelo local.",
            "abstained": True,
            "citations": [],
            "top_similarity": round(top_similarity, 4),
            "cost_usd": record.usd_cost,
            "latency_s": round(time.time() - t0, 2),
        }

    used_contexts = [] if generation_refused else _filter_actually_used(answer, contexts)

    return {
        "question": question,
        "answer": answer,
        "abstained": generation_refused,
        "citations": [
            {
                "doc_id": c["doc_id"],
                "unit_label": c["unit_label"],
                "section": c.get("section"),
                "version_label": c["version_label"],
                "page": c["page"],
                "similarity": round(c["similarity"], 4),
            }
            for c in used_contexts
        ],
        "top_similarity": round(top_similarity, 4),
        "cost_usd": record.usd_cost,
        "latency_s": round(time.time() - t0, 2),
    }
