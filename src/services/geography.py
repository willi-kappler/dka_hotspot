"""Pilot-region geography and PLZ-5 lookups."""

import csv
import json
import math
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
BOUNDARIES_FILE = DATA / "landkreise_baden_wuerttemberg.geojson"
REFERENCE_FILE = DATA / "plz5_reference_pilot_region.csv"
COORDINATES_FILE = DATA / "plz5_coordinates.csv"
PRACTICES_FILE = DATA / "kvbw_pediatricians.csv"
HOSPITALS_FILE = DATA / "bw_childrens_hospitals_2026-07-28.csv"

PILOT_KREISE = {
    "08415": "Reutlingen",
    "08416": "Tübingen",
    "08417": "Zollernalbkreis",
}

# Zollernalbkreis has no participating clinic.
KREISE_WITHOUT_CLINIC = {"08417"}

KREIS_NAME_TO_AGS = {
    "Kreis Reutlingen": "08415",
    "Kreis Tübingen": "08416",
    "Zollernalbkreis": "08417",
}

METRES_PER_LATITUDE_DEGREE = 111_320


@lru_cache(maxsize=1)  #cache to avoid repeated file reads
def pilot_boundaries() -> dict:
    """GeoJSON FeatureCollection holding only the three pilot districts."""
    data = json.loads(BOUNDARIES_FILE.read_text(encoding="utf-8"))
    features = [
        feature for feature in data["features"]
        if str(feature["properties"].get("AGS", "")).zfill(5) in PILOT_KREISE
    ]
    return {"type": "FeatureCollection", "features": features}


@lru_cache(maxsize=1)
def pilot_bounds() -> tuple[tuple[float, float], tuple[float, float]]:
    """South-west and north-east corners enclosing the three pilot districts."""
    lats: list[float] = []
    lons: list[float] = []

    def walk(coordinates):
        if (
            isinstance(coordinates, (list, tuple))
            and len(coordinates) >= 2
            and isinstance(coordinates[0], (int, float))
        ):
            lons.append(float(coordinates[0]))
            lats.append(float(coordinates[1]))
            return
        for item in coordinates:
            walk(item)

    for feature in pilot_boundaries()["features"]:
        walk(feature["geometry"]["coordinates"])
    return (min(lats), min(lons)), (max(lats), max(lons))


def pilot_view(viewport: tuple[int, int] = (960, 520)) -> tuple[tuple[float, float], int]:
    """Return a map view that frames the pilot region."""
    (south, west), (north, east) = pilot_bounds()
    centre = ((south + north) / 2, (west + east) / 2)

    width, height = viewport
    longitude_span = max(east - west, 1e-6)
    latitude_span = max(north - south, 1e-6) / math.cos(math.radians(centre[0]))

    zoom_for_width = math.log2(360 * width / (256 * longitude_span))
    zoom_for_height = math.log2(360 * height / (256 * latitude_span))
    zoom = int(min(zoom_for_width, zoom_for_height))
    return centre, max(6, min(12, zoom))


def kreis_name(ags: str) -> str:
    return PILOT_KREISE.get(str(ags).zfill(5), "")


def is_pilot_kreis(ags: str) -> bool:
    return str(ags).zfill(5) in PILOT_KREISE


def normalise_plz5(value: str) -> str:
    """Return a clean 5-digit postcode, or '' if the input cannot supply one."""
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits[:5] if len(digits) >= 5 else ""


@lru_cache(maxsize=1)
def _reference() -> dict[str, dict]:
    """Load pilot postcodes keyed by postcode."""
    entries: dict[str, dict] = {}
    with REFERENCE_FILE.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            postcode = normalise_plz5(row["zip_code"])
            ags = KREIS_NAME_TO_AGS.get(row["kreis"].strip())
            if not postcode or not ags:
                continue
            entries[postcode] = {
                "plz5": postcode,
                "city": row["city"].strip(),
                "kreis_ags": ags,
            }
    return entries


@lru_cache(maxsize=1)
def pilot_plz5() -> tuple[str, ...]:
    """Every postcode in the pilot region, sorted."""
    return tuple(sorted(_reference()))


def is_pilot_plz5(plz5: str) -> bool:
    return normalise_plz5(plz5) in _reference()


def plz5_kreis(plz5: str) -> str:
    """Landkreis AGS for a postcode, or '' if it is outside the pilot."""
    entry = _reference().get(normalise_plz5(plz5))
    return entry["kreis_ags"] if entry else ""


def plz5_city(plz5: str) -> str:
    entry = _reference().get(normalise_plz5(plz5))
    return entry["city"] if entry else ""


def plz5_label(plz5: str) -> str:
    """Human-readable '72760 Reutlingen' for tables and popups."""
    postcode = normalise_plz5(plz5)
    city = plz5_city(postcode)
    return f"{postcode} {city}".strip() if postcode else "—"


