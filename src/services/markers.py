"""Markers for the case map."""

import json
import math
from html import escape

PH_MIN, PH_MAX = 6.65, 7.45

MALE_STOPS = ((0.00, "#1e3a8a"), (0.50, "#2563eb"), (1.00, "#93c5fd"))
FEMALE_STOPS = ((0.00, "#831843"), (0.50, "#ec4899"), (1.00, "#f9a8d4"))
MALE_FALLBACK, FEMALE_FALLBACK = "#2563eb", "#ec4899"

# The radius grows with sqrt(index) until this pin count.
JITTER_SATURATION_PINS = 90
METRES_PER_LATITUDE_DEGREE = 111_320
DEFAULT_JITTER_METRES = 450.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _hex_to_rgb(colour: str) -> tuple[int, int, int]:
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def _blend(start: str, end: str, position: float) -> str:
    channels = zip(_hex_to_rgb(start), _hex_to_rgb(end))
    return "#" + "".join(
        f"{round(low + (high - low) * position):02x}" for low, high in channels
    )


def ph_colour(ph: float, stops: tuple[tuple[float, str], ...]) -> str:
    normalised = (_clamp(ph, PH_MIN, PH_MAX) - PH_MIN) / (PH_MAX - PH_MIN)
    for index, (position, colour) in enumerate(stops[1:], start=1):
        previous_position, previous_colour = stops[index - 1]
        if normalised <= position:
            span = position - previous_position
            offset = (normalised - previous_position) / span if span else 0
            return _blend(previous_colour, colour, offset)
    return stops[-1][1]


def marker_colour(case: dict) -> str:
    female = case.get("sex") == "Female"
    stops = FEMALE_STOPS if female else MALE_STOPS
    try:
        return ph_colour(float(case["ph"]), stops)
    except (KeyError, TypeError, ValueError):
        return FEMALE_FALLBACK if female else MALE_FALLBACK


def spiral_offset(
    latitude: float,
    longitude: float,
    index: int,
    max_radius_metres: float = DEFAULT_JITTER_METRES,
) -> tuple[float, float]:
    """Place a pin on a bounded Vogel spiral."""
    if index <= 0:
        return round(latitude, 5), round(longitude, 5)
    step = max_radius_metres / math.sqrt(JITTER_SATURATION_PINS)
    angle = index * math.radians(137.5)
    radius = min(max_radius_metres, step * math.sqrt(index))
    north = radius * math.cos(angle)
    east = radius * math.sin(angle)
    return (
        round(latitude + north / METRES_PER_LATITUDE_DEGREE, 5),
        round(
            longitude
            + east / (METRES_PER_LATITUDE_DEGREE * math.cos(math.radians(latitude))),
            5,
        ),
    )


def pin_icon(colour: str) -> str:
    """A Leaflet divIcon expression for a teardrop pin in the given colour."""
    html = (
        '<div style="width:22px;height:22px;'
        f"background:{colour};"
        "border:2px solid white;"
        "border-radius:50% 50% 50% 0;"
        'box-shadow:0 2px 5px rgba(0,0,0,.35);'
        'transform:rotate(-45deg);">'
        '<div style="width:6px;height:6px;background:white;'
        'border-radius:50%;margin:6px 0 0 6px;"></div>'
        "</div>"
    )
    return (
        "L.divIcon({className:'',"
        f"html:{json.dumps(html)},"
        "iconSize:[26,34],iconAnchor:[13,26],popupAnchor:[0,-26]})"
    )


def popup_html(case: dict, severity_label: str, area_label: str) -> str:
    def value(key, suffix=""):
        raw = case.get(key)
        return "—" if raw in (None, "") else f"{escape(str(raw))}{suffix}"

    return "<br>".join([
        f"<b>Case {escape(str(case.get('id', '—')))}</b>",
        f"{escape(str(case.get('sex', '—')))}, age {value('age_at_onset')}",
        f"Onset: {case.get('month_of_onset', '—')}/{case.get('year_of_onset', '—')}",
        f"Severity: {escape(severity_label)}",
        f"pH {value('ph')} · bicarbonate {value('bicarbonate')} mmol/L",
        f"Glucose {value('glucose')} mg/dL · HbA1c {value('hba1c')}%",
        f"Symptom duration: {value('duration_of_symptoms', ' days')}",
        f"<span style='color:#64748b'>{escape(area_label)}</span>",
        "<i style='color:#64748b'>Position is scattered around the postcode "
        "centroid, not the patient's address</i>",
    ])
