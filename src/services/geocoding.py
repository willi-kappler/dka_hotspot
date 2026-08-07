import json
import math
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from env import get_env

GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"
COUNTRY = "Germany"
JITTER_STEP_METERS = 80
JITTER_MAX_METERS = 450
METERS_PER_LAT_DEGREE = 111_320

geocode_cache: dict[tuple[str, str], tuple[float, float]] = {}


def get_geoapify_api_key() -> str:
    return get_env("GEOAPIFY_API_KEY")


def geocode_zipcode(zipcode: str, state: str = "") -> tuple[float, float]:
    """Return the center point for a German ZIP code using Geoapify."""
    api_key = get_geoapify_api_key()
    if not api_key:
        raise RuntimeError("Set GEOAPIFY_API_KEY in the environment or local .env file before adding data.")

    clean_zipcode = zipcode.strip()
    clean_state = state.strip()
    if not clean_zipcode:
        raise ValueError("ZIP code is required.")

    cache_key = (clean_zipcode, clean_state)
    if cache_key in geocode_cache:
        return geocode_cache[cache_key]

    params = {
        "postcode": clean_zipcode,
        "country": COUNTRY,
        "format": "json",
        "limit": 1,
        "apiKey": api_key,
    }
    if clean_state:
        params["state"] = clean_state

    request = Request(
        f"{GEOAPIFY_URL}?{urlencode(params)}",
        headers={"User-Agent": "DKA Hotspot Analysis Map"},
    )
    with urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data.get("results"):
        result = data["results"][0]
        lat_value = result["lat"]
        lon_value = result["lon"]
    elif data.get("features"):
        properties = data["features"][0].get("properties", {})
        lat_value = properties["lat"]
        lon_value = properties["lon"]
    else:
        raise ValueError(f"No coordinates found for ZIP code {clean_zipcode}.")

    lat = float(lat_value)
    lon = float(lon_value)
    geocode_cache[cache_key] = (lat, lon)
    return lat, lon


# Vogel spiral (golden-angle / phyllotaxis spiral, Vogel 1979): each duplicate
# is placed at angle n x 137.5deg and radius ~ sqrt(n), the sunflower-seed pattern,
# which spreads markers around the zip centroid evenly without overlaps.
def jitter_coordinates(lat: float, lon: float, duplicate_index: int) -> tuple[float, float]:
    if duplicate_index <= 0:
        return round(lat, 4), round(lon, 4)

    angle = duplicate_index * math.radians(137.5)
    radius = min(JITTER_MAX_METERS, JITTER_STEP_METERS * math.sqrt(duplicate_index))
    north_meters = radius * math.cos(angle)
    east_meters = radius * math.sin(angle)
    lat_offset = north_meters / METERS_PER_LAT_DEGREE
    lon_offset = east_meters / (METERS_PER_LAT_DEGREE * math.cos(math.radians(lat)))
    return round(lat + lat_offset, 4), round(lon + lon_offset, 4)


def next_free_duplicate_index(lat: float, lon: float, occupied_coords: set[tuple[float, float]]) -> int:
    """Return the first spiral index whose jittered position is not already taken.

    Deriving the index from the actual occupied coordinates (rather than a row
    count) keeps markers from stacking after rows are deleted: a count-based
    index would reuse spiral positions that are still occupied by other rows.
    """
    index = 0
    while jitter_coordinates(lat, lon, index) in occupied_coords:
        index += 1
    return index


def geocode_patient_row(row: dict, occupied_coords: set[tuple[float, float]] | None = None) -> dict:
    lat, lon = geocode_zipcode(row.get("zipcode", ""), row.get("state", ""))
    duplicate_index = next_free_duplicate_index(lat, lon, occupied_coords or set())
    lat, lon = jitter_coordinates(lat, lon, duplicate_index)
    return {**row, "lat": lat, "lon": lon}
