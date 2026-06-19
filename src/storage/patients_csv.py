import csv
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "dka_sample_data_50km.csv"

REQUIRED_COLUMNS = {
    "age at onset", "sex", "zipcode", "state",
    "month of onset", "year of onset", "a1c",
    "glucose", "bikarb", "ph", "duration of symptoms",
}

HEADER_ALIASES = {
    "zip code": "zipcode",
    "postal code": "zipcode",
    "bicarbonate": "bikarb",
    "hba1c": "a1c",
}


def normalize_header(header: str) -> str:
    cleaned = header.strip().lower().replace("_", " ").replace("-", " ")
    cleaned = " ".join(cleaned.split())
    return HEADER_ALIASES.get(cleaned, cleaned)


def get_fieldnames() -> list[str]:
    """Read column order from the actual CSV header."""
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


def load_patient_rows() -> list[dict]:
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def count_rows_by_zipcode(rows: list[dict] | None = None) -> dict[tuple[str, str], int]:
    rows = rows if rows is not None else load_patient_rows()
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (
            row.get("zipcode", "").strip(),
            row.get("state", "").strip(),
        )
        if key[0]:
            counts[key] = counts.get(key, 0) + 1
    return counts


def append_patient_rows(rows: list[dict]) -> None:
    fieldnames = get_fieldnames()
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writerows(rows)
