

def case(**overrides) -> dict:
    record = {
        "pseudonym": "T0001",
        "clinic": "TUE",
        "age_at_onset": 8.0,
        "sex": "Male",
        "migration_background": "No",
        "plz5": "72070",
        "kreis_ags": "08416",
        "month_of_onset": 6,
        "year_of_onset": 2022,
        "new_onset": 1,
        "referral_pathway": "Pediatrician",
        "ph": 7.38,
        "bicarbonate": 22.0,
        "hba1c": 11.0,
        "glucose": 400,
        "duration_of_symptoms": 10,
        "dka_reported": 0,
        "dka_severity_reported": "none",
    }
    record.update(overrides)
    return record


def onset(**overrides) -> dict:
    record = {
        "clinic": "TUE", "year": 2022, "kreis_ags": "08416",
        "manifestations": 30, "dka_cases": 12,
    }
    record.update(overrides)
    return record
