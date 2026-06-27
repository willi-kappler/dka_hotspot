import json

MALE_MARKER_COLOR = "#2563eb"
FEMALE_MARKER_COLOR = "#ec4899"
MAP_CENTER = (48.6536, 8.7020)
PH_MIN = 6.65
PH_MAX = 7.35
MALE_PH_COLOR_STOPS = (
    (0.00, "#1e3a8a"),
    (0.50, "#2563eb"),
    (1.00, "#93c5fd"),
)
FEMALE_PH_COLOR_STOPS = (
    (0.00, "#831843"),
    (0.50, "#ec4899"),
    (1.00, "#f9a8d4"),
)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    return (
        int(hex_color[1:3], 16),
        int(hex_color[3:5], 16),
        int(hex_color[5:7], 16),
    )


def interpolate_channel(start: int, end: int, position: float) -> int:
    return round(start + (end - start) * position)


def interpolate_color(start_color: str, end_color: str, position: float) -> str:
    start_red, start_green, start_blue = hex_to_rgb(start_color)
    end_red, end_green, end_blue = hex_to_rgb(end_color)
    return (
        f"#{interpolate_channel(start_red, end_red, position):02x}"
        f"{interpolate_channel(start_green, end_green, position):02x}"
        f"{interpolate_channel(start_blue, end_blue, position):02x}"
    )


def ph_gradient_color(ph: float, color_stops: tuple[tuple[float, str], ...]) -> str:
    normalized = (clamp(ph, PH_MIN, PH_MAX) - PH_MIN) / (PH_MAX - PH_MIN)

    for index, (stop_position, stop_color) in enumerate(color_stops[1:], start=1):
        previous_position, previous_color = color_stops[index - 1]
        if normalized <= stop_position:
            segment_position = (normalized - previous_position) / (stop_position - previous_position)
            return interpolate_color(previous_color, stop_color, segment_position)

    return color_stops[-1][1]


def marker_color(patient: dict) -> str:
    color_stops = MALE_PH_COLOR_STOPS if patient.get("sex") == "Male" else FEMALE_PH_COLOR_STOPS
    try:
        ph = float(patient["ph"])
    except (ValueError, KeyError):
        return MALE_MARKER_COLOR if patient.get("sex") == "Male" else FEMALE_MARKER_COLOR
    return ph_gradient_color(ph, color_stops)


def pin_icon_expression(color: str) -> str:
    html = (
        "<div style=\""
        "width:24px;height:24px;"
        f"background:{color};"
        "border:2px solid white;"
        "border-radius:50% 50% 50% 0;"
        "box-shadow:0 2px 6px rgba(0,0,0,.35);"
        "transform:rotate(-45deg);"
        "\">"
        "<div style=\""
        "width:7px;height:7px;"
        "background:white;"
        "border-radius:50%;"
        "margin:7px 0 0 7px;"
        "\"></div>"
        "</div>"
    )
    return (
        "L.divIcon({"
        "className: '',"
        f"html: {json.dumps(html)},"
        "iconSize: [28, 36],"
        "iconAnchor: [14, 28],"
        "popupAnchor: [0, -28]"
        "})"
    )


def patient_popup_html(patient: dict) -> str:
    return (
        f"<b>Age:</b> {patient['age at onset']}<br>"
        f"<b>Sex:</b> {patient['sex']}<br>"
        f"<b>Year:</b> {patient['year of onset']}<br>"
        f"<b>Glucose:</b> {patient['glucose']} mg/dL<br>"
        f"<b>pH:</b> {patient['ph']}<br>"
        f"<b>Bicarbonate:</b> {patient['bikarb']}"
    )


def create_patient_marker(map_widget, patient: dict):
    try:
        lat = float(patient["lat"])
        lon = float(patient["lon"])
    except (ValueError, KeyError):
        return None

    marker = map_widget.marker(latlng=(lat, lon))
    marker.run_method(":setIcon", pin_icon_expression(marker_color(patient)))
    marker.run_method("bindPopup", patient_popup_html(patient))
    return marker
