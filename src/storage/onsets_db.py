"""Aggregate manifestation counts by clinic, year, and district."""

import csv
import io
from pathlib import Path

from db import get_connection, init_db
from services.geography import is_pilot_kreis

FIELDS = ("clinic", "year", "kreis_ags", "manifestations", "dka_cases")

HEADER_ALIASES = {
    "klinik": "clinic", "ambulanz": "clinic",
    "jahr": "year", "manifestationsjahr": "year",
    "landkreis": "kreis_ags", "kreis": "kreis_ags", "ags": "kreis_ags",
    "manifestationen": "manifestations", "neumanifestationen": "manifestations",
    "total": "manifestations", "new onsets": "manifestations",
    "dka": "dka_cases", "ketoazidosen": "dka_cases", "dka cases": "dka_cases",
}


def normalise_header(header: str) -> str:
    cleaned = " ".join(header.strip().lower().replace("_", " ").replace("-", " ").split())
    return HEADER_ALIASES.get(cleaned, cleaned.replace(" ", "_"))


def _to_row(entry: dict) -> tuple:
    kreis = str(entry["kreis_ags"]).strip().zfill(5)
    if not is_pilot_kreis(kreis):
        raise ValueError(f"Kreis {kreis} is outside the pilot region.")
    dka = entry.get("dka_cases")
    dka = None if dka is None or str(dka).strip() == "" else int(dka)
    manifestations = int(entry["manifestations"])
    if dka is not None and dka > manifestations:
        raise ValueError(
            f"{entry['clinic']} {entry['year']} {kreis}: "
            f"{dka} DKA cases exceeds {manifestations} manifestations."
        )
    return (
        str(entry["clinic"]).strip().upper(),
        int(entry["year"]),
        kreis,
        manifestations,
        dka,
    )


def load_onsets() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT id, {', '.join(FIELDS)} FROM onsets ORDER BY year, clinic, kreis_ags"
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_onsets(entries: list[dict]) -> int:
    """Insert or replace denominator rows, keyed on clinic-year-Kreis."""
    if not entries:
        return 0
    init_db()
    with get_connection() as conn:
        conn.executemany(
            f"""
            INSERT INTO onsets ({', '.join(FIELDS)})
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (clinic, year, kreis_ags) DO UPDATE SET
                manifestations = excluded.manifestations,
                dka_cases = excluded.dka_cases
            """,
            [_to_row(entry) for entry in entries],
        )
    return len(entries)


def has_denominator() -> bool:
    """Whether any denominator data has arrived yet."""
    init_db()
    with get_connection() as conn:
        return conn.execute("SELECT 1 FROM onsets LIMIT 1").fetchone() is not None


def reporting_coverage() -> list[dict]:
    """Return reporting coverage by clinic and year."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT clinic, year,
                   COUNT(*) AS kreis_rows,
                   SUM(manifestations) AS manifestations,
                   SUM(dka_cases IS NULL) AS missing_dka
            FROM onsets
            GROUP BY clinic, year
            ORDER BY clinic, year
            """
        ).fetchall()
    return [dict(row) for row in rows]


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [normalise_header(name) for name in (reader.fieldnames or [])]
    rows = list(reader)
    missing = {"clinic", "year", "kreis_ags", "manifestations"} - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    return rows


def import_csv_file(path: Path) -> int:
    return upsert_onsets(parse_csv(Path(path).read_text(encoding="utf-8")))
