
import pytest

from services.endpoint import (
    MIN_DENOMINATOR,
    by_kreis,
    by_year,
    overall,
    pandemic_comparison,
    year_trend,
)


def onset(clinic="TUE", year=2022, kreis="08416", manifestations=30, dka=12):
    return {
        "clinic": clinic, "year": year, "kreis_ags": kreis,
        "manifestations": manifestations, "dka_cases": dka,
    }



def test_overall_pools_counts_before_dividing():
    rows = [
        onset(year=2020, manifestations=10, dka=5),
        onset(year=2021, manifestations=100, dka=10),
    ]
    result = overall(rows, 2014, 2025)
    assert result["successes"] == 15
    assert result["total"] == 110
    assert result["proportion"] == pytest.approx(15 / 110)


def test_overall_respects_the_year_filter():
    rows = [onset(year=2019, dka=30, manifestations=30), onset(year=2022)]
    assert overall(rows, 2022, 2025)["total"] == 30
    assert overall(rows, 2022, 2025)["successes"] == 12


def test_overall_respects_a_clinic_filter():
    rows = [onset(clinic="TUE"), onset(clinic="RT", kreis="08415")]
    assert overall(rows, 2014, 2025, clinics={"TUE"})["total"] == 30


def test_rows_without_a_dka_count_are_excluded_entirely():
    rows = [onset(dka=None), onset(dka=12)]
    assert overall(rows, 2014, 2025)["total"] == 30


def test_overall_with_no_matching_rows_has_no_proportion():
    assert overall([], 2014, 2025)["proportion"] is None



def test_by_year_groups_and_sorts():
    rows = [
        onset(year=2021, manifestations=10, dka=2),
        onset(year=2020, manifestations=20, dka=8),
        onset(year=2020, clinic="RT", kreis="08415", manifestations=10, dka=2),
    ]
    annual = by_year(rows, 2014, 2025)
    assert [r["year"] for r in annual] == [2020, 2021]
    assert annual[0]["total"] == 30 and annual[0]["successes"] == 10


def test_year_trend_detects_a_rise():
    rows = [
        onset(year=year, manifestations=100, dka=dka)
        for year, dka in [(2018, 10), (2019, 20), (2020, 30), (2021, 40)]
    ]
    assert year_trend(rows, 2014, 2025)["p_value"] < 0.001



def test_by_kreis_returns_all_three_districts_even_with_no_data():
    result = by_kreis([onset(kreis="08416")], 2014, 2025)
    assert {r["ags"] for r in result} == {"08415", "08416", "08417"}
    empty = [r for r in result if r["ags"] == "08415"][0]
    assert empty["total"] == 0 and empty["proportion"] is None


def test_by_kreis_marks_districts_under_the_reporting_threshold():
    rows = [onset(kreis="08416", manifestations=MIN_DENOMINATOR - 1, dka=5)]
    district = [r for r in by_kreis(rows, 2014, 2025) if r["ags"] == "08416"][0]
    assert district["sufficient"] is False


def test_by_kreis_marks_a_district_at_exactly_the_threshold_as_sufficient():
    rows = [onset(kreis="08416", manifestations=MIN_DENOMINATOR, dka=5)]
    district = [r for r in by_kreis(rows, 2014, 2025) if r["ags"] == "08416"][0]
    assert district["sufficient"] is True


def test_by_kreis_flags_the_district_with_no_participating_clinic():
    result = {r["ags"]: r for r in by_kreis([], 2014, 2025)}
    assert result["08417"]["no_local_clinic"] is True
    assert result["08416"]["no_local_clinic"] is False


def test_by_kreis_pools_across_clinics_within_a_district():
    rows = [
        onset(clinic="TUE", kreis="08416", manifestations=20, dka=5),
        onset(clinic="RT", kreis="08416", manifestations=30, dka=10),
    ]
    district = [r for r in by_kreis(rows, 2014, 2025) if r["ags"] == "08416"][0]
    assert district["total"] == 50 and district["successes"] == 15



def test_pandemic_windows_are_fixed_calendar_years():
    rows = [
        onset(year=2016, manifestations=100, dka=20),
        onset(year=2020, manifestations=100, dka=40),
        onset(year=2023, manifestations=100, dka=25),
    ]
    result = pandemic_comparison(rows)
    assert result["before"]["label"] == "2014–2019"
    assert result["during"]["label"] == "2020–2021"
    assert result["after"]["label"] == "2022–2025"
    assert result["during"]["proportion"] == pytest.approx(0.40)
    assert result["during_vs_before"]["ratio"] == pytest.approx(2.0)


def test_pandemic_comparison_with_no_data_is_not_a_crash():
    result = pandemic_comparison([])
    assert result["before"]["proportion"] is None
    assert result["during_vs_before"]["ratio"] is None
