"""Patient-level case storage and CSV import."""

import csv
import io
from pathlib import Path

from db import get_connection, init_db
from services.epidemiology import severity
from services.geography import (
    is_pilot_kreis,
    is_pilot_plz5,
    normalise_plz5,
    plz5_kreis,
)

FIELDS = (
    "pseudonym", "clinic", "age_at_onset", "sex", "migration_background",
    "plz5", "kreis_ags", "month_of_onset", "year_of_onset", "new_onset",
    "referral_pathway", "ph", "bicarbonate", "hba1c", "glucose",
    "duration_of_symptoms", "dka_reported", "dka_severity_reported",
)

REQUIRED = ("clinic", "age_at_onset", "sex", "new_onset")

HEADER_ALIASES = {
    "pseudo id": "pseudonym",
    "center": "clinic", "centre": "clinic",
    "zip code": "plz5", "zipcode": "plz5",
    "symptom duration days": "duration_of_symptoms",
    "ph venous": "ph",
    "bicarbonate mmol l": "bicarbonate",
    "hba1c percent": "hba1c",
    "glucose mg dl": "glucose",
    "dka": "dka_reported",
    "dka severity": "dka_severity_reported",
    "age": "age_at_onset", "age at onset": "age_at_onset",
    "alter": "age_at_onset", "geschlecht": "sex",
    "bikarb": "bicarbonate", "bikarbonat": "bicarbonate",
    "a1c": "hba1c", "hba1c wert": "hba1c",
    "plz": "plz5", "postleitzahl": "plz5",
    "landkreis": "kreis_ags", "kreis": "kreis_ags", "ags": "kreis_ags",
    "migrationshintergrund": "migration_background",
    "manifestationsjahr": "year_of_onset",
    "manifestationsmonat": "month_of_onset",
    "duration of symptoms": "duration_of_symptoms",
    "symptomdauer": "duration_of_symptoms",
}

IGNORED_COLUMNS = {"hba1c_mmol_mol"}

SEX_VALUES = {
    "m": "Male", "male": "Male", "männlich": "Male", "maennlich": "Male",
    "f": "Female", "w": "Female", "female": "Female", "weiblich": "Female",
}

TRUE_VALUES = {"1", "true", "yes", "ja", "y", "j"}
FALSE_VALUES = {"0", "false", "no", "nein", "n"}

_SELECT = f"SELECT id, {', '.join(FIELDS)}, created_at FROM cases"


def normalise_header(header: str) -> str:
    cleaned = " ".join(header.strip().lower().replace("_", " ").replace("-", " ").split())
    return HEADER_ALIASES.get(cleaned, cleaned.replace(" ", "_"))


def _optional(value):
    if value is None:
        return None
    text = str(value).strip()
    return None if text == "" else text


