import json
import math
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"
COUNTRY = "Germany"
JITTER_STEP_METERS = 80
JITTER_MAX_METERS = 450
METERS_PER_LAT_DEGREE = 111_320

geocode_cache: dict[tuple[str, str], tuple[float, float]] = {}


def get_geoapify_api_key() -> str:
    env_key = os.getenv("GEOAPIFY_API_KEY")
    if env_key:
        return env_key

    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return ""

    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "GEOAPIFY_API_KEY":
            return value.strip().strip('"').strip("'")

    return ""


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


def geocode_patient_row(row: dict, duplicate_index: int = 0) -> dict:
    lat, lon = geocode_zipcode(row.get("zipcode", ""), row.get("state", ""))
    lat, lon = jitter_coordinates(lat, lon, duplicate_index)
    return {**row, "lat": lat, "lon": lon}
