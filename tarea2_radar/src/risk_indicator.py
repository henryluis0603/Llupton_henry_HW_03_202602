"""Fase 5 (Tarea 2): indicador de riesgo -- adjudicaciones a postor unico.

Metodologia:
  - Un proceso cuenta como "adjudicado" si su `ocid` aparece en
    com_awards.csv de su mes de origen.
  - Un proceso adjudicado es de "postor unico" si
    `compiledRelease/tender/numberOfTenderers` == 1 (un solo participante
    presento oferta). Es una aproximacion: mide competencia en la etapa de
    presentacion de ofertas, no verifica coordinacion ni irregularidad.
  - Se calcula el % de procesos adjudicados que fueron de postor unico,
    por departamento y por comprador (`buyer_name`).

ADVERTENCIA (tal como pide el enunciado): este indicador senala la
necesidad de investigar, NO prueba irregularidad. Un % alto de postor
unico puede deberse a mercados de proveedores pequenos (zonas rurales,
bienes/servicios muy especializados) y no necesariamente a mala practica.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "data" / "outputs"
MONTHS = ["2026_06", "2026_07", "2026_08"]

MIN_PROCESOS_PARA_RANKING_COMPRADOR = 5


def _load_awarded_ocids(month: str) -> set[str]:
    with (RAW_DIR / month / "com_awards.csv").open(encoding="utf-8") as f:
        return {row["ocid"] for row in csv.DictReader(f)}


def build_risk_indicator() -> dict:
    rows = []
    for month in MONTHS:
        awarded = _load_awarded_ocids(month)
        with (PROCESSED_DIR / f"{month}_clean.jsonl").open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row["ocid"] not in awarded:
                    continue
                try:
                    n_tenderers = int(row["number_of_tenderers"]) if row["number_of_tenderers"] else None
                except ValueError:
                    n_tenderers = None
                if n_tenderers is None:
                    continue
                rows.append(
                    {
                        "ocid": row["ocid"],
                        "buyer_name": row["buyer_name"],
                        "buyer_department": row["buyer_department"],
                        "single_bidder": n_tenderers == 1,
                    }
                )

    n_awarded_with_tenderer_count = len(rows)

    by_department: dict[str, dict] = {}
    for r in rows:
        d = by_department.setdefault(r["buyer_department"], {"n_awarded": 0, "n_single_bidder": 0})
        d["n_awarded"] += 1
        d["n_single_bidder"] += int(r["single_bidder"])
    department_ranking = sorted(
        (
            {
                "department": dept,
                "n_awarded": v["n_awarded"],
                "n_single_bidder": v["n_single_bidder"],
                "single_bidder_share": round(v["n_single_bidder"] / v["n_awarded"], 4),
            }
            for dept, v in by_department.items()
        ),
        key=lambda x: -x["single_bidder_share"],
    )

    by_buyer: dict[str, dict] = {}
    for r in rows:
        b = by_buyer.setdefault(r["buyer_name"], {"n_awarded": 0, "n_single_bidder": 0, "department": r["buyer_department"]})
        b["n_awarded"] += 1
        b["n_single_bidder"] += int(r["single_bidder"])
    buyer_ranking = sorted(
        (
            {
                "buyer_name": buyer,
                "department": v["department"],
                "n_awarded": v["n_awarded"],
                "n_single_bidder": v["n_single_bidder"],
                "single_bidder_share": round(v["n_single_bidder"] / v["n_awarded"], 4),
            }
            for buyer, v in by_buyer.items()
            if v["n_awarded"] >= MIN_PROCESOS_PARA_RANKING_COMPRADOR
        ),
        key=lambda x: -x["single_bidder_share"],
    )[:10]

    report = {
        "n_processes_awarded_with_tenderer_count": n_awarded_with_tenderer_count,
        "overall_single_bidder_share": round(sum(r["single_bidder"] for r in rows) / n_awarded_with_tenderer_count, 4),
        "by_department": department_ranking,
        "top10_buyers_single_bidder_share": buyer_ranking,
        "min_processes_threshold_for_buyer_ranking": MIN_PROCESOS_PARA_RANKING_COMPRADOR,
        "advertencia": (
            "Este indicador senala la necesidad de investigar, no prueba irregularidad. "
            "Un porcentaje alto de postor unico puede deberse a mercados de proveedores "
            "pequenos (zonas rurales, bienes/servicios especializados)."
        ),
    }

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "risk_indicator.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build_risk_indicator(), ensure_ascii=False, indent=2))
