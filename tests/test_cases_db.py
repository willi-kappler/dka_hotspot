
import pytest
from factories import case

from storage.cases_db import (
    _flag,
    _onset_month_year,
    _to_row,
    add_cases,
    import_csv_file,
    load_cases,
    normalise_header,
    parse_csv,
    validate,
)


@pytest.mark.parametrize("header, expected", [
    ("pseudo_id", "pseudonym"),
    ("Pseudo ID", "pseudonym"),
    ("center", "clinic"),
    ("centre", "clinic"),
    ("zip_code", "plz5"),
    ("Zip Code", "plz5"),
    ("PLZ", "plz5"),
    ("postleitzahl", "plz5"),
    ("ph_venous", "ph"),
    ("bicarbonate_mmol_l", "bicarbonate"),
    ("hba1c_percent", "hba1c"),
    ("glucose_mg_dl", "glucose"),
    ("symptom_duration_days", "duration_of_symptoms"),
    ("symptomdauer", "duration_of_symptoms"),
    ("dka", "dka_reported"),
    ("dka_severity", "dka_severity_reported"),
    ("landkreis", "kreis_ags"),
    ("Alter", "age_at_onset"),
    ("geschlecht", "sex"),
])
def test_header_aliases_map_clinic_and_german_headings(header, expected):
    assert normalise_header(header) == expected


def test_unknown_headers_are_snake_cased_rather_than_dropped():
    assert normalise_header("Some New Column") == "some_new_column"
    assert normalise_header("  spaced   out  ") == "spaced_out"



@pytest.mark.parametrize("value, expected", [
    ("2016-07", (7, 2016)),
    ("2016/07", (7, 2016)),
    ("2016-07-15", (7, 2016)),
])
def test_onset_date_is_read_as_month_and_year(value, expected):
    assert _onset_month_year({"date_of_onset": value}) == expected


def test_separate_month_and_year_columns_still_work():
    assert _onset_month_year({"month_of_onset": "7", "year_of_onset": "2016"}) == (7, 2016)
    assert _onset_month_year({"month_of_onset": 7.0, "year_of_onset": 2016.0}) == (7, 2016)


def test_a_date_takes_precedence_over_separate_columns():
    assert _onset_month_year(
        {"date_of_onset": "2016-07", "month_of_onset": 1, "year_of_onset": 1999}
    ) == (7, 2016)


@pytest.mark.parametrize("payload", [
    {}, {"month_of_onset": 7}, {"year_of_onset": 2016}, {"date_of_onset": "2016"},
])
def test_an_unreadable_onset_date_raises(payload):
    with pytest.raises(ValueError):
        _onset_month_year(payload)


@pytest.mark.parametrize("raw, expected", [
    ("1", 1), ("yes", 1), ("Ja", 1), ("TRUE", 1), ("y", 1),
    ("0", 0), ("no", 0), ("nein", 0), ("false", 0),
    ("", None), (None, None), ("maybe", None),
])
def test_flag_parses_yes_no_in_both_languages(raw, expected):
    assert _flag(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("m", "Male"), ("M", "Male"), ("male", "Male"), ("männlich", "Male"),
    ("f", "Female"), ("w", "Female"), ("weiblich", "Female"),
])
def test_sex_values_accept_clinic_and_german_codings(raw, expected):
    assert _to_row(case(sex=raw))[3] == expected


def test_an_unrecognised_sex_raises_rather_than_defaulting():
    with pytest.raises(ValueError, match="Unrecognised sex"):
        _to_row(case(sex="x"))



def test_the_landkreis_is_derived_from_the_postcode_when_absent():
    row = _to_row(case(plz5="72760", kreis_ags=None))
    assert row[5] == "72760" and row[6] == "08415"


def test_a_supplied_landkreis_is_kept_as_filed():
    assert _to_row(case(plz5="72070", kreis_ags="08416"))[6] == "08416"


def test_a_short_landkreis_code_is_zero_padded():
    assert _to_row(case(plz5="72070", kreis_ags="8416"))[6] == "08416"


def test_a_postcode_outside_the_pilot_region_is_rejected():
    with pytest.raises(ValueError, match="outside the pilot region"):
        _to_row(case(plz5="70173", kreis_ags=None))


def test_a_landkreis_outside_the_pilot_region_is_rejected():
    with pytest.raises(ValueError, match="outside the pilot region"):
        _to_row(case(plz5=None, kreis_ags="08111"))


def test_migration_background_falls_back_to_unknown():
    assert _to_row(case(migration_background="nonsense"))[4] == "Unknown"
    assert _to_row(case(migration_background=None))[4] == "Unknown"
    assert _to_row(case(migration_background="yes"))[4] == "Yes"



def test_a_valid_row_produces_no_errors():
    assert validate([case()]) == []


