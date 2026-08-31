"""Descriptive breakdowns for analysis charts."""

from collections import Counter, defaultdict

from services.deprivation import tertile_for
from services.epidemiology import (
    SEVERITY_ORDER,
    cochran_armitage_trend,
    eligible_manifestations,
    is_dka,
    is_gradeable,
    is_severe,
    proportion_with_ci,
    risk_ratio_with_ci,
    severity,
)
from services.geography import KREISE_WITHOUT_CLINIC, kreis_name

AGE_BANDS = (("0–4", 0, 4), ("5–9", 5, 9), ("10–14", 10, 14), ("15–19", 15, 19))
TERTILE_LABELS = {1: "Lower", 2: "Middle", 3: "Higher"}


def _years(cases: list[dict]) -> tuple[int, int]:
    years = [case["year_of_onset"] for case in cases]
    return (min(years), max(years)) if years else (2014, 2025)


def _share(members: list[dict], outcome) -> dict:
    """Return a complete-case proportion and interval."""
    gradeable = [case for case in members if is_gradeable(case)]
    return {
        **proportion_with_ci(
            sum(1 for case in gradeable if outcome(case)), len(gradeable)
        ),
        "ungradeable": len(members) - len(gradeable),
    }


def _breakdown(label: str, members: list[dict], **extra) -> dict:
    """Build one chart row."""
    dka = _share(members, is_dka)
    return {
        "label": label,
        "cases": dka["total"],
        "ungradeable": dka["ungradeable"],
        "dka": dka,
        "severe": _share(members, is_severe),
        **extra,
    }


def overall(cases: list[dict]) -> dict:
    """Overall DKA share among eligible observed case records."""
    return _share(eligible_manifestations(cases), is_dka)


def severity_mix(cases: list[dict]) -> list[dict]:
    """Counts in each severity class, including manifestations without DKA."""
    counts = Counter(severity(case) for case in eligible_manifestations(cases))
    return [
        {"label": label, "count": counts[label]}
        for label in (*SEVERITY_ORDER, "No DKA", "Unknown") if counts[label]
    ]


def by_deprivation(cases: list[dict]) -> list[dict]:
    """DKA and severe-DKA share across the pilot's own deprivation tertiles."""
    cases = eligible_manifestations(cases)
    year_min, year_max = _years(cases)
    groups: dict[int, list[dict]] = defaultdict(list)
    for case in cases:
        tertile = tertile_for(case.get("plz5") or "", year_min, year_max)
        if tertile:
            groups[tertile].append(case)
    return [
        _breakdown(TERTILE_LABELS[tertile], groups[tertile], tertile=tertile)
        for tertile in (1, 2, 3) if groups.get(tertile)
    ]


def by_age_band(cases: list[dict]) -> list[dict]:
    cases = eligible_manifestations(cases)
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        age = int(float(case["age_at_onset"]))
        for label, low, high in AGE_BANDS:
            if low <= age <= high:
                groups[label].append(case)
                break
    return [
        _breakdown(label, groups[label])
        for label, _, _ in AGE_BANDS if groups.get(label)
    ]


def by_sex(cases: list[dict]) -> list[dict]:
    cases = eligible_manifestations(cases)
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        groups[case["sex"]].append(case)
    return [
        _breakdown(sex, groups[sex])
        for sex in ("Male", "Female") if groups.get(sex)
    ]


def by_year(cases: list[dict]) -> list[dict]:
    """DKA share per year among eligible observed case records."""
    cases = eligible_manifestations(cases)
    groups: dict[int, list[dict]] = defaultdict(list)
    for case in cases:
        groups[case["year_of_onset"]].append(case)
    return [
        {"year": year, **_share(members, is_dka)}
        for year, members in sorted(groups.items())
    ]


def by_kreis(cases: list[dict]) -> list[dict]:
    """DKA share per Landkreis, using only complete case records."""
    cases = eligible_manifestations(cases)
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        if case.get("kreis_ags"):
            groups[case["kreis_ags"]].append(case)
    return [
        {
            "ags": ags,
            "kreis": kreis_name(ags),
            "no_local_clinic": ags in KREISE_WITHOUT_CLINIC,
            **_share(members, is_dka),
        }
        for ags, members in sorted(groups.items())
    ]


def pandemic_comparison(cases: list[dict]) -> dict:
    """Compare fixed pre-, during-, and post-pandemic windows."""
    cases = eligible_manifestations(cases)

    def window(low: int, high: int) -> dict:
        members = [case for case in cases if low <= case["year_of_onset"] <= high]
        return {"label": f"{low}–{high}", **_share(members, is_dka)}

    before = window(2014, 2019)
    during = window(2020, 2021)
    after = window(2022, 2025)
    return {
        "before": before,
        "during": during,
        "after": after,
        "during_vs_before": risk_ratio_with_ci(
            during["successes"], during["total"],
            before["successes"], before["total"],
        ),
        "after_vs_before": risk_ratio_with_ci(
            after["successes"], after["total"],
            before["successes"], before["total"],
        ),
    }


def year_trend(cases: list[dict]) -> dict:
    annual = by_year(cases)
    return cochran_armitage_trend(
        [row["successes"] for row in annual],
        [row["total"] for row in annual],
        [float(row["year"]) for row in annual],
    )


def duration_by_deprivation(cases: list[dict]) -> list[dict]:
    """Return symptom-duration quartiles by deprivation tertile."""
    cases = eligible_manifestations(cases)
    year_min, year_max = _years(cases)
    groups: dict[int, list[float]] = defaultdict(list)
    for case in cases:
        duration = case.get("duration_of_symptoms")
        tertile = tertile_for(case.get("plz5") or "", year_min, year_max)
        if duration is not None and tertile:
            groups[tertile].append(float(duration))

    def quantile(values: list[float], fraction: float) -> float:
        ordered = sorted(values)
        if not ordered:
            return 0.0
        position = fraction * (len(ordered) - 1)
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    return [
        {
            "tertile": tertile,
            "label": TERTILE_LABELS[tertile],
            "n": len(values),
            "median": quantile(values, 0.5),
            "q1": quantile(values, 0.25),
            "q3": quantile(values, 0.75),
        }
        for tertile, values in sorted(groups.items()) if values
    ]
