"""Fase 2 (Tarea 2): validacion de calidad de los datos de contrataciones.

Lee records.csv (uno por ocid, ver docs/tarea2_fase1_adquisicion.md) y
com_parties.csv (para el departamento del comprador) de cada mes
descargado, y produce data/processed/quality_report.json con:
  - duplicados (por ocid, dentro de un mes y entre meses)
  - montos faltantes (tender/value/amount)
  - descripciones faltantes (tender/description)
  - errores de ubicacion (departamento no normalizable a los 25 oficiales)
  - inconsistencias de codificacion (caracteres de reemplazo / mojibake)
  - tasa de recuperacion: filas utilizables / filas totales tras normalizar
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

MONTHS = ["2026_06", "2026_07", "2026_08"]

# Los 25 departamentos oficiales del Peru (Lima Metropolitana y la
# provincia constitucional del Callao se mantienen dentro de LIMA/CALLAO,
# que son las 2 entradas correspondientes de esta lista de 25).
DEPARTAMENTOS_OFICIALES = {
    "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA",
    "CALLAO", "CUSCO", "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN",
    "LA LIBERTAD", "LAMBAYEQUE", "LIMA", "LORETO", "MADRE DE DIOS",
    "MOQUEGUA", "PASCO", "PIURA", "PUNO", "SAN MARTIN", "TACNA", "TUMBES",
    "UCAYALI",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize_department(raw: str | None) -> str | None:
    """Devuelve el nombre oficial del departamento, o None si no se puede
    normalizar (esto se cuenta como 'error de ubicacion')."""
    if not raw or not raw.strip():
        return None
    candidate = _strip_accents(raw.strip().upper())
    candidate = re.sub(r"\s+", " ", candidate)
    if candidate in DEPARTAMENTOS_OFICIALES:
        return candidate
    # Variantes conocidas (defensivo: en la muestra real de 2026-06/07/08
    # no aparecieron, pero se documentan por si otros meses las traen).
    aliases = {
        "MADRE DE DIOS ": "MADRE DE DIOS",
        "PROV. CONST. DEL CALLAO": "CALLAO",
        "LIMA METROPOLITANA": "LIMA",
        "LIMA PROVINCIAS": "LIMA",
    }
    return aliases.get(candidate)


def _fix_stray_backslash_quote(text: str | None) -> str | None:
    """Hallazgo real (2026-09-20, probando el dashboard con el usuario):
    el nombre de un comprador se mostraba como
    'UNIDAD EJECUTORA 022 \\"PROYECTO DE TRANSFORMACION...' con una barra
    invertida literal. Se rastreo hasta el archivo FUENTE (records.csv de
    OECE): el campo crudo contiene la secuencia de bytes '\\""' (una barra
    invertida seguida de DOS comillas) en vez del escape CSV estandar
    '""'. El modulo csv de Python reduce las dos comillas a una (regla
    estandar), pero dejaje la barra invertida como caracter literal, ya
    que no es un caracter especial en CSV estandar -- es un defecto real
    de publicacion de OECE, no un bug de este pipeline ni algo ambiguo
    como el caso de '¿' (aqui se puede corregir con certeza: ningun
    nombre de entidad contiene legitimamente una barra invertida pegada a
    una comilla). Afecta 7 filas de 20,422 (5 en junio, 2 en julio, 0 en
    agosto) en buyer_name/tender_title/tender_description.
    """
    if not text:
        return text
    return text.replace('\\"', '"')


def _has_encoding_issue(text: str | None) -> bool:
    """Hallazgo real (2026-09-20): la primera version de esta funcion solo
    buscaba U+FFFD/'Ã', y reporto '0 problemas de codificacion' en los 3
    meses. Al revisar manualmente titulos reales se encontro que 1,821 de
    7,303 filas (25%) de junio 2026 usan '¿' como sustituto corrupto de un
    guion o una comilla de apertura (ej. 'GTI ¿ Local Carabaya', deberia
    ser 'GTI - Local Carabaya' o similar) -- NO como signo de interrogacion
    real. Se verifico la hipotesis: de esas 1,821 filas, 1,820 no tienen un
    '?' de cierre correspondiente (una pregunta real en español siempre
    lleva ambos signos), lo que confirma que es corrupcion, no contenido
    real. No se puede recuperar con certeza cual era el caracter original
    (guion, comilla u otro), asi que se cuenta como 'problema de
    codificacion' pero NO se intenta adivinar el caracter correcto."""
    if not text:
        return False
    if "�" in text or "Ã" in text or "�" in text:
        return True
    if "¿" in text and "?" not in text:
        return True
    if '\\"' in text:
        return True
    return False


