"""Build the PLZ-5 centroid table used by the case map."""

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from env import get_env  # noqa: E402
from services.geography import PILOT_KREISE, in_pilot_region  # noqa: E402

DATA = PROJECT_ROOT / "src" / "data"
REFERENCE_FILE = DATA / "plz5_reference_pilot_region.csv"
OUTPUT_FILE = DATA / "plz5_coordinates.csv"

ENDPOINT = "https://api.geoapify.com/v1/geocode/search"
FIELDS = ("zip_code", "latitude", "longitude", "resolved_name", "in_pilot_region")

REQUEST_PAUSE_SECONDS = 0.2


def pilot_postcodes() -> list[str]:
    with REFERENCE_FILE.open(encoding="utf-8-sig", newline="") as file:
        return sorted({row["zip_code"].strip() for row in csv.DictReader(file)})


def existing() -> dict[str, dict]:
    if not OUTPUT_FILE.exists():
        return {}
    with OUTPUT_FILE.open(encoding="utf-8", newline="") as file:
        return {row["zip_code"]: row for row in csv.DictReader(file)}


def geocode(postcode: str, key: str) -> dict | None:
    """Resolve a German postcode centroid."""
    query = urllib.parse.urlencode({
        "postcode": postcode,
        "country": "Germany",
        "type": "postcode",
        "format": "json",
        "limit": 1,
        "apiKey": key,
    })
    request = urllib.request.Request(
        f"{ENDPOINT}?{query}", headers={"User-Agent": "dka-hotspot-pilot/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"  {postcode}: request failed ({error})")
        return None

    results = payload.get("results") or []
    if not results:
        print(f"  {postcode}: no result")
        return None

    result = results[0]
    if str(result.get("postcode", "")).strip() != postcode:
        print(f"  {postcode}: geocoder returned {result.get('postcode')!r}, skipped")
        return None
    if result.get("state_code") != "BW":
        print(f"  {postcode}: resolved outside Baden-Württemberg, skipped")
        return None

    latitude, longitude = float(result["lat"]), float(result["lon"])
    return {
        "zip_code": postcode,
        "latitude": f"{latitude:.6f}",
        "longitude": f"{longitude:.6f}",
        "resolved_name": result.get("formatted", ""),
        "in_pilot_region": "yes" if in_pilot_region(latitude, longitude) else "no",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                        help="re-fetch postcodes already in the output file")
    arguments = parser.parse_args()

    key = get_env("GEOAPIFY_API_KEY")
    if not key:
        raise SystemExit(
            "Set GEOAPIFY_API_KEY in the environment or .env before running this."
        )

    postcodes = pilot_postcodes()
    known = {} if arguments.refresh else existing()
    pending = [postcode for postcode in postcodes if postcode not in known]

    print(f"{len(postcodes)} pilot postcodes, {len(known)} already resolved, "
          f"{len(pending)} to fetch.")

    resolved = dict(known)
    for index, postcode in enumerate(pending, start=1):
        print(f"[{index}/{len(pending)}] {postcode}", end=" ")
        entry = geocode(postcode, key)
        if entry:
            resolved[postcode] = entry
            print(f"-> {entry['latitude']}, {entry['longitude']}")
        time.sleep(REQUEST_PAUSE_SECONDS)

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for postcode in postcodes:
            if postcode in resolved:
                writer.writerow(resolved[postcode])

    outside = [row for row in resolved.values() if row["in_pilot_region"] == "no"]
    missing = [postcode for postcode in postcodes if postcode not in resolved]

    print(f"\nWrote {len(resolved)} of {len(postcodes)} postcodes to {OUTPUT_FILE}.")
    if outside:
        print(f"{len(outside)} centroids fall outside the three district polygons: "
              + ", ".join(row["zip_code"] for row in outside))
        print("  (kept — these are boundary-straddling areas, not errors)")
    if missing:
        print(f"{len(missing)} could not be resolved: " + ", ".join(missing))
    print(f"Districts covered: {', '.join(sorted(PILOT_KREISE.values()))}")


if __name__ == "__main__":
    main()
