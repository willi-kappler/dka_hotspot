"""Generate the synthetic PLZ-5 patient extract."""

import argparse
import csv
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from services.deprivation import score_for  # noqa: E402
from services.epidemiology import (  # noqa: E402
    MILD_BICARBONATE,
    MILD_PH,
    MODERATE_BICARBONATE,
    MODERATE_PH,
    SEVERE_BICARBONATE,
    SEVERE_PH,
    severity,
)
from services.geography import plz5_kreis  # noqa: E402

DATA = PROJECT_ROOT / "src" / "data"
REFERENCE_FILE = DATA / "plz5_reference_pilot_region.csv"
OUTPUT_FILE = DATA / "dka_synthetic_patients_plz5.csv"

FIELDS = (
    "pseudo_id", "center", "sex", "age_at_onset", "date_of_onset", "zip_code",
    "migration_background", "new_onset", "symptom_duration_days", "referral_pathway",
    "ph_venous", "bicarbonate_mmol_l", "hba1c_percent", "hba1c_mmol_mol",
    "glucose_mg_dl", "dka", "dka_severity",
)

YEARS = range(2014, 2026)
FIRST_PSEUDO_ID = 10001

GISD_CENTRE = 0.40

DKA_BASE = 0.50
DKA_PER_GISD = 0.10
SEVERE_BASE = 0.30
SEVERE_PER_GISD = 0.10
HOTSPOT_BONUS = 0.06
PANDEMIC_FACTOR = 1.20

P_MISSING_PH = 0.0
P_MISSING_BICARBONATE = 0.0
P_MISSING_HBA1C = 0.0
P_MISSING_GLUCOSE = 0.0
P_MISSING_DURATION = 0.0

# Keep generated values clear of grade thresholds.
MARGIN_PH = 0.02
MARGIN_BICARBONATE = 0.4

GRADE_NAMES = {
    "Severe": "severe", "Moderate": "moderate", "Mild": "mild",
    "No DKA": "none", "Unknown": "none",
}


def load_reference() -> list[dict]:
    with REFERENCE_FILE.open(encoding="utf-8-sig", newline="") as file:
        rows = []
        for row in csv.DictReader(file):
            postcode = row["zip_code"].strip()
            ags = plz5_kreis(postcode)
            if not ags:
                continue
            rows.append({
                "plz5": postcode,
                "kreis_ags": ags,
                "children": max(1, int(row["children_u18_synthetic"])),
                "hotspot": row.get("is_planted_hotspot", "").strip() == "yes",
            })
    return rows


def grade(ph: float | None, bicarbonate: float | None) -> str:
    """Return the extract label for the computed ISPAD grade."""
    return GRADE_NAMES[severity({"ph": ph, "bicarbonate": bicarbonate})]


def laboratory(rng: random.Random, target: str) -> tuple[float, float]:
    """Draw pH and bicarbonate for a target grade."""
    if target == "severe":
        return (
            rng.uniform(SEVERE_PH - 0.25, SEVERE_PH - 0.04),
            rng.uniform(2.0, SEVERE_BICARBONATE - MARGIN_BICARBONATE),
        )
    if target == "moderate":
        return (
            rng.uniform(SEVERE_PH + MARGIN_PH, MODERATE_PH - MARGIN_PH),
            rng.uniform(
                SEVERE_BICARBONATE + MARGIN_BICARBONATE,
                MODERATE_BICARBONATE - 0.6,
            ),
        )
    if target == "mild":
        return (
            rng.uniform(MODERATE_PH + MARGIN_PH, MILD_PH - MARGIN_PH),
            rng.uniform(
                MODERATE_BICARBONATE + MARGIN_BICARBONATE,
                MILD_BICARBONATE - 0.6,
            ),
        )
    return (
        rng.uniform(MILD_PH + 0.03, MILD_PH + 0.12),
        rng.uniform(MILD_BICARBONATE + 1.0, MILD_BICARBONATE + 9.0),
    )


