"""Calculo y logging de costos por llamada a un modelo de lenguaje.

Requisito del enunciado: "Cost logging for every LLM call" y "Cost
calculation with time-based pricing" (Fase 3).

Honestidad de datos: al no contar con una API key de OpenAI en este
proyecto (ver docs/fase3_engine.md), el proveedor de generacion activo es
local (Hugging Face, corre en esta maquina). El costo monetario real de
esas llamadas es $0.00 -- no se inventa un numero de "costo estimado"
para simular gasto que no ocurrio. La formula de precios de OpenAI queda
lista y probada (ver test en este archivo) para cuando se configure una
API key real.

"Time-based pricing" (los precios de un mismo modelo cambian con el
tiempo) se modela con una tabla de tarifas con fecha de vigencia; se usa
la tarifa vigente a la fecha de la llamada.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "cost_log.jsonl"

# Tarifas publicas de OpenAI por 1M tokens, con fecha de vigencia (fuente:
# pagina de precios de OpenAI). Se agregan nuevas entradas si el precio
# cambia; se usa la que tenga vigente_desde <= fecha de la llamada, la mas
# reciente de las que califican.
OPENAI_PRICING_USD_PER_1M_TOKENS = {
    "gpt-4o-mini": [
        {"vigente_desde": "2024-07-18", "input": 0.15, "output": 0.60},
    ],
    "text-embedding-3-small": [
        {"vigente_desde": "2024-01-25", "input": 0.02, "output": 0.0},
    ],
}


@dataclass
class CostRecord:
    timestamp: str
    provider: str
    model: str
    call_type: str  # "generation" | "embedding"
    input_tokens: int
    output_tokens: int
    usd_cost: float
    note: str = ""


def _rate_for(model: str, when: str) -> dict | None:
    entries = OPENAI_PRICING_USD_PER_1M_TOKENS.get(model)
    if not entries:
        return None
    applicable = [e for e in entries if e["vigente_desde"] <= when]
    if not applicable:
        return None
    return max(applicable, key=lambda e: e["vigente_desde"])


def estimate_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int, when: str | None = None) -> float:
    if provider == "huggingface_local":
        return 0.0
    if provider == "openai":
        when = when or time.strftime("%Y-%m-%d")
        rate = _rate_for(model, when)
        if rate is None:
            raise ValueError(f"No hay tarifa registrada para {model} vigente en {when}.")
        return round(input_tokens / 1_000_000 * rate["input"] + output_tokens / 1_000_000 * rate["output"], 6)
    raise ValueError(f"Proveedor desconocido: {provider}")


def log_call(provider: str, model: str, call_type: str, input_tokens: int, output_tokens: int, note: str = "") -> CostRecord:
    when = time.strftime("%Y-%m-%d")
    cost = estimate_cost_usd(provider, model, input_tokens, output_tokens, when)
    record = CostRecord(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        provider=provider,
        model=model,
        call_type=call_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usd_cost=cost,
        note=note,
    )
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return record


if __name__ == "__main__":
    # Auto-test de la formula de precios (no requiere API key: es solo
    # aritmetica sobre la tabla de tarifas).
    c = estimate_cost_usd("openai", "gpt-4o-mini", input_tokens=1000, output_tokens=200, when="2026-09-20")
    assert abs(c - (1000/1_000_000*0.15 + 200/1_000_000*0.60)) < 1e-9
    print("Formula de costo OpenAI verificada:", c, "USD para 1000 in / 200 out tokens de gpt-4o-mini")
    print("Costo local (Hugging Face):", estimate_cost_usd("huggingface_local", "qwen2.5-1.5b-instruct", 1000, 200))
