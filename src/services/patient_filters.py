# Single source of truth for the filterable value ranges. The map filters,
# their reset defaults, and the pH marker gradient all derive from these.
AGE_MIN, AGE_MAX = 1, 48
PH_MIN, PH_MAX = 6.65, 7.45
BIKARB_MIN, BIKARB_MAX = 1.5, 22.0
GLUCOSE_MIN, GLUCOSE_MAX = 150, 789


def year_range(patients: list[dict]) -> tuple[int, int]:
    years = sorted({int(patient["year of onset"]) for patient in patients})
    return min(years), max(years)


def default_filters(patients: list[dict]) -> dict:
    year_min, year_max = year_range(patients)
    return {
        "age_min": AGE_MIN,
        "age_max": AGE_MAX,
        "year_min": year_min,
        "year_max": year_max,
        "sex": {"Male", "Female"},
        "glucose_min": GLUCOSE_MIN,
        "glucose_max": GLUCOSE_MAX,
        "ph_min": PH_MIN,
        "ph_max": PH_MAX,
        "bikarb_min": BIKARB_MIN,
        "bikarb_max": BIKARB_MAX,
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