def generate(seed: int, count: int) -> list[dict]:
    rng = random.Random(seed)
    reference = load_reference()
    # Weight cases by the child population.
    weights = [entry["children"] for entry in reference]

    records = []
    for index in range(count):
        area = rng.choices(reference, weights=weights, k=1)[0]
        year = rng.choice(list(YEARS))
        month = rng.randint(1, 12)
        plz5 = area["plz5"]

        gisd = score_for(plz5, year) or GISD_CENTRE
        excess = (gisd - GISD_CENTRE) * 10
        hotspot = HOTSPOT_BONUS if area["hotspot"] else 0.0
        pandemic = PANDEMIC_FACTOR if year in (2020, 2021) else 1.0

        age = round(rng.uniform(0.6, 17.9), 1)

        # Younger children have a slightly higher DKA probability.
        p_dka = (DKA_BASE + DKA_PER_GISD * excess + hotspot
                 - 0.012 * (age - 9.0)) * pandemic
        in_dka = rng.random() < min(0.85, max(0.15, p_dka))

        if in_dka:
            p_severe = min(0.60, max(0.10,
                                     SEVERE_BASE + SEVERE_PER_GISD * excess + hotspot))
            roll = rng.random()
            target = "severe" if roll < p_severe else (
                "moderate" if roll < p_severe + 0.32 else "mild"
            )
        else:
            target = "none"

        ph, bicarbonate = laboratory(rng, target)

        # Keep at least one grading value.
        shown_ph: float | None = round(ph, 2)
        shown_bicarbonate: float | None = round(bicarbonate, 1)
        roll = rng.random()
        if roll < P_MISSING_PH:
            shown_ph = None
        elif roll < P_MISSING_PH + P_MISSING_BICARBONATE:
            shown_bicarbonate = None

        severity = grade(shown_ph, shown_bicarbonate)

        hba1c = None if rng.random() < P_MISSING_HBA1C else round(
            rng.uniform(9.0, 15.5) + (1.2 if in_dka else 0.0), 1
        )
        glucose = None if rng.random() < P_MISSING_GLUCOSE else rng.randint(
            260 if in_dka else 200, 720 if in_dka else 480
        )
        duration = None if rng.random() < P_MISSING_DURATION else max(
            1, int(rng.gauss(7 + 4.0 * excess + 3.0 * in_dka, 3.5))
        )

        if severity == "severe":
            pathway = rng.choices(
                ["emergency_self", "pediatrician", "other", "unknown"],
                weights=[62, 22, 9, 7],
            )[0]
        elif severity in ("moderate", "mild"):
            pathway = rng.choices(
                ["emergency_self", "pediatrician", "other", "unknown"],
                weights=[48, 36, 8, 8],
            )[0]
        else:
            pathway = rng.choices(
                ["emergency_self", "pediatrician", "other", "unknown"],
                weights=[28, 54, 8, 10],
            )[0]

        records.append({
            "pseudo_id": FIRST_PSEUDO_ID + index,
            "center": "RT" if area["kreis_ags"] == "08415" else "TUE",
            "sex": rng.choice(["m", "f"]),
            "age_at_onset": age,
            "date_of_onset": f"{year}-{month:02d}",
            "zip_code": plz5,
            "migration_background": rng.choices(
                ["no", "yes"],
                weights=[74 - 8 * excess, 26 + 8 * excess],
            )[0],
            "new_onset": "yes",
            "symptom_duration_days": "" if duration is None else f"{duration}.0",
            "referral_pathway": pathway,
            "ph_venous": "" if shown_ph is None else f"{shown_ph:.2f}",
            "bicarbonate_mmol_l": "" if shown_bicarbonate is None
            else f"{shown_bicarbonate:.1f}",
            "hba1c_percent": "" if hba1c is None else f"{hba1c:.1f}",
            "hba1c_mmol_mol": "" if hba1c is None
            else f"{round((hba1c - 2.15) * 10.929):.1f}",
            "glucose_mg_dl": "" if glucose is None else f"{glucose}.0",
            "dka": "yes" if severity != "none" else "no",
            "dka_severity": severity if severity != "none" else "none",
        })

    records.sort(key=lambda row: row["date_of_onset"])
    for index, record in enumerate(records):
        record["pseudo_id"] = FIRST_PSEUDO_ID + index
    return records


def summarise(records: list[dict]) -> None:
    total = len(records)
    severity = Counter(row["dka_severity"] for row in records)
    dka = sum(1 for row in records if row["dka"] == "yes")
    severe = severity["severe"]
    print(f"\n{total} manifestations, {len(set(r['zip_code'] for r in records))} postcodes")
    print(f"  DKA at manifestation : {dka} ({dka / total:.1%})  "
          f"[concept: above 50% in this catchment]")
    print(f"  severe               : {severe} ({severe / total:.1%} of all, "
          f"{severe / dka:.1%} of DKA)")
    print(f"  grades               : {dict(severity)}")
    print(f"  centres              : {dict(Counter(r['center'] for r in records))}")
    needed = 60
    verdict = "fits" if severe >= needed else "STILL TOO FEW"
    print(f"  severity_model needs {needed} severe events -> {severe} ({verdict})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--n", type=int, default=500, help="number of manifestations")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    arguments = parser.parse_args()

    records = generate(arguments.seed, arguments.n)

    if arguments.output.exists():
        backup = arguments.output.with_suffix(".previous.csv")
        shutil.copy(arguments.output, backup)
        print(f"Previous extract kept at {backup}")

    with arguments.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {arguments.output}")
    summarise(records)
    print("\nSYNTHETIC DATA. Reload it with:")
    print("  python3 scripts/import_plz5_dataset.py "
          f"{arguments.output} --replace --derive-onsets "
          "--confirm-complete-cohort")


if __name__ == "__main__":
    main()