def _load_buyer_departments(month: str) -> dict[str, str | None]:
    path = RAW_DIR / month / "com_parties.csv"
    result = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "buyer" in row.get("compiledRelease/parties/0/roles", ""):
                result[row["ocid"]] = row.get("compiledRelease/parties/0/address/department")
    return result


def validate_month(month: str) -> dict:
    records_path = RAW_DIR / month / "records.csv"
    buyer_dept = _load_buyer_departments(month)

    seen_ocids = set()
    duplicates_within_month = 0
    missing_amount = 0
    missing_description = 0
    location_errors = 0
    encoding_issues = 0
    rows = []

    with records_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ocid = row["ocid"]
            if ocid in seen_ocids:
                duplicates_within_month += 1
                continue
            seen_ocids.add(ocid)

            amount = row.get("compiledRelease/tender/value/amount", "").strip()
            description = row.get("compiledRelease/tender/description", "").strip()
            title = row.get("compiledRelease/tender/title", "").strip()
            buyer_name = row.get("compiledRelease/buyer/name", "")

            if not amount:
                missing_amount += 1
            if not description and not title:
                missing_description += 1
            if _has_encoding_issue(description) or _has_encoding_issue(title) or _has_encoding_issue(buyer_name):
                encoding_issues += 1

            # Se corrige el defecto de '\"' (ver _fix_stray_backslash_quote)
            # DESPUES de contarlo como problema de calidad -- se cuenta lo
            # que vino mal, pero se guarda ya corregido porque es un caso
            # no ambiguo (a diferencia de '¿', que no se corrige).
            buyer_name = _fix_stray_backslash_quote(buyer_name)
            description = _fix_stray_backslash_quote(description)
            title = _fix_stray_backslash_quote(title)

            raw_dept = buyer_dept.get(ocid)
            norm_dept = normalize_department(raw_dept)
            if norm_dept is None:
                location_errors += 1

            rows.append(
                {
                    "ocid": ocid,
                    "month": month,
                    "buyer_name": buyer_name,
                    "buyer_department": norm_dept,
                    "tender_title": title or description[:120],
                    "tender_description": description,
                    "amount_pen": row.get("compiledRelease/tender/value/amount_PEN") or amount,
                    "main_category": row.get("compiledRelease/tender/mainProcurementCategory"),
                    "procurement_method": row.get("compiledRelease/tender/procurementMethod"),
                    "date_published": row.get("compiledRelease/tender/datePublished"),
                    "number_of_tenderers": row.get("compiledRelease/tender/numberOfTenderers"),
                }
            )

    n_total = len(seen_ocids) + duplicates_within_month
    out_path = PROCESSED_DIR / f"{month}_clean.jsonl"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {
        "month": month,
        "n_rows_raw": n_total,
        "n_rows_unique_ocid": len(seen_ocids),
        "duplicates_within_month": duplicates_within_month,
        "missing_amount": missing_amount,
        "missing_description_and_title": missing_description,
        "location_errors_unnormalizable": location_errors,
        "encoding_issues": encoding_issues,
        "recovery_rate": round(len(seen_ocids) / n_total, 4) if n_total else 0.0,
        "output_file": str(out_path.relative_to(PROCESSED_DIR.parents[1])),
    }


def main() -> None:
    per_month = [validate_month(m) for m in MONTHS]

    # Duplicados ENTRE meses (mismo ocid publicado/actualizado en mas de
    # un archivo mensual -- normal en OCDS por actualizaciones de estado,
    # pero se reporta para que quede documentado, no oculto).
    ocid_month_count: dict[str, list[str]] = {}
    for m in MONTHS:
        with (PROCESSED_DIR / f"{m}_clean.jsonl").open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                ocid_month_count.setdefault(row["ocid"], []).append(m)
    cross_month_duplicates = {k: v for k, v in ocid_month_count.items() if len(v) > 1}

    report = {
        "per_month": per_month,
        "n_ocid_appearing_in_multiple_months": len(cross_month_duplicates),
        "note_cross_month_duplicates": (
            "Un mismo ocid puede aparecer en mas de un archivo mensual porque OCDS republica "
            "el proceso completo cada vez que cambia de estado (convocado -> adjudicado -> "
            "contratado). No se eliminan automaticamente: se documentan aqui y el dashboard "
            "(Fase 4) debe decidir explicitamente si deduplicar quedandose con la version mas "
            "reciente por fecha de publicacion."
        ),
    }
    (PROCESSED_DIR / "quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