@lru_cache(maxsize=1)
def _coordinates() -> dict[str, dict]:
    if not COORDINATES_FILE.exists():
        return {}
    entries: dict[str, dict] = {}
    with COORDINATES_FILE.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            postcode = normalise_plz5(row["zip_code"])
            if not postcode:
                continue
            try:
                entries[postcode] = {
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "resolved_name": row.get("resolved_name", ""),
                    "in_region": row.get("in_pilot_region", "yes") == "yes",
                }
            except (TypeError, ValueError):
                continue
    return entries


@lru_cache(maxsize=1)
def plz5_centroids() -> dict[str, tuple[float, float]]:
    """Return the known pilot-postcode centroids."""
    known = _reference()
    return {
        postcode: (entry["lat"], entry["lon"])
        for postcode, entry in _coordinates().items()
        if postcode in known
    }


JITTER_SPACING_FRACTION = 0.42
JITTER_MIN_METRES = 300.0
JITTER_MAX_METRES = 2500.0


def _metres_between(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    """Approximate ground distance, good enough at this latitude and scale."""
    (lat_a, lon_a), (lat_b, lon_b) = first, second
    mean_latitude = math.radians((lat_a + lat_b) / 2)
    north = (lat_a - lat_b) * METRES_PER_LATITUDE_DEGREE
    east = (lon_a - lon_b) * METRES_PER_LATITUDE_DEGREE * math.cos(mean_latitude)
    return math.hypot(north, east)


@lru_cache(maxsize=1)
def plz5_jitter_radii() -> dict[str, float]:
    """Size each postcode's pin scatter from its nearest neighbour."""
    centroids = plz5_centroids()
    if len(centroids) < 2:
        return {postcode: JITTER_MIN_METRES for postcode in centroids}

    radii = {}
    for postcode, point in centroids.items():
        nearest = min(
            _metres_between(point, other)
            for code, other in centroids.items() if code != postcode
        )
        radii[postcode] = min(
            JITTER_MAX_METRES,
            max(JITTER_MIN_METRES, nearest * JITTER_SPACING_FRACTION),
        )
    return radii


def plz5_jitter_radius(plz5: str) -> float:
    return plz5_jitter_radii().get(normalise_plz5(plz5), JITTER_MIN_METRES)


@lru_cache(maxsize=1)
def plz5_outside_region() -> frozenset[str]:
    """Return centroids outside the district polygons."""
    known = _reference()
    return frozenset(
        postcode for postcode, entry in _coordinates().items()
        if postcode in known and not entry["in_region"]
    )


def _point_in_ring(longitude: float, latitude: float, ring: list) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[0], previous[1]
        x2, y2 = current[0], current[1]
        if (y1 > latitude) != (y2 > latitude):
            crossing = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < crossing:
                inside = not inside
        previous = current
    return inside


def in_pilot_region(latitude: float, longitude: float) -> bool:
    """Whether a point falls inside any of the three pilot districts."""
    for feature in pilot_boundaries()["features"]:
        geometry = feature["geometry"]
        polygons = (
            geometry["coordinates"] if geometry["type"] == "MultiPolygon"
            else [geometry["coordinates"]]
        )
        for polygon in polygons:
            if not polygon:
                continue
            if _point_in_ring(longitude, latitude, polygon[0]) and not any(
                _point_in_ring(longitude, latitude, hole) for hole in polygon[1:]
            ):
                return True
    return False


@lru_cache(maxsize=1)
def paediatric_practices() -> tuple[dict, ...]:
    """Paediatric practices inside the pilot districts, for the map overlay."""
    pilot_postcodes = set(pilot_plz5())
    practices = []
    with PRACTICES_FILE.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file, delimiter=";"):
            postcode = row["postcode"].strip()
            if postcode not in pilot_postcodes:
                continue
            try:
                practices.append({
                    "name": row["practice_name"] or row["physician_name"],
                    "city": row["city"],
                    "postcode": postcode,
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                })
            except (ValueError, KeyError):
                continue
    return tuple(practices)


@lru_cache(maxsize=1)
def clinics_on_map() -> tuple[dict, ...]:
    """Return paediatric hospitals in the pilot districts."""
    pilot_postcodes = set(pilot_plz5())
    participating = {"Universitätsklinikum Tübingen", "Klinikum am Steinenberg"}
    hospitals = []
    with HOSPITALS_FILE.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file, delimiter=";"):
            if row["postcode"].strip() not in pilot_postcodes:
                continue
            try:
                hospitals.append({
                    "name": row["hospital_name"],
                    "city": row["city"],
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "participating": row["hospital_name"] in participating,
                })
            except (ValueError, KeyError):
                continue
    return tuple(hospitals)
