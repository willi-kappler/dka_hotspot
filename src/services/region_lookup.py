"""Map a ZIP code to its Landkreis (district), for grouping cases by Kreis.

Backed by data/baden_wuerttemberg_zipcodes.csv (columns: zipcode, city, kreis,
state). ZIPs not found in the file fall back to a per-ZIP label so their cases
still appear on the map instead of being silently dropped.
"""
import csv
from pathlib import Path

LOOKUP_FILE = Path(__file__).resolve().parent.parent / "data" / "baden_wuerttemberg_zipcodes.csv"

_zip_to_kreis: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _zip_to_kreis
    if _zip_to_kreis is None:
        mapping: dict[str, str] = {}
        # utf-8-sig strips the byte-order mark some spreadsheet exports prepend.
        with open(LOOKUP_FILE, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                zipcode = (row.get("zipcode") or "").strip()
                kreis = (row.get("kreis") or "").strip()
                if zipcode and kreis:
                    mapping[zipcode] = kreis
        _zip_to_kreis = mapping
    return _zip_to_kreis


def kreis_for_zip(zipcode: str) -> str:
    zipcode = str(zipcode).strip()
    if not zipcode:
        return ""
    kreis = _load().get(zipcode)
    return kreis if kreis else f"PLZ {zipcode}"
