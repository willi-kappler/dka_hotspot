"""Case-level regression models."""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from services.deprivation import attach_to_cases
from services.epidemiology import eligible_manifestations, is_gradeable, is_severe

# Minimum events per fitted parameter.
MIN_EVENTS_PER_PARAMETER = 10


def _frame(cases: list[dict]) -> pd.DataFrame:
    """Analysis frame with deprivation attached and covariates coded."""
    enriched = [
        {
            **case,
            "severe": 1 if is_severe(case) else 0,
            "gradeable": is_gradeable(case),
        }
        for case in attach_to_cases(eligible_manifestations(cases))
    ]
    frame = pd.DataFrame(enriched)
    if frame.empty:
        return frame

    frame = frame[frame["gisd_score"].notna()].copy()
    if frame.empty:
        return frame
    frame["gisd_10"] = frame["gisd_score"] * 10
    frame["female"] = (frame["sex"] == "Female").astype(int)
    frame["migration"] = (frame["migration_background"] == "Yes").astype(int)
    frame["migration_unknown"] = (
        frame["migration_background"] == "Unknown"
    ).astype(int)
    frame["migration_known"] = (frame["migration_background"] != "Unknown").astype(int)
    frame["age"] = pd.to_numeric(frame["age_at_onset"], errors="coerce")
    frame["year_centred"] = frame["year_of_onset"] - frame["year_of_onset"].min()
    return frame


def _terms(frame: pd.DataFrame) -> list[str]:
    """Covariates, dropping any that have no variation in this cohort."""
    candidates = ["gisd_10", "age", "female", "year_centred"]
    if frame["migration_known"].mean() > 0.5 and frame["migration"].nunique() > 1:
        candidates.extend(["migration", "migration_unknown"])
    return [term for term in candidates if frame[term].nunique() > 1]


def _fit(frame: pd.DataFrame, outcome: str, terms: list[str], family) -> dict:
    design = sm.add_constant(frame[terms], has_constant="add")
    model = sm.GLM(frame[outcome], design, family=family)
    try:
        result = model.fit(
            cov_type="cluster",
            cov_kwds={"groups": frame["plz5"].fillna("unknown")},
        )
    except Exception as error:  # singular design, separation, non-convergence
        return {"available": False, "reason": f"Model did not fit: {error}"}

    if not np.all(np.isfinite(result.bse)):
        return {
            "available": False,
            "reason": "Standard errors are not estimable — the cohort is too "
                      "sparse or a predictor separates the outcome.",
        }

    estimates = []
    for name in design.columns:
        if name == "const":
            continue
        estimates.append({
            "term": name,
            "estimate": float(np.exp(result.params[name])),
            "ci_low": float(np.exp(result.conf_int().loc[name, 0])),
            "ci_high": float(np.exp(result.conf_int().loc[name, 1])),
            "p_value": float(result.pvalues[name]),
        })
    return {
        "available": True,
        "terms": estimates,
        "n": int(frame.shape[0]),
        "clusters": int(frame["plz5"].nunique()),
        "parameters": len(design.columns),
    }


def severity_model(cases: list[dict]) -> dict:
    """Model severe DKA against deprivation and covariates."""
    frame = _frame(cases)
    if frame.empty:
        return {"available": False, "reason": "No cases with a deprivation score."}

    ungradeable = int((~frame["gradeable"]).sum())
    frame = frame[frame["gradeable"]]
    if frame.empty:
        return {"available": False, "reason": "No case can be graded from pH or bicarbonate."}
    events = int(frame["severe"].sum())
    terms = _terms(frame)
    if not terms:
        return {"available": False, "reason": "No predictor varies in this cohort."}
    if events < MIN_EVENTS_PER_PARAMETER * (len(terms) + 1):
        return {
            "available": False,
            "reason": (
                f"{events} severe cases support about {events // MIN_EVENTS_PER_PARAMETER} "
                f"parameters; this model needs {len(terms) + 1}. Reduce the "
                "covariates or wait for more data."
            ),
        }

    model = _fit(frame, "severe", terms, sm.families.Poisson())
    if model.get("available"):
        model["measure"] = "Risk ratio"
        model["events"] = events
        model["ungradeable"] = ungradeable
        model["outcome"] = "Severe DKA (pH <7.1 or bicarbonate <5 mmol/L)"
    return model


def _dispersion(frame: pd.DataFrame, terms: list[str]) -> tuple[float, bool]:
    """Estimate negative-binomial dispersion."""
    design = sm.add_constant(frame[terms], has_constant="add")
    try:
        fitted = sm.NegativeBinomial(frame["duration"], design).fit(disp=0)
        alpha = float(fitted.params["alpha"])
    except Exception:  # non-convergence, singular design
        return 1.0, False
    if not np.isfinite(alpha) or alpha <= 0:
        return 1.0, False
    return alpha, True


def duration_model(cases: list[dict]) -> dict:
    """Model symptom duration against deprivation and covariates."""
    frame = _frame(cases)
    if frame.empty:
        return {"available": False, "reason": "No cases with a deprivation score."}

    frame = frame[pd.to_numeric(frame["duration_of_symptoms"], errors="coerce").notna()].copy()
    frame["duration"] = pd.to_numeric(frame["duration_of_symptoms"])
    if frame.shape[0] < 30:
        return {
            "available": False,
            "reason": f"Only {frame.shape[0]} cases record symptom duration; "
                      "at least 30 are needed.",
        }

    terms = _terms(frame)
    if not terms:
        return {"available": False, "reason": "No predictor varies in this cohort."}

    alpha, alpha_estimated = _dispersion(frame, terms)
    model = _fit(frame, "duration", terms, sm.families.NegativeBinomial(alpha=alpha))
    if model.get("available"):
        model["measure"] = "Duration ratio"
        model["outcome"] = "Days of symptoms before diagnosis"
        model["median_duration"] = float(frame["duration"].median())
        model["alpha"] = alpha
        model["alpha_estimated"] = alpha_estimated
    return model


TERM_LABELS = {
    "gisd_10": "Deprivation (per +0.1 GISD)",
    "age": "Age at onset (per year)",
    "female": "Female vs male",
    "year_centred": "Onset year (per year)",
    "migration": "Migration background vs none",
    "migration_unknown": "Migration background unknown vs none",
}