def _flag(value) -> int | None:
    text = _optional(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in TRUE_VALUES:
        return 1
    if lowered in FALSE_VALUES:
        return 0
    return None


def _onset_month_year(case: dict) -> tuple[int, int]:
    """Month and year of onset, from ``YYYY-MM`` or two separate columns."""
    date = _optional(case.get("date_of_onset"))
    if date:
        parts = date.replace("/", "-").split("-")
        if len(parts) >= 2 and len(parts[0]) == 4:
            return int(parts[1]), int(parts[0])
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
        raise ValueError(f"Cannot read a month and year from date {date!r}")

    month, year = _optional(case.get("month_of_onset")), _optional(case.get("year_of_onset"))
    if month is None or year is None:
        raise ValueError("Needs date_of_onset, or month_of_onset and year_of_onset")
    return int(float(month)), int(float(year))


def _to_row(case: dict) -> tuple:
    plz5 = normalise_plz5(case.get("plz5") or "")
    if plz5 and not is_pilot_plz5(plz5):
        raise ValueError(
            f"Postcode {plz5} is outside the pilot region "
            "(Tübingen, Reutlingen, Zollernalbkreis)."
        )

    kreis = _optional(case.get("kreis_ags"))
    kreis = str(kreis).zfill(5) if kreis else None
    if kreis is None and plz5:
        kreis = plz5_kreis(plz5) or None
    if kreis and not is_pilot_kreis(kreis):
        raise ValueError(
            f"Kreis {kreis} is outside the pilot region "
            "(Tübingen, Reutlingen, Zollernalbkreis)."
        )

    def number(key, cast):
        value = _optional(case.get(key))
        return None if value is None else cast(float(value))

    month, year = _onset_month_year(case)

    sex = SEX_VALUES.get(str(case["sex"]).strip().lower())
    if sex is None:
        raise ValueError(f"Unrecognised sex {case['sex']!r}")

    migration = (_optional(case.get("migration_background")) or "Unknown").capitalize()
    if migration not in ("Yes", "No", "Unknown"):
        migration = "Unknown"

    referral = _optional(case.get("referral_pathway"))

    return (
        _optional(case.get("pseudonym")),
        str(case["clinic"]).strip().upper(),
        float(case["age_at_onset"]),
        sex,
        migration,
        plz5 or None,
        kreis,
        month,
        year,
        _flag(case.get("new_onset")),
        referral.capitalize() if referral else None,
        number("ph", float),
        number("bicarbonate", float),
        number("hba1c", float),
        number("glucose", int),
        number("duration_of_symptoms", int),
        _flag(case.get("dka_reported")),
        _optional(case.get("dka_severity_reported")),
    )


def load_cases() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(f"{_SELECT} ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def add_cases(cases: list[dict]) -> int:
    if not cases:
        return 0
    init_db()
    placeholders = ", ".join("?" for _ in FIELDS)
    with get_connection() as conn:
        conn.executemany(
            f"INSERT INTO cases ({', '.join(FIELDS)}) VALUES ({placeholders})",
            [_to_row(case) for case in cases],
        )
    return len(cases)


def validate(rows: list[dict]) -> list[str]:
    errors = []
    for number, row in enumerate(rows, start=2):
        missing = [field for field in REQUIRED if not _optional(row.get(field))]
        if missing:
            errors.append(f"row {number}: missing {', '.join(missing)}")
            continue
        try:
            age = float(row["age_at_onset"])
        except (TypeError, ValueError):
            errors.append(f"row {number}: age must be a number")
            continue
        if not 0 <= age < 20:
            errors.append(f"row {number}: age {age} outside 0–19")
        if str(row["sex"]).strip().lower() not in SEX_VALUES:
            errors.append(f"row {number}: unrecognised sex {row['sex']!r}")
        if _flag(row.get("new_onset")) is None:
            errors.append(f"row {number}: new_onset must be yes or no")
        try:
            _onset_month_year(row)
        except (TypeError, ValueError) as error:
            errors.append(f"row {number}: {error}")
        plz5 = normalise_plz5(row.get("plz5") or "")
        if not plz5 and not _optional(row.get("kreis_ags")):
            errors.append(f"row {number}: needs a postcode or a Landkreis")
        elif plz5 and not is_pilot_plz5(plz5):
            errors.append(f"row {number}: postcode {plz5} is outside the pilot region")
    return errors


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [normalise_header(name) for name in (reader.fieldnames or [])]
    rows = [
        {key: value for key, value in row.items() if key not in IGNORED_COLUMNS}
        for row in reader
    ]
    errors = validate(rows)
    if errors:
        raise ValueError("; ".join(errors[:5]))
    return rows


def import_csv_file(path: Path, replace: bool = False) -> int:
    rows = parse_csv(Path(path).read_text(encoding="utf-8"))
    init_db()
    if replace:
        with get_connection() as conn:
            conn.execute("DELETE FROM cases")
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'cases'")
    return add_cases(rows)


def classification_disagreements() -> list[dict]:
    """Return clinic grades that differ from the recomputed grade."""
    mapping = {"none": "No DKA", "mild": "Mild", "moderate": "Moderate", "severe": "Severe"}
    rows = []
    for case in load_cases():
        reported = case.get("dka_severity_reported")
        if not reported:
            continue
        expected = mapping.get(str(reported).strip().lower())
        derived = severity(case)
        if expected and derived != expected:
            rows.append({
                "id": case["id"],
                "pseudonym": case.get("pseudonym") or "—",
                "reported": expected,
                "derived": derived,
                "ph": case.get("ph"),
                "bicarbonate": case.get("bicarbonate"),
            })
    return rows
