import csv
import io
from pathlib import Path

from db import get_connection, init_db

REQUIRED_COLUMNS = {
    "age at onset", "sex", "zipcode", "state",
    "month of onset", "year of onset", "a1c",
    "glucose", "bikarb", "ph", "duration of symptoms",
}
OPTIONAL_COLUMNS = {"a1c", "duration of symptoms"}
REQUIRED_VALUE_COLUMNS = REQUIRED_COLUMNS - OPTIONAL_COLUMNS

HEADER_ALIASES = {
    "zip code": "zipcode",
    "postal code": "zipcode",
    "bicarbonate": "bikarb",
    "hba1c": "a1c",
}

DB_TO_APP_COLUMNS = {
    "id": "id",
    "age_at_onset": "age at onset",
    "sex": "sex",
    "zipcode": "zipcode",
    "state": "state",
    "month_of_onset": "month of onset",
    "year_of_onset": "year of onset",
    "a1c": "a1c",
    "glucose": "glucose",
    "bikarb": "bikarb",
    "ph": "ph",
    "duration_of_symptoms": "duration of symptoms",
    "lat": "lat",
    "lon": "lon",
    "created_at": "created_at",
}


def normalize_header(header: str) -> str:
    cleaned = header.strip().lower().replace("_", " ").replace("-", " ")
    cleaned = " ".join(cleaned.split())
    return HEADER_ALIASES.get(cleaned, cleaned)


def db_row_to_patient(row) -> dict:
    return {app_key: row[db_key] for db_key, app_key in DB_TO_APP_COLUMNS.items()}


def optional_value(value):
    return None if value is None or value == "" else value


def validate_patient_rows(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        missing_values = [
            column for column in sorted(REQUIRED_VALUE_COLUMNS)
            if row.get(column) is None or str(row.get(column)).strip() == ""
        ]
        if missing_values:
            errors.append(f"row {row_number}: missing {', '.join(missing_values)}")
    return errors


def patient_to_db_values(patient: dict) -> tuple:
    return (
        int(patient["age at onset"]),
        patient["sex"],
        str(patient["zipcode"]).strip(),
        str(patient["state"]).strip(),
        int(patient["month of onset"]),
        int(patient["year of onset"]),
        float(patient["a1c"]) if optional_value(patient.get("a1c")) is not None else None,
        int(patient["glucose"]),
        float(patient["bikarb"]),
        float(patient["ph"]),
        int(patient["duration of symptoms"]) if optional_value(patient.get("duration of symptoms")) is not None else None,
        float(patient["lat"]),
        float(patient["lon"]),
    )


SELECT_PATIENTS = """
    SELECT id, age_at_onset, sex, zipcode, state, month_of_onset,
           year_of_onset, a1c, glucose, bikarb, ph,
           duration_of_symptoms, lat, lon, created_at
    FROM patients
"""


def load_patient_rows() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(SELECT_PATIENTS + " ORDER BY id").fetchall()
    return [db_row_to_patient(row) for row in rows]


def get_patient(case_id: int) -> dict | None:
    init_db()
    with get_connection() as conn:
        row = conn.execute(SELECT_PATIENTS + " WHERE id = ?", (case_id,)).fetchone()
    return db_row_to_patient(row) if row else None


def update_patient(case_id: int, patient: dict) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE patients SET
                age_at_onset = ?, sex = ?, zipcode = ?, state = ?,
                month_of_onset = ?, year_of_onset = ?, a1c = ?, glucose = ?,
                bikarb = ?, ph = ?, duration_of_symptoms = ?, lat = ?, lon = ?
            WHERE id = ?
            """,
            (*patient_to_db_values(patient), case_id),
        )


def coords_by_zipcode(rows: list[dict] | None = None) -> dict[tuple[str, str], set[tuple[float, float]]]:
    """Map each (zipcode, state) to the marker coordinates already in use there."""
    rows = rows if rows is not None else load_patient_rows()
    coords: dict[tuple[str, str], set[tuple[float, float]]] = {}
    for row in rows:
        key = (
            str(row.get("zipcode", "")).strip(),
            str(row.get("state", "")).strip(),
        )
        if not key[0]:
            continue
        try:
            point = (round(float(row["lat"]), 4), round(float(row["lon"]), 4))
        except (KeyError, TypeError, ValueError):
            continue
        coords.setdefault(key, set()).add(point)
    return coords


def append_patient_rows(rows: list[dict]) -> None:
    if not rows:
        return

    init_db()
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO patients (
                age_at_onset, sex, zipcode, state, month_of_onset,
                year_of_onset, a1c, glucose, bikarb, ph,
                duration_of_symptoms, lat, lon
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [patient_to_db_values(row) for row in rows],
        )


def delete_patient(case_id: int) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM patients WHERE id = ?", (case_id,))


def clear_patient_rows() -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM patients")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'patients'")


def parse_patient_csv(csv_text: str) -> list[dict]:
    """Normalize headers and validate a patient CSV, raising ValueError on problems."""
    reader = csv.DictReader(io.StringIO(csv_text))
    reader.fieldnames = [normalize_header(name) for name in (reader.fieldnames or [])]
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    rows = list(reader)
    validation_errors = validate_patient_rows(rows)
    if validation_errors:
        raise ValueError("; ".join(validation_errors[:5]))
    return rows


def import_csv_file(csv_file: Path, replace: bool = False) -> int:
    rows = parse_patient_csv(csv_file.read_text(encoding="utf-8"))

    if replace:
        clear_patient_rows()
    append_patient_rows(rows)
    return len(rows)
