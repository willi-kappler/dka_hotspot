"""DKA share among new type 1 manifestations."""

from collections import defaultdict

from services.epidemiology import (
    cochran_armitage_trend,
    eligible_manifestations,
    is_dka,
    is_gradeable,
    proportion_with_ci,
    risk_ratio_with_ci,
)
from services.geography import KREISE_WITHOUT_CLINIC, PILOT_KREISE, kreis_name

# Minimum denominator for reporting a district share.
MIN_DENOMINATOR = 20


def from_cases(cases: list[dict]) -> list[dict]:
    """Aggregate case records by clinic, year, and district."""
    grouped: dict[tuple[str, int, str], list[int]] = defaultdict(lambda: [0, 0])
    for case in eligible_manifestations(cases):
        kreis = case.get("kreis_ags")
        if not kreis or not is_gradeable(case):
            continue
        key = (case["clinic"], case["year_of_onset"], kreis)
        grouped[key][0] += 1
        grouped[key][1] += 1 if is_dka(case) else 0
    return [
        {
            "clinic": clinic, "year": year, "kreis_ags": kreis,
            "manifestations": manifestations, "dka_cases": dka,
        }
        for (clinic, year, kreis), (manifestations, dka) in sorted(grouped.items())
    ]


def _filtered(onsets: list[dict], year_min: int, year_max: int,
              clinics: set[str] | None = None) -> list[dict]:
    return [
        row for row in onsets
        if year_min <= row["year"] <= year_max
        and (clinics is None or row["clinic"] in clinics)
        and row["dka_cases"] is not None
    ]


def overall(onsets: list[dict], year_min: int, year_max: int,
            clinics: set[str] | None = None) -> dict:
    """Return the pooled proportion for a selection."""
    rows = _filtered(onsets, year_min, year_max, clinics)
    dka = sum(row["dka_cases"] for row in rows)
    total = sum(row["manifestations"] for row in rows)
    return proportion_with_ci(dka, total)


def by_year(onsets: list[dict], year_min: int, year_max: int,
            clinics: set[str] | None = None) -> list[dict]:
    rows = _filtered(onsets, year_min, year_max, clinics)
    grouped: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        grouped[row["year"]][0] += row["dka_cases"]
        grouped[row["year"]][1] += row["manifestations"]
    return [
        {"year": year, **proportion_with_ci(dka, total)}
        for year, (dka, total) in sorted(grouped.items())
    ]


def by_kreis(onsets: list[dict], year_min: int, year_max: int,
             clinics: set[str] | None = None) -> list[dict]:
    """Return pooled proportions by district."""
    rows = _filtered(onsets, year_min, year_max, clinics)
    grouped: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        grouped[row["kreis_ags"]][0] += row["dka_cases"]
        grouped[row["kreis_ags"]][1] += row["manifestations"]

    results = []
    for ags in PILOT_KREISE:
        dka, total = grouped.get(ags, [0, 0])
        entry = proportion_with_ci(dka, total)
        results.append({
            "ags": ags,
            "kreis": kreis_name(ags),
            **entry,
            "sufficient": total >= MIN_DENOMINATOR,
            "no_local_clinic": ags in KREISE_WITHOUT_CLINIC,
        })
    return results


def year_trend(onsets: list[dict], year_min: int, year_max: int,
               clinics: set[str] | None = None) -> dict:
    annual = by_year(onsets, year_min, year_max, clinics)
    return cochran_armitage_trend(
        [row["successes"] for row in annual],
        [row["total"] for row in annual],
        [float(row["year"]) for row in annual],
    )


def pandemic_comparison(onsets: list[dict], clinics: set[str] | None = None) -> dict:
    """Compare fixed pre-, during-, and post-pandemic windows."""
    def window(low, high):
        rows = _filtered(onsets, low, high, clinics)
        return (
            sum(row["dka_cases"] for row in rows),
            sum(row["manifestations"] for row in rows),
        )

    before_dka, before_total = window(2014, 2019)
    during_dka, during_total = window(2020, 2021)
    after_dka, after_total = window(2022, 2025)

    return {
        "before": {"label": "2014–2019", **proportion_with_ci(before_dka, before_total)},
        "during": {"label": "2020–2021", **proportion_with_ci(during_dka, during_total)},
        "after": {"label": "2022–2025", **proportion_with_ci(after_dka, after_total)},
        "during_vs_before": risk_ratio_with_ci(
            during_dka, during_total, before_dka, before_total
        ),
        "after_vs_before": risk_ratio_with_ci(
            after_dka, after_total, before_dka, before_total
        ),
    }
