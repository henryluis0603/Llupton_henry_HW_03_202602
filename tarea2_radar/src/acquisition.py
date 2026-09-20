"""Fase 1 (Tarea 2): adquisicion de datos via la API real del portal OECE.

La API (`GET /api/v1/files`) y los meses ya descargados manualmente en esta
sesion (junio-agosto 2026) estan documentados en
docs/tarea2_fase1_adquisicion.md. Este script automatiza esa misma
descarga para poder correrla de nuevo mas adelante (actualizaciones) sin
tener que repetir los pasos manuales:

  1. Consulta `GET /api/v1/files` para ver que meses estan disponibles.
  2. Descarga solo los meses que TODAVIA no existen en data/raw/ (cache:
     no vuelve a descargar un mes ya presente, para no golpear el portal
     innecesariamente).
  3. Aplica una espera (throttling) entre descargas.
  4. Descomprime cada ZIP mensual en data/raw/<anio>_<mes>/.
  5. Registra cada corrida en logs/acquisition_log.jsonl (que meses se
     pidieron, cuales ya estaban en cache, cuales se descargaron, cuanto
     tardo) -- el "cost logging" de la Tarea 1 no aplica aqui (no hay
     llamadas a un LLM en esta fase), pero el enunciado exige loguear el
     proceso de adquisicion igual.

Uso: `python3 src/acquisition.py` (sin argumentos: descarga cualquier mes
nuevo que el portal tenga y que aun no este en data/raw/).
"""
from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
LOGS_DIR = BASE_DIR / "logs"
FILES_API = "https://contratacionesabiertas.oece.gob.pe/api/v1/files"
THROTTLE_SECONDS = 2.0


def _get_json(url: str) -> dict:
    with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path) -> None:
    with urlopen(Request(url), timeout=120) as resp:
        dest.write_bytes(resp.read())


def _month_dir_name(file_id: str) -> str:
    # file_id tiene forma "seace_v3-2026-09" -> carpeta "2026_09"
    _, year, month = file_id.rsplit("-", 2)
    return f"{year}_{month}"


def run(months_to_skip_download: bool = False) -> dict:
    listing = _get_json(FILES_API)
    log_entry = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "available": [], "downloaded": [], "cached": []}

    for item in listing["results"]:
        month_dir = _month_dir_name(item["id"])
        log_entry["available"].append(month_dir)
        target_dir = RAW_DIR / month_dir
        if target_dir.exists() and any(target_dir.iterdir()):
            log_entry["cached"].append(month_dir)
            continue
        if months_to_skip_download:
            continue

        zip_path = RAW_DIR / f"seace_v3_{month_dir}.zip"
        _download(item["files"]["csv"], zip_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target_dir)
        log_entry["downloaded"].append(month_dir)
        time.sleep(THROTTLE_SECONDS)  # throttling entre descargas

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with (LOGS_DIR / "acquisition_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    return log_entry


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
