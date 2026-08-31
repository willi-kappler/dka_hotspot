
import math

import pytest
from statsmodels.stats.proportion import proportion_confint

from services.epidemiology import (
    MILD_BICARBONATE,
    MILD_PH,
    MODERATE_BICARBONATE,
    MODERATE_PH,
    NO_DKA,
    SEVERE_BICARBONATE,
    SEVERE_PH,
    UNKNOWN,
    cochran_armitage_trend,
    eligible_manifestations,
    frame_check,
    is_dka,
    is_gradeable,
    is_severe,
    proportion,
    proportion_with_ci,
    risk_ratio_with_ci,
    severity,
    split_manifestations,
    wilson_interval,
)


def test_ispad_thresholds_match_the_published_definition():
    assert (MILD_PH, MILD_BICARBONATE) == (7.3, 18.0)
    assert (MODERATE_PH, MODERATE_BICARBONATE) == (7.2, 10.0)
    assert (SEVERE_PH, SEVERE_BICARBONATE) == (7.1, 5.0)


@pytest.mark.parametrize("ph, bicarbonate, expected", [
    (7.40, 24.0, NO_DKA),
    (7.29, 24.0, "Mild"),
    (7.19, 24.0, "Moderate"),
    (7.05, 24.0, "Severe"),
    (7.40, 17.0, "Mild"),
    (7.40, 9.0, "Moderate"),
    (7.40, 4.0, "Severe"),
    (7.05, 24.0, "Severe"),
    (7.40, 4.0, "Severe"),
    (7.25, 4.0, "Severe"),
])
def test_severity_grades(ph, bicarbonate, expected):
    assert severity({"ph": ph, "bicarbonate": bicarbonate}) == expected


@pytest.mark.parametrize("bicarbonate, expected", [
    (17.9, "Mild"),     # just inside the diagnostic threshold
    (18.0, NO_DKA),     # exactly at it — the rule is strictly "below"
    (18.1, NO_DKA),
    (16.0, "Mild"),     # the value the bicarbonate-15 bug misclassified
])
def test_bicarbonate_boundary_with_normal_ph(bicarbonate, expected):
    assert severity({"ph": 7.40, "bicarbonate": bicarbonate}) == expected


@pytest.mark.parametrize("ph, expected", [
    (7.29, "Mild"),
    (7.30, NO_DKA),     # at the threshold, not below it
    (7.19, "Moderate"),
    (7.20, "Mild"),
    (7.09, "Severe"),
    (7.10, "Moderate"),
])
def test_ph_boundaries_are_strictly_below(ph, expected):
    assert severity({"ph": ph, "bicarbonate": 24.0}) == expected



def test_one_abnormal_value_establishes_dka_without_the_other():
    assert severity({"ph": 7.05, "bicarbonate": None}) == "Severe"
    assert severity({"ph": None, "bicarbonate": 4.0}) == "Severe"


def test_one_normal_value_cannot_exclude_dka_while_the_other_is_missing():
    assert severity({"ph": 7.40, "bicarbonate": None}) == UNKNOWN
    assert severity({"ph": None, "bicarbonate": 24.0}) == UNKNOWN


def test_both_values_missing_is_unknown():
    assert severity({"ph": None, "bicarbonate": None}) == UNKNOWN
    assert severity({}) == UNKNOWN


@pytest.mark.parametrize("junk", ["", "  ", "n/a", None, float("nan"), float("inf")])
def test_unparseable_values_are_treated_as_missing_not_as_zero(junk):
    assert severity({"ph": junk, "bicarbonate": junk}) == UNKNOWN


def test_numeric_strings_are_accepted():
    assert severity({"ph": "7.05", "bicarbonate": "4.0"}) == "Severe"


def test_is_gradeable_matches_the_unknown_grade():
    assert is_gradeable({"ph": 7.4, "bicarbonate": 24.0}) is True
    assert is_gradeable({"ph": 7.05, "bicarbonate": None}) is True
    assert is_gradeable({"ph": 7.4, "bicarbonate": None}) is False
    assert is_gradeable({}) is False


def test_is_dka_and_is_severe():
    assert is_dka({"ph": 7.25, "bicarbonate": 12.0}) is True
    assert is_dka({"ph": 7.40, "bicarbonate": 24.0}) is False
    assert is_dka({"ph": 7.40, "bicarbonate": None}) is False   # Unknown is not DKA
    assert is_severe({"ph": 7.05, "bicarbonate": 4.0}) is True
    assert is_severe({"ph": 7.25, "bicarbonate": 12.0}) is False



def test_split_manifestations_keeps_unknown_separate_from_no():
    groups = split_manifestations([
        {"new_onset": 1}, {"new_onset": True},
        {"new_onset": 0}, {"new_onset": False},
        {"new_onset": None}, {},
    ])
    assert len(groups["eligible"]) == 2
    assert len(groups["not_new_onset"]) == 2
    assert len(groups["unknown_new_onset"]) == 2


def test_eligible_manifestations_returns_only_confirmed_first_onsets():
    assert eligible_manifestations([{"new_onset": 1}, {"new_onset": None}]) == [
        {"new_onset": 1}
    ]



@pytest.mark.parametrize("successes, total", [
    (10, 100), (1, 5), (0, 20), (20, 20), (3, 7), (250, 500), (1, 1),
])
def test_wilson_interval_matches_statsmodels(successes, total):
    expected = proportion_confint(successes, total, alpha=0.05, method="wilson")
    assert wilson_interval(successes, total) == pytest.approx(expected, abs=1e-9)


