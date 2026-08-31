
import pytest
from factories import case

from services.summaries import (
    by_age_band,
    by_deprivation,
    by_kreis,
    by_sex,
    by_year,
    duration_by_deprivation,
    overall,
    pandemic_comparison,
    severity_mix,
    year_trend,
)

DKA = {"ph": 7.05, "bicarbonate": 4.0}          # Severe
MILD = {"ph": 7.25, "bicarbonate": 16.0}        # Mild
CLEAR = {"ph": 7.40, "bicarbonate": 24.0}       # No DKA
UNGRADEABLE = {"ph": 7.40, "bicarbonate": None}  # Unknown


def test_overall_excludes_ungradeable_records_from_both_counts():
    cases = [case(**DKA), case(**CLEAR), case(**UNGRADEABLE)]
    result = overall(cases)
    assert result["total"] == 2, "the ungradeable record must leave the denominator"
    assert result["successes"] == 1
    assert result["ungradeable"] == 1


def test_overall_ignores_known_diabetes_episodes():
    cases = [case(**DKA), case(new_onset=0, **DKA)]
    assert overall(cases)["total"] == 1


def test_overall_ignores_records_with_an_unknown_onset_flag():
    cases = [case(**DKA), case(new_onset=None, **DKA)]
    assert overall(cases)["total"] == 1


def test_severity_mix_counts_every_class_that_occurs():
    cases = [case(**DKA), case(**MILD), case(**CLEAR), case(**UNGRADEABLE)]
    mix = {row["label"]: row["count"] for row in severity_mix(cases)}
    assert mix == {"Severe": 1, "Mild": 1, "No DKA": 1, "Unknown": 1}


def test_severity_mix_omits_empty_classes():
    labels = {row["label"] for row in severity_mix([case(**DKA)])}
    assert labels == {"Severe"}


def test_by_sex_splits_and_carries_denominators():
    cases = [case(sex="Male", **DKA), case(sex="Male", **CLEAR), case(sex="Female", **DKA)]
    rows = {row["label"]: row for row in by_sex(cases)}
    assert rows["Male"]["cases"] == 2
    assert rows["Male"]["dka"]["proportion"] == pytest.approx(0.5)
    assert rows["Female"]["dka"]["proportion"] == pytest.approx(1.0)


def test_age_bands_floor_a_decimal_age():
    rows = {row["label"]: row["cases"] for row in by_age_band([
        case(age_at_onset=4.5, **DKA),
        case(age_at_onset=0.6, **DKA),
        case(age_at_onset=19.4, **DKA),
    ])}
    assert rows["0–4"] == 2
    assert rows["15–19"] == 1


def test_every_paediatric_age_lands_in_exactly_one_band():
    ages = [0.0, 4.99, 5.0, 9.9, 10.0, 14.9, 15.0, 19.9]
    total = sum(row["cases"] for row in by_age_band(
        [case(age_at_onset=age, **DKA) for age in ages]
    ))
    assert total == len(ages)


def test_by_year_groups_and_sorts():
    cases = [case(year_of_onset=2020, **DKA), case(year_of_onset=2018, **CLEAR)]
    rows = by_year(cases)
    assert [row["year"] for row in rows] == [2018, 2020]


def test_by_kreis_flags_the_district_with_no_participating_clinic():
    rows = {r["ags"]: r for r in by_kreis([
        case(plz5="72070", kreis_ags="08416", **DKA),
        case(plz5="72336", kreis_ags="08417", **DKA),
    ])}
    assert rows["08417"]["no_local_clinic"] is True
    assert rows["08416"]["no_local_clinic"] is False


def test_by_kreis_skips_cases_with_no_district():
    assert by_kreis([case(plz5=None, kreis_ags=None, **DKA)]) == []


def test_by_deprivation_returns_ordered_tertiles():
    cases = [
        case(plz5=postcode, kreis_ags=None, **DKA)
        for postcode in ("72070", "72760", "72336", "72379", "72072", "72074")
    ]
    rows = by_deprivation(cases)
    assert [row["tertile"] for row in rows] == sorted(row["tertile"] for row in rows)
    assert all(row["label"] in ("Lower", "Middle", "Higher") for row in rows)


def test_pandemic_windows_are_fixed_calendar_years():
    cases = (
        [case(year_of_onset=2016, **CLEAR)] * 4
        + [case(year_of_onset=2020, **DKA)] * 4
        + [case(year_of_onset=2023, **MILD)] * 4
    )
    result = pandemic_comparison(cases)
    assert result["before"]["label"] == "2014–2019"
    assert result["before"]["proportion"] == pytest.approx(0.0)
    assert result["during"]["proportion"] == pytest.approx(1.0)


def test_year_trend_reports_no_trend_on_a_flat_series():
    cases = [
        case(year_of_onset=year, **(DKA if index % 2 else CLEAR))
        for year in (2018, 2019, 2020)
        for index in range(10)
    ]
    assert year_trend(cases)["p_value"] == pytest.approx(1.0, abs=0.05)


def test_duration_quartiles_are_ordered():
    cases = [
        case(plz5="72070", kreis_ags=None, duration_of_symptoms=days, **DKA)
        for days in (1, 3, 5, 7, 9, 11, 21)
    ]
    rows = duration_by_deprivation(cases)
    assert rows
    for row in rows:
        assert row["q1"] <= row["median"] <= row["q3"]
        assert row["n"] == 7


def test_duration_ignores_cases_with_no_recorded_duration():
    cases = [
        case(plz5="72070", kreis_ags=None, duration_of_symptoms=None, **DKA),
        case(plz5="72070", kreis_ags=None, duration_of_symptoms=5, **DKA),
    ]
    rows = duration_by_deprivation(cases)
    assert sum(row["n"] for row in rows) == 1


def test_an_empty_cohort_returns_empty_breakdowns_rather_than_raising():
    assert by_sex([]) == []
    assert by_year([]) == []
    assert by_age_band([]) == []
    assert by_deprivation([]) == []
    assert severity_mix([]) == []
    assert overall([])["proportion"] is None
