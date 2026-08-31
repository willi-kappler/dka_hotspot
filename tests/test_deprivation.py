
import pytest

from services.deprivation import (
    GISD_MAX_YEAR,
    GISD_MIN_YEAR,
    attach_to_cases,
    coverage,
    is_carried_forward,
    mean_score,
    observation_year,
    regional_tertile_cuts,
    score_for,
    tertile_for,
)
from services.geography import pilot_plz5


def test_observation_year_clamps_to_the_available_series():
    assert observation_year(2015) == 2015
    assert observation_year(1990) == GISD_MIN_YEAR
    assert observation_year(2030) == GISD_MAX_YEAR


def test_carried_forward_is_flagged_only_past_the_last_observation():
    assert is_carried_forward(2023) is False
    assert is_carried_forward(2024) is True
    assert is_carried_forward(2025) is True


def test_score_for_resolves_a_pilot_postcode():
    postcode = pilot_plz5()[0]
    assert isinstance(score_for(postcode, 2020), float)


def test_score_for_beyond_the_series_reuses_the_last_observation():
    postcode = pilot_plz5()[0]
    assert score_for(postcode, 2025) == score_for(postcode, GISD_MAX_YEAR)


def test_score_for_an_unknown_or_blank_postcode_is_none():
    assert score_for("", 2020) is None
    assert score_for("70173", 2020) is None


def test_mean_score_lies_between_the_yearly_scores_it_averages():
    postcode = pilot_plz5()[0]
    yearly = [score_for(postcode, year) for year in range(2014, 2024)]
    assert min(yearly) <= mean_score(postcode, 2014, 2023) <= max(yearly)


def test_mean_score_of_a_single_year_is_that_year():
    postcode = pilot_plz5()[0]
    assert mean_score(postcode, 2020, 2020) == pytest.approx(score_for(postcode, 2020))


def test_tertiles_split_the_region_into_three_populated_bands():
    bands = [tertile_for(p, 2014, 2025) for p in pilot_plz5()]
    populated = {b for b in bands if b is not None}
    assert populated == {1, 2, 3}


def test_tertile_cuts_are_ordered():
    first, second = regional_tertile_cuts(2014, 2025)
    assert first < second


def test_tertile_one_is_the_least_deprived():
    scores = {p: mean_score(p, 2014, 2025) for p in pilot_plz5()}
    banded = {p: tertile_for(p, 2014, 2025) for p in pilot_plz5()}
    lower = [scores[p] for p, b in banded.items() if b == 1]
    higher = [scores[p] for p, b in banded.items() if b == 3]
    assert max(lower) <= min(higher)


def test_tertile_of_an_unknown_postcode_is_none():
    assert tertile_for("70173", 2014, 2025) is None
    assert tertile_for("", 2014, 2025) is None


def test_coverage_reports_how_many_areas_resolve():
    result = coverage()
    assert result["areas"] == len(pilot_plz5())
    assert result["resolved"] <= result["areas"]
    assert len(result["missing"]) == result["areas"] - result["resolved"]


def test_attach_to_cases_adds_a_year_matched_score():
    postcode = pilot_plz5()[0]
    cases = [
        {"plz5": postcode, "year_of_onset": 2015},
        {"plz5": postcode, "year_of_onset": 2020},
    ]
    enriched = attach_to_cases(cases)
    assert enriched[0]["gisd_score"] == score_for(postcode, 2015)
    assert enriched[1]["gisd_score"] == score_for(postcode, 2020)
    assert all(c["gisd_carried_forward"] is False for c in enriched)


def test_attach_to_cases_preserves_the_original_fields():
    postcode = pilot_plz5()[0]
    enriched = attach_to_cases([{"plz5": postcode, "year_of_onset": 2020, "sex": "Male"}])
    assert enriched[0]["sex"] == "Male"


def test_attach_to_cases_marks_carried_forward_years():
    postcode = pilot_plz5()[0]
    enriched = attach_to_cases([{"plz5": postcode, "year_of_onset": 2025}])
    assert enriched[0]["gisd_carried_forward"] is True


def test_attach_to_cases_tolerates_a_missing_postcode():
    enriched = attach_to_cases([{"year_of_onset": 2020}])
    assert enriched[0]["gisd_score"] is None
