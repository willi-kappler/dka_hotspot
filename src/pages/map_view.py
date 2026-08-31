"""Scientist case map."""

from html import escape

from nicegui import ui

from pages.shared import header, notice, require
from services.deprivation import mean_score, tertile_for
from services.epidemiology import SEVERITY_ORDER, severity, split_manifestations
from services.geography import (
    KREISE_WITHOUT_CLINIC,
    clinics_on_map,
    kreis_name,
    paediatric_practices,
    pilot_boundaries,
    pilot_view,
    plz5_centroids,
    plz5_jitter_radius,
    plz5_kreis,
    plz5_label,
    plz5_outside_region,
)
from services.markers import (
    FEMALE_STOPS,
    MALE_STOPS,
    marker_colour,
    pin_icon,
    popup_html,
    spiral_offset,
)
from storage.cases_db import load_cases

# Maximum number of readable pins.
MAX_PINS = 1200

CAPTION = "text-xs text-slate-500 leading-relaxed"

# A4 landscape, 12 mm margins, minus the caption block: 273 x 145 mm of map.
# The pixel pair is the same box at 96 dpi and is what the map is resized to
# on screen before printing — see PRINT_JS.
PRINT_MAP_MM = (273, 145)
PRINT_MAP_PX = (1032, 548)

# Two rule sets for one layout. The ``at-printing`` block applies on screen
# while the sheet is prepared, so Leaflet actually reflows and fetches tiles at
# the printed size; the ``@media print`` block is the page itself. Sizing only
# in @media print was the bug: the map kept its screen layout and got stretched
# into the print box, clipping the right edge.
PRINT_CSS = """
.print-only { display: none; }

body.at-printing .at-sheet,
body.at-printing .at-map-frame {
    height: auto !important; min-height: 0 !important; display: block !important;
}
body.at-printing .print-map {
    width: %dpx !important; height: %dpx !important; flex: none !important;
}

@media print {
    @page { size: A4 landscape; margin: 12mm; }
    html, body, .q-layout, .q-page-container, .q-page, .nicegui-content,
    .at-sheet, .at-map-frame {
        height: auto !important; min-height: 0 !important; overflow: visible !important;
        background: #fff !important;
    }
    .no-print { display: none !important; }
    .print-only { display: block !important; }
    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    .print-map {
        width: %dmm !important; height: %dmm !important; flex: none !important;
    }
    .leaflet-control-container, .leaflet-marker-shadow { display: none !important; }
    /* Stacked drop shadows read as grey smudges where pins crowd. */
    .leaflet-marker-icon div { box-shadow: none !important; }
}
""" % (PRINT_MAP_PX + PRINT_MAP_MM)

# Resize on screen, let Leaflet settle and fetch tiles for that box, then print.
# The hard cap matters because a tile that 404s never fires ``load``.
PRINT_JS = """
const el = getElement(%d);
const map = el.map;
document.body.classList.add('at-printing');
map.invalidateSize();
await new Promise(r => setTimeout(r, 200));
await new Promise(resolve => {
    let settled = false;
    const done = () => { if (!settled) { settled = true; resolve(); } };
    let waiting = 0;
    map.eachLayer(layer => {
        if (layer instanceof L.TileLayer) { waiting += 1; layer.once('load', done); }
    });
    if (waiting === 0) { done(); }
    setTimeout(done, 4000);
});
await new Promise(r => setTimeout(r, 150));
window.print();
document.body.classList.remove('at-printing');
map.invalidateSize();
"""

