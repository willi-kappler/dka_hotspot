from nicegui import app, ui

from services.map_markers import MAP_CENTER
from services.patient_aggregation import aggregate_by_region
from storage.patients_db import load_patient_rows

# Circle radius (pixels) grows with case count; capped so big regions stay readable.
MIN_RADIUS = 8
MAX_RADIUS = 34
RADIUS_PER_CASE = 3

# Count thresholds → fill color (low to high). Chosen as a simple traffic-light
# scale so a "hotspot" reads at a glance.
COLOR_STOPS = (
    (1, "#22c55e"),   # green
    (3, "#eab308"),   # yellow
    (6, "#f97316"),   # orange
    (10, "#ef4444"),  # red
)


def count_radius(count: int) -> int:
    return min(MAX_RADIUS, MIN_RADIUS + RADIUS_PER_CASE * count)


def count_color(count: int) -> str:
    color = COLOR_STOPS[0][1]
    for threshold, stop_color in COLOR_STOPS:
        if count >= threshold:
            color = stop_color
    return color


@ui.page("/hotspot")
def hotspot_page():
    if not app.storage.user.get("role"):
        ui.navigate.to("/")
        return

    patients = load_patient_rows()
    regions = aggregate_by_region(patients)

    with ui.column().classes("w-full h-screen gap-0"):
        with ui.row().classes("h-14 w-full items-center border-b border-gray-200 bg-white px-5 gap-3"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/map")) \
                .props("flat round").tooltip("Back to case map")
            with ui.column().classes("gap-0"):
                ui.label("DKA Hotspot Map").classes("text-base font-semibold text-gray-900")
                ui.label(f"{len(regions)} regions · {len(patients)} cases").classes("text-xs text-gray-500")
            ui.space()
            # Legend: circle size = number of cases, color = same, low to high.
            with ui.row().classes("items-center gap-3 text-xs text-gray-600"):
                ui.label("Cases per region:").classes("font-medium")
                for threshold, color in COLOR_STOPS:
                    with ui.row().classes("items-center gap-1"):
                        ui.html(
                            f'<span style="display:inline-block;width:12px;height:12px;'
                            f'border-radius:50%;background:{color};"></span>'
                        )
                        ui.label(f"{threshold}+")

        map_widget = ui.leaflet(center=MAP_CENTER, zoom=9).classes("w-full flex-1")

        def draw_regions():
            for region in regions:
                circle = map_widget.generic_layer(
                    name="circleMarker",
                    args=[
                        [region["lat"], region["lon"]],
                        {
                            "radius": count_radius(region["count"]),
                            "color": "white",
                            "weight": 2,
                            "fillColor": count_color(region["count"]),
                            "fillOpacity": 0.75,
                        },
                    ],
                )
                circle.run_method("bindPopup", f"<b>{region['region']}</b><br>{region['count']} cases")

        map_widget.on("init", lambda _: draw_regions())
