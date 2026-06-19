import json

MALE_MARKER_COLOR = "#2563eb"
FEMALE_MARKER_COLOR = "#ec4899"
MAP_CENTER = (48.5, 9.0)


def marker_color(sex: str) -> str:
    return MALE_MARKER_COLOR if sex == "Male" else FEMALE_MARKER_COLOR


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
    marker.run_method(":setIcon", pin_icon_expression(marker_color(patient["sex"])))
    marker.run_method("bindPopup", patient_popup_html(patient))
    return marker