def test_wilson_interval_stays_inside_zero_and_one():
    for successes, total in [(0, 5), (5, 5), (1, 3)]:
        low, high = wilson_interval(successes, total)
        assert 0.0 <= low <= high <= 1.0


def test_wilson_interval_with_no_denominator_is_nan():
    low, high = wilson_interval(0, 0)
    assert math.isnan(low) and math.isnan(high)


def test_proportion_and_proportion_with_ci():
    assert proportion(1, 4) == 0.25
    assert proportion(1, 0) is None

    result = proportion_with_ci(25, 100)
    assert result["proportion"] == 0.25
    assert result["successes"] == 25
    assert result["total"] == 100
    assert result["ci_low"] < 0.25 < result["ci_high"]

    empty = proportion_with_ci(0, 0)
    assert empty["proportion"] is None and empty["ci_low"] is None



def test_risk_ratio_point_estimate():
    result = risk_ratio_with_ci(50, 100, 25, 100)
    assert result["ratio"] == pytest.approx(2.0)
    assert result["ci_low"] < 2.0 < result["ci_high"]
    assert result["p_value"] < 0.05


def test_risk_ratio_of_identical_groups_is_one_and_not_significant():
    result = risk_ratio_with_ci(30, 100, 30, 100)
    assert result["ratio"] == pytest.approx(1.0)
    assert result["ci_low"] < 1.0 < result["ci_high"]
    assert result["p_value"] == pytest.approx(1.0)


@pytest.mark.parametrize("a, n_a, b, n_b", [
    (0, 50, 10, 50),    # no events in the exposed group
    (10, 50, 0, 50),    # none in the reference
    (5, 0, 5, 50),      # no denominator
])
def test_risk_ratio_not_estimable_at_a_zero_boundary(a, n_a, b, n_b):
    result = risk_ratio_with_ci(a, n_a, b, n_b)
    assert result == {"ratio": None, "ci_low": None, "ci_high": None, "p_value": None}


def test_risk_ratio_of_two_saturated_groups_is_not_estimable():
    assert risk_ratio_with_ci(50, 50, 50, 50)["ratio"] is None



def test_cochran_armitage_detects_a_monotone_rise():
    result = cochran_armitage_trend(
        successes=[10, 20, 30, 40],
        totals=[100, 100, 100, 100],
        scores=[2014.0, 2015.0, 2016.0, 2017.0],
    )
    assert result["statistic"] > 0
    assert result["p_value"] < 0.001
    assert result["n_groups"] == 4


def test_cochran_armitage_is_symmetric_under_reversal():
    rising = cochran_armitage_trend([10, 20, 30], [100] * 3, [1.0, 2.0, 3.0])
    falling = cochran_armitage_trend([30, 20, 10], [100] * 3, [1.0, 2.0, 3.0])
    assert rising["statistic"] == pytest.approx(-falling["statistic"])
    assert rising["p_value"] == pytest.approx(falling["p_value"])


def test_cochran_armitage_flat_series_has_no_trend():
    result = cochran_armitage_trend([20, 20, 20], [100] * 3, [1.0, 2.0, 3.0])
    assert result["statistic"] == pytest.approx(0.0)
    assert result["p_value"] == pytest.approx(1.0)


@pytest.mark.parametrize("successes, totals, scores, why", [
    ([10, 20], [100, 100], [1.0, 2.0], "fewer than three groups"),
    ([0, 0, 0], [100] * 3, [1.0, 2.0, 3.0], "no events anywhere"),
    ([100, 100, 100], [100] * 3, [1.0, 2.0, 3.0], "every case an event"),
    ([10, 20, 30], [100] * 3, [5.0, 5.0, 5.0], "no spread in the scores"),
])
def test_cochran_armitage_declines_to_report_when_undefined(successes, totals, scores, why):
    result = cochran_armitage_trend(successes, totals, scores)
    assert result["statistic"] is None, why
    assert result["p_value"] is None


def test_cochran_armitage_skips_empty_groups():
    result = cochran_armitage_trend([10, 0, 20, 30], [100, 0, 100, 100],
                                    [1.0, 2.0, 3.0, 4.0])
    assert result["n_groups"] == 3



def test_frame_check_flags_a_dka_only_extract():
    check = frame_check([{"ph": 7.1, "bicarbonate": 8.0}] * 20)
    assert check["share"] == 0.0
    assert check["suspicious"] is True


def test_frame_check_passes_a_plausible_cohort():
    cases = [{"ph": 7.1, "bicarbonate": 8.0}] * 6 + [{"ph": 7.4, "bicarbonate": 24.0}] * 4
    check = frame_check(cases)
    assert check["share"] == pytest.approx(0.4)
    assert check["suspicious"] is False
    assert check["n"] == 10


def test_frame_check_on_an_empty_cohort_is_suspicious_not_a_crash():
    check = frame_check([])
    assert check["n"] == 0 and check["suspicious"] is True


def test_frame_check_ignores_ungradeable_rows_in_its_denominator():
    cases = (
        [{"ph": 7.1, "bicarbonate": 8.0}] * 5
        + [{"ph": 7.4, "bicarbonate": 24.0}] * 5
        + [{"ph": None, "bicarbonate": None}] * 90
    )
    assert frame_check(cases)["n"] == 10
