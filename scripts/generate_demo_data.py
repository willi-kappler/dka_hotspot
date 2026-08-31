"""Fill the database with synthetic demo data."""

import argparse
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from db import get_connection, init_db  # noqa: E402
from services.deprivation import mean_score  # noqa: E402
from services.geography import PILOT_KREISE, pilot_plz5, plz5_kreis  # noqa: E402
from storage.cases_db import add_cases  # noqa: E402
from storage.onsets_db import upsert_onsets  # noqa: E402

YEARS = range(2014, 2026)
CLINIC_BY_KREIS = {"08416": "TUE", "08415": "RT", "08417": "TUE"}

REFERRAL_PATHWAYS = ("Pediatrician", "Emergency_self", "Other", "Unknown")


def clear() -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM cases")
        conn.execute("DELETE FROM onsets")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('cases', 'onsets')")
    print("Cleared cases and onsets.")


def generate(seed: int = 7) -> None:
    rng = random.Random(seed)
    areas = [plz5 for plz5 in pilot_plz5() if mean_score(plz5, 2014, 2025) is not None]
    scores = {plz5: mean_score(plz5, 2014, 2025) for plz5 in areas}
    lowest = min(scores.values())

    by_kreis: dict[str, list[str]] = {ags: [] for ags in PILOT_KREISE}
    for plz5 in areas:
        ags = plz5_kreis(plz5)
        if ags in by_kreis:
            by_kreis[ags].append(plz5)

    cases, onsets = [], []
    for year in YEARS:
        pandemic = 1.6 if year in (2020, 2021) else 1.0
        for ags, clinic in CLINIC_BY_KREIS.items():
            local_areas = by_kreis.get(ags) or areas
            manifestations = rng.randint(18, 34)

            dka_count = 0
            for index in range(manifestations):
                plz5 = rng.choice(local_areas)
                excess = (scores[plz5] - lowest) * 4
                in_dka = rng.random() < min(0.85, (0.20 + excess * 0.22) * pandemic)
                severe = in_dka and rng.random() < 0.30 + excess * 0.30
                dka_count += in_dka

                if severe:
                    ph, bicarbonate = rng.uniform(6.85, 7.09), rng.uniform(2.0, 4.8)
                elif in_dka:
                    ph, bicarbonate = rng.uniform(7.10, 7.29), rng.uniform(5.5, 14.5)
                else:
                    ph, bicarbonate = rng.uniform(7.31, 7.42), rng.uniform(16.0, 24.0)

                cases.append({
                    "pseudonym": f"D{year}{ags[-3:]}{index:03d}",
                    "clinic": clinic,
                    "age_at_onset": round(rng.uniform(0.5, 19.4), 1),
                    "sex": rng.choice(["m", "f"]),
                    "migration_background": rng.choice(["Yes", "No", "No", "Unknown"]),
                    "plz5": plz5,
                    "kreis_ags": ags,
                    "month_of_onset": rng.randint(1, 12),
                    "year_of_onset": year,
                    "new_onset": 1,
                    "referral_pathway": rng.choice(REFERRAL_PATHWAYS),
                    "ph": round(ph, 2),
                    "bicarbonate": round(bicarbonate, 1),
                    "hba1c": round(rng.uniform(9.5, 15.5), 1),
                    "glucose": rng.randint(250, 700),
                    "duration_of_symptoms": max(
                        1, int(rng.gauss(6 + excess * 6 + 4 * in_dka, 3))
                    ),
                })

            onsets.append({
                "clinic": clinic, "year": year, "kreis_ags": ags,
                "manifestations": manifestations, "dka_cases": dka_count,
            })

    upsert_onsets(onsets)
    add_cases(cases)
    print(f"Inserted {len(onsets)} denominator rows and {len(cases)} synthetic "
          f"cases across {len(areas)} postcode areas.")
    print("SYNTHETIC DATA — clear before loading anything real.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clear", action="store_true", help="wipe both tables and exit")
    parser.add_argument("--seed", type=int, default=7)
    arguments = parser.parse_args()
    init_db()
    if arguments.clear:
        clear()
    else:
        clear()
        generate(arguments.seed)
