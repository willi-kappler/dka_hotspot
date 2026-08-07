"""Group patient cases into regions (Landkreise) for the hotspot map.

Step 1 (current): each region is colored/sized by how many cases it holds.
Step 2 (later, once a denominator is available): divide the count by the total
T1D manifestations in that region to show the true DKA *frequency* instead.
"""
from services.region_lookup import kreis_for_zip


def region_key(patient: dict) -> str:
    return kreis_for_zip(patient.get("zipcode", ""))


def aggregate_by_region(patients: list[dict]) -> list[dict]:
    """Return one entry per region (Kreis): its name, case count, and map position.

    The position is the average of the member coordinates, which places a single
    bubble roughly at the center of that region's cases.
    """
    groups: dict[str, list[dict]] = {}
    for patient in patients:
        key = region_key(patient)
        if key:
            groups.setdefault(key, []).append(patient)

    regions = []
    for key, members in groups.items():
        coords = []
        for member in members:
            try:
                coords.append((float(member["lat"]), float(member["lon"])))
            except (KeyError, TypeError, ValueError):
                continue
        if not coords:
            continue
        regions.append({
            "region": key,
            "count": len(members),
            "lat": sum(lat for lat, _ in coords) / len(coords),
            "lon": sum(lon for _, lon in coords) / len(coords),
        })
    return regions
