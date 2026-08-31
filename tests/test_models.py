
import random

import pytest
from factories import case

from services.geography import pilot_plz5
from services.models import (
    MIN_EVENTS_PER_PARAMETER,
    TERM_LABELS,
    duration_model,
    severity_model,
)

pytestmark = pytest.mark.slow

SEVERE = {"ph": 7.05, "bicarbonate": 4.0}
MILD = {"ph": 7.25, "bicarbonate": 16.0}
CLEAR = {"ph": 7.40, "bicarbonate": 24.0}


def cohort(n=400, severe_share=0.30, seed=11):
    rng = random.Random(seed)
    postcodes = list(pilot_plz5())
    records = []
    for index in range(n):
        severe = rng.random() < severe_share
        labs = SEVERE if severe else (MILD if rng.random() < 0.4 else CLEAR)
        records.append(case(
            pseudonym=f"C{index:04d}",
            plz5=rng.choice(postcodes),
            kreis_ags=None,
            age_at_onset=round(rng.uniform(1.0, 17.9), 1),
            sex=rng.choice(["Male", "Female"]),
            migration_background=rng.choice(["Yes", "No", "No"]),
            year_of_onset=rng.choice(range(2014, 2026)),
            duration_of_symptoms=max(1, int(rng.gauss(10, 4))),
            **labs,
        ))
    return records



def test_severity_model_fits_on_an_adequate_cohort():
    model = severity_model(cohort())
    assert model["available"] is True, model.get("reason")
    assert model["measure"] == "Risk ratio"
    assert model["n"] > 0
    assert model["clusters"] > 1


def test_severity_model_reports_risk_ratios_with_intervals():
    model = severity_model(cohort())
    for term in model["terms"]:
        assert term["ci_low"] <= term["estimate"] <= term["ci_high"]
        assert term["estimate"] > 0, "an exponentiated coefficient cannot be negative"
        assert 0.0 <= term["p_value"] <= 1.0


def test_every_fitted_term_has_a_human_readable_label():
    model = severity_model(cohort())
    for term in model["terms"]:
        assert term["term"] in TERM_LABELS, f"no label for {term['term']}"


def test_standard_errors_are_clustered_on_the_postcode():
    model = severity_model(cohort())
    assert model["clusters"] <= model["n"]
    assert model["clusters"] == len({c["plz5"] for c in cohort()})


def test_severity_model_declines_when_there_are_too_few_events():
    model = severity_model(cohort(n=60, severe_share=0.05))
    assert model["available"] is False
    assert "parameters" in model["reason"] or "severe" in model["reason"]


def test_severity_model_declines_on_an_empty_cohort():
    model = severity_model([])
    assert model["available"] is False
    assert "deprivation score" in model["reason"]


def test_severity_model_declines_when_nothing_can_be_graded():
    records = [case(ph=None, bicarbonate=None, plz5=p, kreis_ags=None)
               for p in pilot_plz5()]
    model = severity_model(records)
    assert model["available"] is False


def test_severity_model_ignores_cases_without_a_deprivation_score():
    records = cohort(n=400)
    model = severity_model(records)
    assert model["available"] is True, model.get("reason")
    assert model["n"] <= len(records)


def test_ungradeable_cases_are_dropped_not_modelled_as_non_severe():
    records = cohort(n=300)
    baseline = severity_model(records)
    padded = records + [
        case(ph=7.40, bicarbonate=None, plz5=p, kreis_ags=None)
        for p in list(pilot_plz5()) * 2
    ]
    model = severity_model(padded)
    assert model["ungradeable"] == len(list(pilot_plz5())) * 2
    assert model["n"] == baseline["n"], "ungradeable rows must not enter the fit"


def test_the_events_per_parameter_floor_is_ten():
    assert MIN_EVENTS_PER_PARAMETER == 10



def test_duration_model_fits_and_estimates_its_dispersion():
    model = duration_model(cohort())
    assert model["available"] is True, model.get("reason")
    assert model["measure"] == "Duration ratio"
    assert model["alpha"] > 0
    assert isinstance(model["alpha_estimated"], bool)
    assert model["median_duration"] > 0


def test_duration_model_declines_below_thirty_records():
    model = duration_model(cohort(n=20))
    assert model["available"] is False
    assert "30" in model["reason"]


def test_duration_model_declines_when_no_case_records_a_duration():
    records = [
        case(duration_of_symptoms=None, plz5=p, kreis_ags=None, **SEVERE)
        for p in list(pilot_plz5()) * 6
    ]
    model = duration_model(records)
    assert model["available"] is False


def test_duration_model_uses_only_new_onset_records():
    records = cohort(n=300)
    known_diabetes = [dict(record, new_onset=0) for record in cohort(n=300, seed=99)]
    assert duration_model(records + known_diabetes)["n"] == duration_model(records)["n"]
