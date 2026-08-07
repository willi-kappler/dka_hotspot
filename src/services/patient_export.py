import csv
import io

EXPORT_COLUMNS = [
    "age at onset", "sex", "zipcode", "state",
    "month of onset", "year of onset", "a1c", "glucose",
    "bikarb", "ph", "duration of symptoms",
]


def patients_to_csv(patients: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(patients)
    return buffer.getvalue().encode("utf-8")
