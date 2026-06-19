def year_range(patients: list[dict]) -> tuple[int, int]:
    years = sorted({int(patient["year of onset"]) for patient in patients})
    return min(years), max(years)


def default_filters(patients: list[dict]) -> dict:
    year_min, year_max = year_range(patients)
    return {
        "age_min": 1,
        "age_max": 48,
        "year_min": year_min,
        "year_max": year_max,
        "sex": {"Male", "Female"},
        "glucose_min": 150.0,
        "glucose_max": 789.0,
        "ph_min": 6.65,
        "ph_max": 7.35,
        "bikarb_min": 1.5,
        "bikarb_max": 22.0,
    }


def patient_matches(patient: dict, filters: dict) -> bool:
    try:
        age = int(patient["age at onset"])
        year = int(patient["year of onset"])
        glucose = float(patient["glucose"])
        ph = float(patient["ph"])
        bikarb = float(patient["bikarb"])
        sex = patient["sex"]
    except (ValueError, KeyError):
        return False

    return (
        filters["age_min"] <= age <= filters["age_max"]
        and filters["year_min"] <= year <= filters["year_max"]
        and sex in filters["sex"]
        and filters["glucose_min"] <= glucose <= filters["glucose_max"]
        and filters["ph_min"] <= ph <= filters["ph_max"]
        and filters["bikarb_min"] <= bikarb <= filters["bikarb_max"]
    )
