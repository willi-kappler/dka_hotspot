
import pytest
from factories import onset

from storage.onsets_db import (
    _to_row,
    has_denominator,
    load_onsets,
    normalise_header,
    parse_csv,
    reporting_coverage,
    upsert_onsets,
)


@pytest.mark.parametrize("header, expected", [
    ("klinik", "clinic"), ("ambulanz", "clinic"),
    ("jahr", "year"), ("manifestationsjahr", "year"),
    ("landkreis", "kreis_ags"), ("kreis", "kreis_ags"), ("ags", "kreis_ags"),
    ("neumanifestationen", "manifestations"), ("total", "manifestations"),
    ("dka", "dka_cases"), ("ketoazidosen", "dka_cases"),
])
def test_german_headings_are_mapped(header, expected):
    assert normalise_header(header) == expected


def test_clinic_code_is_upper_cased_and_kreis_zero_padded():
    row = _to_row(onset(clinic="tue", kreis_ags="8416"))
    assert row[0] == "TUE" and row[2] == "08416"


def test_a_blank_dka_count_becomes_null_not_zero():
    assert _to_row(onset(dka_cases=""))[4] is None
    assert _to_row(onset(dka_cases=None))[4] is None
    assert _to_row(onset(dka_cases=0))[4] == 0


def test_more_dka_cases_than_manifestations_is_rejected():
    with pytest.raises(ValueError, match="exceeds"):
        _to_row(onset(manifestations=10, dka_cases=11))


def test_a_district_outside_the_pilot_is_rejected():
    with pytest.raises(ValueError, match="outside the pilot region"):
        _to_row(onset(kreis_ags="08111"))


def test_upsert_inserts_then_updates_in_place(temp_db):
    upsert_onsets([onset(manifestations=30, dka_cases=12)])
    upsert_onsets([onset(manifestations=31, dka_cases=13)])
    rows = load_onsets()
    assert len(rows) == 1
    assert rows[0]["manifestations"] == 31 and rows[0]["dka_cases"] == 13


def test_different_clinics_in_one_district_are_separate_rows(temp_db):
    upsert_onsets([onset(clinic="TUE"), onset(clinic="RT")])
    assert len(load_onsets()) == 2


def test_upsert_of_an_empty_list_is_a_no_op(temp_db):
    assert upsert_onsets([]) == 0


def test_has_denominator_reflects_whether_anything_is_loaded(temp_db):
    assert has_denominator() is False
    upsert_onsets([onset()])
    assert has_denominator() is True


def test_load_onsets_is_ordered_by_year_then_clinic(temp_db):
    upsert_onsets([
        onset(year=2022, clinic="TUE"),
        onset(year=2020, clinic="RT", kreis_ags="08415"),
        onset(year=2020, clinic="TUE"),
    ])
    rows = load_onsets()
    assert [(r["year"], r["clinic"]) for r in rows] == [
        (2020, "RT"), (2020, "TUE"), (2022, "TUE")
    ]


def test_reporting_coverage_exposes_gaps_and_missing_numerators(temp_db):
    upsert_onsets([
        onset(year=2020, manifestations=30, dka_cases=12),
        onset(year=2020, kreis_ags="08417", manifestations=10, dka_cases=None),
    ])
    coverage = reporting_coverage()
    assert len(coverage) == 1
    assert coverage[0]["kreis_rows"] == 2
    assert coverage[0]["manifestations"] == 40
    assert coverage[0]["missing_dka"] == 1


def test_parse_csv_requires_the_four_mandatory_columns():
    with pytest.raises(ValueError, match="Missing columns"):
        parse_csv("clinic,year\nTUE,2024\n")


def test_parse_csv_accepts_german_headings():
    rows = parse_csv("klinik,jahr,landkreis,neumanifestationen,dka\nTUE,2024,08416,31,12\n")
    assert rows[0]["manifestations"] == "31"


def test_the_database_enforces_the_dka_ceiling(temp_db):
    import sqlite3
    with pytest.raises((sqlite3.IntegrityError, ValueError)):
        upsert_onsets([onset(manifestations=5, dka_cases=9)])
