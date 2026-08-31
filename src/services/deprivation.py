"""GISD deprivation scores at PLZ-5 level."""

import csv
from functools import lru_cache
from pathlib import Path

from services.geography import pilot_plz5

GISD_FILE = (
    Path(__file__).resolve().parent.parent
    / "data" / "GISD_PLZ5_Baden-Wuerttemberg.tsv"
)
GISD_MIN_YEAR = 1998
GISD_MAX_YEAR = 2023

TERTILE_LABELS = {1: "Lower deprivation", 2: "Middle", 3: "Higher deprivation"}


@lru_cache(maxsize=1)
def _plz5_scores() -> dict[tuple[str, int], float]:
    """GISD score keyed by (postcode, year), restricted to the pilot region."""
    wanted = set(pilot_plz5())
    scores: dict[tuple[str, int], float] = {}
    with GISD_FILE.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file, delimiter="\t"):
            postcode = str(row["region_id"]).strip().zfill(5)
            if postcode not in wanted:
                continue
            try:
                scores[(postcode, int(row["year"]))] = float(row["gisd_score"])
            except (TypeError, ValueError):
                continue
    return scores


def observation_year(year: int) -> int:
    """Clamp a study year to the available GISD range."""
    return min(max(int(year), GISD_MIN_YEAR), GISD_MAX_YEAR)


def score_for(plz5: str, year: int) -> float | None:
    """Year-matched GISD score for a postcode."""
    if not plz5:
        return None
    return _plz5_scores().get((str(plz5).zfill(5), observation_year(year)))


def is_carried_forward(year: int) -> bool:
    return int(year) > GISD_MAX_YEAR


@lru_cache(maxsize=4096)
def mean_score(plz5: str, year_min: int, year_max: int) -> float | None:
    """Mean GISD score for a postcode across a study period."""
    values = [
        score for score in (
            score_for(plz5, year) for year in range(year_min, year_max + 1)
        ) if score is not None
    ]
    return sum(values) / len(values) if values else None


@lru_cache(maxsize=64)
def regional_tertile_cuts(year_min: int, year_max: int) -> tuple[float, float]:
    """Return unweighted tertile cuts for pilot postcodes."""
    means = [
        mean for mean in (
            mean_score(plz5, year_min, year_max) for plz5 in pilot_plz5()
        ) if mean is not None
    ]
    if len(means) < 3:
        return float("nan"), float("nan")
    means.sort()
    first = means[len(means) // 3]
    second = means[2 * len(means) // 3]
    return first, second


def tertile_for(plz5: str, year_min: int, year_max: int) -> int | None:
    """Local deprivation tertile, 1 = least deprived within the pilot region."""
    mean = mean_score(plz5, year_min, year_max)
    if mean is None:
        return None
    first, second = regional_tertile_cuts(year_min, year_max)
    if first != first:  # NaN guard
        return None
    if mean < first:
        return 1
    return 2 if mean < second else 3


def coverage() -> dict:
    """Return GISD coverage for pilot postcodes."""
    areas = pilot_plz5()
    resolved = [plz5 for plz5 in areas if mean_score(plz5, GISD_MIN_YEAR, GISD_MAX_YEAR)]
    return {
        "areas": len(areas),
        "resolved": len(resolved),
        "missing": sorted(set(areas) - set(resolved)),
    }


def attach_to_cases(cases: list[dict]) -> list[dict]:
    """Add the year-matched deprivation score to each case."""
    enriched = []
    for case in cases:
        score = score_for(case.get("plz5", ""), case.get("year_of_onset", 0))
        enriched.append({
            **case,
            "gisd_score": score,
            "gisd_carried_forward": is_carried_forward(case.get("year_of_onset", 0)),
        })
    return enriched