@pytest.mark.parametrize("field", ["clinic", "age_at_onset", "sex", "new_onset"])
def test_missing_required_fields_are_reported(field):
    errors = validate([case(**{field: None})])
    assert errors and field in errors[0]


@pytest.mark.parametrize("age", [-1, 20, 25])
def test_ages_outside_the_paediatric_range_are_rejected(age):
    errors = validate([case(age_at_onset=age)])
    assert errors and "outside 0" in errors[0]


def test_a_non_numeric_age_is_reported_as_such():
    assert "age must be a number" in validate([case(age_at_onset="eight")])[0]


def test_an_ambiguous_new_onset_value_is_rejected():
    assert "new_onset" in validate([case(new_onset="maybe")])[0]


def test_a_row_with_neither_postcode_nor_landkreis_is_rejected():
    errors = validate([case(plz5=None, kreis_ags=None)])
    assert "needs a postcode or a Landkreis" in errors[0]


def test_error_messages_carry_the_spreadsheet_row_number():
    errors = validate([case(), case(sex="x")])
    assert errors[0].startswith("row 3:")



CSV = (
    "pseudo_id,center,sex,age_at_onset,date_of_onset,zip_code,"
    "migration_background,new_onset,symptom_duration_days,referral_pathway,"
    "ph_venous,bicarbonate_mmol_l,hba1c_percent,hba1c_mmol_mol,glucose_mg_dl,"
    "dka,dka_severity\n"
    "10001,TUE,f,7.4,2024-03,72074,no,yes,14,pediatrician,7.05,4.2,12.4,114.0,412,yes,severe\n"
)


def test_parse_csv_maps_headers_and_keeps_the_row():
    rows = parse_csv(CSV)
    assert len(rows) == 1
    assert rows[0]["plz5"] == "72074"
    assert rows[0]["clinic"] == "TUE"
    assert rows[0]["duration_of_symptoms"] == "14"


def test_parse_csv_drops_the_redundant_hba1c_scale():
    assert "hba1c_mmol_mol" not in parse_csv(CSV)[0]


def test_parse_csv_raises_on_an_invalid_row():
    bad = CSV.replace(",f,", ",x,")
    with pytest.raises(ValueError, match="Unrecognised sex|unrecognised sex"):
        parse_csv(bad)



def test_add_and_load_cases_round_trip(temp_db):
    assert add_cases([case(pseudonym="A"), case(pseudonym="B")]) == 2
    loaded = load_cases()
    assert [c["pseudonym"] for c in loaded] == ["A", "B"]
    assert loaded[0]["kreis_ags"] == "08416"
    assert loaded[0]["sex"] == "Male"


def test_add_cases_with_an_empty_list_is_a_no_op(temp_db):
    assert add_cases([]) == 0
    assert load_cases() == []


def test_import_csv_file_appends_by_default(tmp_path, temp_db):
    path = tmp_path / "cases.csv"
    path.write_text(CSV, encoding="utf-8")
    import_csv_file(path)
    import_csv_file(path)
    assert len(load_cases()) == 2


def test_import_csv_file_with_replace_clears_first(tmp_path, temp_db):
    path = tmp_path / "cases.csv"
    path.write_text(CSV, encoding="utf-8")
    import_csv_file(path)
    import_csv_file(path, replace=True)
    assert len(load_cases()) == 1


def test_the_database_rejects_an_out_of_range_age(temp_db):
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        add_cases([case(age_at_onset=25.0)])


def test_the_database_rejects_an_unknown_clinic(temp_db):
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        add_cases([case(clinic="XXX")])



def test_classification_disagreements_finds_a_mismatch(temp_db):
    from storage.cases_db import classification_disagreements

    add_cases([
        case(pseudonym="MISMATCH", ph=7.40, bicarbonate=24.0,
             dka_severity_reported="severe"),
        case(pseudonym="AGREES", ph=7.05, bicarbonate=4.0,
             dka_severity_reported="severe"),
    ])
    rows = classification_disagreements()
    assert [row["pseudonym"] for row in rows] == ["MISMATCH"]
    assert rows[0]["reported"] == "Severe"
    assert rows[0]["derived"] == "No DKA"


def test_cases_without_a_reported_grade_are_not_disagreements(temp_db):
    from storage.cases_db import classification_disagreements

    add_cases([case(dka_severity_reported=None, ph=7.05, bicarbonate=4.0)])
    assert classification_disagreements() == []


def test_an_ungradeable_case_reported_as_dka_is_a_disagreement(temp_db):
    from storage.cases_db import classification_disagreements

    add_cases([case(pseudonym="PARTIAL", ph=7.40, bicarbonate=None,
                    dka_severity_reported="mild")])
    rows = classification_disagreements()
    assert rows[0]["derived"] == "Unknown"