@ui.page("/map")
def map_page():
    if not require("scientist", "admin"):
        return

    ui.add_css(PRINT_CSS)

    loaded_cases = load_cases()
    eligibility = split_manifestations(loaded_cases)
    cases = eligibility["eligible"]
    centroids = plz5_centroids()
    years = sorted({case["year_of_onset"] for case in cases}) or [2014, 2025]

    filters = {
        "year_min": years[0],
        "year_max": years[-1],
        "sexes": {"Male", "Female"},
        "age_min": 0,
        "age_max": 19,
        "severities": set(SEVERITY_ORDER),
        "dka_only": True,
    }
    overlays = {"clinics": True, "practices": False}
    circles: list = []
    markers: list = []

    with ui.column().classes("w-full h-screen gap-0 at-sheet"):
        header("Case map", "One pin per case · colour by sex, depth by pH")

        with ui.column().classes("w-full print-only gap-1 pb-2"):
            ui.label(
                "DKA at type 1 manifestation — Tübingen, Reutlingen, Zollernalbkreis"
            ).classes("text-lg font-bold text-slate-900")
            print_caption = ui.label().classes("text-xs text-slate-700")
            with ui.row().classes("items-center gap-5 pt-1"):
                for legend_label, legend_stops in (("Male", MALE_STOPS), ("Female", FEMALE_STOPS)):
                    with ui.row().classes("items-center gap-2"):
                        legend_gradient = ", ".join(
                            f"{colour} {position * 100:.0f}%"
                            for position, colour in reversed(legend_stops)
                        )
                        ui.html(
                            f'<span style="display:inline-block;width:56px;height:12px;'
                            f'border:1px solid #cbd5e1;border-radius:2px;'
                            f'background:linear-gradient(to right, {legend_gradient})"></span>'
                        )
                        ui.label(legend_label).classes("text-xs text-slate-600")
                ui.label("Darker is a lower pH.").classes("text-xs text-slate-600")
            ui.label(
                "Pin positions are scattered around the postcode centroid and are "
                "not patient addresses. Zollernalbkreis (dashed) has no "
                "participating clinic, so its cases are not comparable."
            ).classes("text-xs text-slate-600")

        if eligibility["unknown_new_onset"]:
            with ui.column().classes("w-full max-w-3xl mx-auto p-8"):
                notice(
                    f"{len(eligibility['unknown_new_onset'])} records have unknown "
                    "new-onset status. Resolve them before mapping manifestations.",
                    tone="blocked",
                )
            return

        if not loaded_cases:
            with ui.column().classes("w-full max-w-3xl mx-auto p-8"):
                notice("No cases loaded. Import them under Data.", tone="blocked")
            return

        if not cases:
            with ui.column().classes("w-full max-w-3xl mx-auto p-8"):
                notice("No confirmed first manifestations are available.", tone="blocked")
            return

        if not centroids:
            with ui.column().classes("w-full max-w-3xl mx-auto p-8"):
                notice(
                    "No postcode coordinates are loaded, so the map cannot be "
                    "drawn. Run scripts/build_plz5_coordinates.py.",
                    tone="blocked",
                )
            return

        with ui.row().classes("w-full flex-1 min-h-0 gap-0 at-map-frame"):
            with ui.column().classes(
                "w-72 h-full shrink-0 overflow-y-auto border-r border-slate-200 "
                "bg-white px-5 py-4 gap-4 no-print"
            ):
                count_label = ui.label().classes("text-sm font-medium text-slate-700")
                too_many = ui.label().classes(
                    "text-xs text-amber-800 bg-amber-50 rounded p-2 leading-relaxed"
                )
                too_many.set_visibility(False)

                ui.label("Period").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-500"
                )
                with ui.row().classes("w-full justify-between"):
                    year_low = ui.label(str(years[0])).classes("text-xs text-slate-500")
                    year_high = ui.label(str(years[-1])).classes("text-xs text-slate-500")

                def on_years(event):
                    filters["year_min"] = int(event.value["min"])
                    filters["year_max"] = int(event.value["max"])
                    year_low.set_text(str(filters["year_min"]))
                    year_high.set_text(str(filters["year_max"]))
                    refresh()

                ui.range(
                    min=years[0], max=years[-1], step=1,
                    value={"min": years[0], "max": years[-1]}, on_change=on_years,
                ).props("color=blue-7 thumb-size=18px").classes("w-full px-1")

                ui.label("Age at onset").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-500"
                )
                with ui.row().classes("w-full justify-between"):
                    age_low = ui.label("0").classes("text-xs text-slate-500")
                    age_high = ui.label("19").classes("text-xs text-slate-500")

                def on_ages(event):
                    filters["age_min"] = int(event.value["min"])
                    filters["age_max"] = int(event.value["max"])
                    age_low.set_text(str(filters["age_min"]))
                    age_high.set_text(str(filters["age_max"]))
                    refresh()

                ui.range(
                    min=0, max=19, step=1, value={"min": 0, "max": 19},
                    on_change=on_ages,
                ).props("color=blue-7 thumb-size=18px").classes("w-full px-1")

                ui.label("Sex").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-500"
                )
                sex_boxes = {}
                with ui.row().classes("w-full gap-2"):
                    for sex in ("Male", "Female"):
                        def on_sex(_, value=sex):
                            if sex_boxes[value].value:
                                filters["sexes"].add(value)
                            else:
                                filters["sexes"].discard(value)
                            refresh()
                        sex_boxes[sex] = ui.checkbox(
                            sex, value=True, on_change=on_sex
                        ).props("dense").classes("flex-1")

                ui.label("DKA severity").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-500"
                )
                severity_boxes = {}
                for level in SEVERITY_ORDER:
                    def on_severity(_, value=level):
                        if severity_boxes[value].value:
                            filters["severities"].add(value)
                        else:
                            filters["severities"].discard(value)
                        refresh()
                    severity_boxes[level] = ui.checkbox(
                        level, value=True, on_change=on_severity
                    ).props("dense")

                def on_dka_only(event):
                    filters["dka_only"] = bool(event.value)
                    refresh()

                ui.switch(
                    "Ketoacidosis only", value=True, on_change=on_dka_only
                ).props("dense").classes("text-sm")
                ui.label(
                    "Off includes manifestations that did not meet the "
                    "biochemical threshold."
                ).classes(CAPTION)

                ui.separator()
                ui.label("Overlays").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-500"
                )

                def on_overlay(key):
                    def handler(event):
                        overlays[key] = bool(event.value)
                        refresh()
                    return handler

                ui.checkbox("Hospitals", value=True, on_change=on_overlay("clinics")) \
                    .props("dense")
                ui.checkbox("Paediatric practices", value=False,
                            on_change=on_overlay("practices")).props("dense")

                ui.separator()
                ui.label("Pin colour").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-500"
                )
                for label, stops in (("Male", MALE_STOPS), ("Female", FEMALE_STOPS)):
                    with ui.row().classes("items-center gap-2"):
                        gradient = ", ".join(
                            f"{colour} {position * 100:.0f}%"
                            for position, colour in reversed(stops)
                        )
                        ui.html(
                            f'<span style="display:inline-block;width:56px;height:12px;'
                            f'border:1px solid #cbd5e1;border-radius:2px;'
                            f'background:linear-gradient(to right, {gradient})"></span>'
                        )
                        ui.label(label).classes("text-xs text-slate-600")
                ui.label(
                    "Darker means lower pH, so a deeper pin is a child who "
                    "arrived more acidotic."
                ).classes(CAPTION)

                ui.label(
                    "Each pin is one case, scattered around its postcode "
                    "centroid — a drawn position, never an address."
                ).classes(CAPTION)

                ui.separator()

                async def print_map():
                    await ui.run_javascript(PRINT_JS % map_widget.id, timeout=15)

                ui.button("Print map", icon="print", on_click=print_map) \
                    .props("outline dense").classes("w-full text-blue-700")

            centre, zoom = pilot_view()
            map_widget = ui.leaflet(center=centre, zoom=zoom).classes("h-full flex-1 print-map")

    def selected() -> list[dict]:
        chosen = []
        for case in cases:
            level = severity(case)
            if filters["dka_only"] and level not in SEVERITY_ORDER:
                continue
            if level in SEVERITY_ORDER and level not in filters["severities"]:
                continue
            if case["sex"] not in filters["sexes"]:
                continue
            if not filters["year_min"] <= case["year_of_onset"] <= filters["year_max"]:
                continue
            if not filters["age_min"] <= case["age_at_onset"] <= filters["age_max"]:
                continue
            chosen.append(case)
        return chosen

    def area_label(plz5: str) -> str:
        district = kreis_name(plz5_kreis(plz5)) or "—"
        score = mean_score(plz5, filters["year_min"], filters["year_max"])
        tertile = tertile_for(plz5, filters["year_min"], filters["year_max"])
        text = f"{plz5_label(plz5)} · {district}"
        if score is not None:
            band = {1: "lower", 2: "middle", 3: "higher"}.get(tertile, "—")
            text += f" · GISD {score:.3f} ({band})"
        if plz5 in plz5_outside_region():
            text += " · centroid falls outside the district polygons"
        return text

    def clear(collection: list):
        for layer in collection:
            layer.run_method("remove")
        collection.clear()

    def refresh():
        chosen = selected()
        mappable = [
            case for case in chosen
            if case.get("plz5") and case["plz5"] in centroids
        ]
        unplaced = len(chosen) - len(mappable)
        areas = len({case["plz5"] for case in mappable})
        count_label.set_text(
            f"{len(chosen)} of {len(cases)} cases · {areas} postcode areas"
            + (f" · {unplaced} without a mappable postcode" if unplaced else "")
        )

        # The paper copy has no sidebar, so it has to carry its own filter state
        # or a reader cannot tell what subset they are looking at.
        severities = (
            "all severities" if filters["severities"] == set(SEVERITY_ORDER)
            else ", ".join(sorted(filters["severities"])) or "none"
        )
        sexes = "both sexes" if len(filters["sexes"]) == 2 else (
            ", ".join(sorted(filters["sexes"])) or "no sex selected"
        )
        print_caption.set_text(
            f"{len(mappable)} cases plotted of {len(cases)} confirmed first "
            f"manifestations · {areas} postcode areas · "
            f"{filters['year_min']}–{filters['year_max']} · ages "
            f"{filters['age_min']}–{filters['age_max']} · {sexes} · {severities}"
            + (", ketoacidosis only" if filters["dka_only"] else ", including non-DKA")
            + (f" · {unplaced} not mappable" if unplaced else "")
        )

        clear(circles)
        if len(mappable) > MAX_PINS:
            too_many.set_text(
                f"{len(mappable)} pins is too many to draw legibly. "
                "Narrow the period, age range or severity."
            )
            too_many.set_visibility(True)
            return
        too_many.set_visibility(False)

        placed_per_area: dict[str, int] = {}
        for case in mappable:
            plz5 = case["plz5"]
            index = placed_per_area.get(plz5, 0)
            placed_per_area[plz5] = index + 1
            latitude, longitude = spiral_offset(
                *centroids[plz5], index, plz5_jitter_radius(plz5)
            )

            pin = map_widget.marker(latlng=(latitude, longitude))
            pin.run_method(":setIcon", pin_icon(marker_colour(case)))
            pin.run_method(
                "bindPopup", popup_html(case, severity(case), area_label(plz5))
            )
            circles.append(pin)

        clear(markers)
        if overlays["clinics"]:
            for hospital in clinics_on_map():
                marker = map_widget.generic_layer(
                    name="circleMarker",
                    args=[
                        {"lat": hospital["lat"], "lng": hospital["lon"]},
                        {
                            "radius": 7,
                            "color": "#0f766e" if hospital["participating"] else "#b91c1c",
                            "weight": 2,
                            "fillColor": "#ffffff",
                            "fillOpacity": 1,
                        },
                    ],
                )
                marker.run_method(
                    "bindTooltip",
                    f"<b>{escape(hospital['name'])}</b><br>{escape(hospital['city'])}<br>"
                    + ("Participating Ambulanz" if hospital["participating"]
                       else "<i>Not participating — its cases are not captured</i>"),
                )
                markers.append(marker)

        if overlays["practices"]:
            for practice in paediatric_practices():
                marker = map_widget.generic_layer(
                    name="circleMarker",
                    args=[
                        {"lat": practice["lat"], "lng": practice["lon"]},
                        {
                            "radius": 3,
                            "color": "#64748b",
                            "weight": 1,
                            "fillColor": "#94a3b8",
                            "fillOpacity": 0.8,
                        },
                    ],
                )
                marker.run_method(
                    "bindTooltip",
                    f"{escape(practice['name'])}<br>"
                    f"{escape(practice['postcode'])} {escape(practice['city'])}",
                )
                markers.append(marker)

    def draw():
        for feature in pilot_boundaries()["features"]:
            ags = str(feature["properties"]["AGS"]).zfill(5)
            map_widget.generic_layer(
                name="geoJSON",
                args=[feature, {"style": {
                    "color": "#64748b",
                    "weight": 1.4,
                    "fillColor": "#f8fafc",
                    "fillOpacity": 0.35,
                    "dashArray": "4" if ags in KREISE_WITHOUT_CLINIC else None,
                }}],
            )
        refresh()

    map_widget.on("init", lambda _: draw())
