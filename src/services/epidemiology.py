"""Epidemiological calculations."""

import math

from scipy import stats

# ISPAD thresholds; the worst of pH and bicarbonate determines severity.
SEVERE_PH, SEVERE_BICARBONATE = 7.1, 5.0
MODERATE_PH, MODERATE_BICARBONATE = 7.2, 10.0
MILD_PH, MILD_BICARBONATE = 7.3, 18.0

SEVERITY_ORDER = ("Severe", "Moderate", "Mild")
NO_DKA = "No DKA"
UNKNOWN = "Unknown"

Z_95 = 1.959963984540054  #stats constant for 95% confidence intervals


def severity(case: dict) -> str:
    """Classify a case from pH and bicarbonate."""
    values = []
    for key in ("ph", "bicarbonate"):
        try:
            value = case.get(key)
            parsed = None if value is None else float(value)
            values.append(parsed if parsed is None or math.isfinite(parsed) else None)
        except (TypeError, ValueError):
            values.append(None)
    ph, bicarbonate = values
    if ph is None and bicarbonate is None:
        return UNKNOWN

    def below(value, threshold):
        return value is not None and value < threshold

    if below(ph, SEVERE_PH) or below(bicarbonate, SEVERE_BICARBONATE):
        return "Severe"
    if below(ph, MODERATE_PH) or below(bicarbonate, MODERATE_BICARBONATE):
        return "Moderate"
    if below(ph, MILD_PH) or below(bicarbonate, MILD_BICARBONATE):
        return "Mild"
    if ph is None or bicarbonate is None:
        return UNKNOWN
    return NO_DKA


def is_dka(case: dict) -> bool:
    return severity(case) in SEVERITY_ORDER


def is_severe(case: dict) -> bool:
    return severity(case) == "Severe"


def is_gradeable(case: dict) -> bool:
    """Return whether the case can be classified."""
    return severity(case) != UNKNOWN


def split_manifestations(cases: list[dict]) -> dict[str, list[dict]]:
    """Split cases by new-onset status."""
    groups = {"eligible": [], "not_new_onset": [], "unknown_new_onset": []}
    for case in cases:
        value = case.get("new_onset")
        if value in (1, True):
            groups["eligible"].append(case)
        elif value in (0, False):
            groups["not_new_onset"].append(case)
        else:
            groups["unknown_new_onset"].append(case)
    return groups


def eligible_manifestations(cases: list[dict]) -> list[dict]:
    """Confirmed new-onset records only."""
    return split_manifestations(cases)["eligible"]


# Warn when an extract may contain only DKA cases.
MIN_NON_DKA_SHARE = 0.10


def frame_check(cases: list[dict]) -> dict:
    """Check whether the DKA share suggests a selected extract."""
    gradeable = [case for case in cases if is_gradeable(case)]
    non_dka = sum(1 for case in gradeable if not is_dka(case))
    share = non_dka / len(gradeable) if gradeable else 0.0
    return {
        "n": len(gradeable),
        "non_dka": non_dka,
        "share": share,
        "suspicious": not gradeable or share < MIN_NON_DKA_SHARE,
    }


def wilson_interval(successes: int, total: int, z: float = Z_95) -> tuple[float, float]:
    """Return a Wilson score interval."""
    if total <= 0:
        return float("nan"), float("nan")
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z**2 / (4 * total**2)
    ) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def proportion(successes: int, total: int) -> float | None:
    """DKA share of manifestations, or None when there is no denominator."""
    return successes / total if total > 0 else None


def proportion_with_ci(successes: int, total: int) -> dict:
    if total <= 0:
        return {
            "successes": successes, "total": total,
            "proportion": None, "ci_low": None, "ci_high": None,
        }
    low, high = wilson_interval(successes, total)
    return {
        "successes": successes,
        "total": total,
        "proportion": successes / total,
        "ci_low": low,
        "ci_high": high,
    }


def risk_ratio_with_ci(  #pandemic period vs pre-pandemic period
    successes_a: int, total_a: int,
    successes_b: int, total_b: int,
) -> dict:
    """Return a risk ratio with confidence interval."""
    not_estimable = {"ratio": None, "ci_low": None, "ci_high": None, "p_value": None}
    if min(total_a, total_b) <= 0 or successes_a <= 0 or successes_b <= 0:
        return not_estimable
    risk_a = successes_a / total_a
    risk_b = successes_b / total_b
    ratio = risk_a / risk_b
    standard_error = math.sqrt(
        (1 - risk_a) / successes_a + (1 - risk_b) / successes_b
    )
    if standard_error == 0:
        return not_estimable
    log_ratio = math.log(ratio)
    return {
        "ratio": ratio,
        "ci_low": math.exp(log_ratio - Z_95 * standard_error),
        "ci_high": math.exp(log_ratio + Z_95 * standard_error),
        "p_value": 2 * stats.norm.sf(abs(log_ratio / standard_error)),
    }


def cochran_armitage_trend(successes: list[int], totals: list[int], scores: list[float]) -> dict:
    """Run a Cochran-Armitage trend test."""
    pairs = [
        (s, n, x) for s, n, x in zip(successes, totals, scores) if n > 0
    ]
    if len(pairs) < 3:
        return {"statistic": None, "p_value": None, "n_groups": len(pairs)}

    total_n = sum(n for _, n, _ in pairs)
    total_s = sum(s for s, _, _ in pairs)
    if total_s in (0, total_n):
        return {"statistic": None, "p_value": None, "n_groups": len(pairs)}

    overall = total_s / total_n
    mean_score = sum(n * x for _, n, x in pairs) / total_n
    numerator = sum(s * (x - mean_score) for s, _, x in pairs)
    variance = overall * (1 - overall) * sum(
        n * (x - mean_score) ** 2 for _, n, x in pairs
    )
    if variance <= 0:
        return {"statistic": None, "p_value": None, "n_groups": len(pairs)}
    z = numerator / math.sqrt(variance)
    return {
        "statistic": z,
        "p_value": 2 * stats.norm.sf(abs(z)),
        "n_groups": len(pairs),
    }
