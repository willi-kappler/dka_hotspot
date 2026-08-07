from nicegui import app, ui

from services.map_markers import MAP_CENTER, create_patient_marker
from services.patient_export import patients_to_csv
from services.patient_filters import (
    AGE_MAX,
    AGE_MIN,
    BIKARB_MAX,
    BIKARB_MIN,
    GLUCOSE_MAX,
    GLUCOSE_MIN,
    PH_MAX,
    PH_MIN,
    default_filters,
    patient_matches,
    year_range,
)
from storage.patients_db import load_patient_rows

# Hides the sidebar/header chrome and lets the map take over the whole
# printed page, instead of printing whatever the on-screen layout happens to be.
PRINT_STYLE = """
<style>
@media print {
    /* Browsers drop background colors by default when printing (to save ink) —
       this forces them to print exactly as shown, so the colored marker pins
       don't come out blank/white. */
    * {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
        color-adjust: exact !important;
    }
    .no-print { display: none !important; }
    .print-target {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        margin: 0 !important;
    }
}
</style>
"""


@ui.page("/map")
def map_page():
    if not app.storage.user.get("role"):
        ui.navigate.to("/")
        return

    ui.add_head_html(PRINT_STYLE)

    role = app.storage.user["role"]
    username = app.storage.user.get("username", role)
    patients = load_patient_rows()
    filters = default_filters(patients)
    y_min, y_max = year_range(patients)

    active_markers: list = []

    def refresh_markers(m, count_label):
        for marker in active_markers:
            marker.run_method("remove")
        active_markers.clear()

        matched = [p for p in patients if patient_matches(p, filters)]
        count_label.set_text(f"{len(matched)} of {len(patients)} cases shown")

        for p in matched:
            marker = create_patient_marker(m, p)
            if marker:
                active_markers.append(marker)

    def filter_shell(title: str):
        with ui.column().classes("w-full gap-2 border-b border-gray-200 pb-4"):
            ui.label(title).classes("text-xs font-semibold uppercase text-gray-500")
            return ui.column().classes("w-full gap-2")

    def filter_number(label: str, **props):
        with ui.column().classes("gap-1 flex-1 min-w-0"):
            ui.label(label).classes("text-[11px] font-medium text-gray-500")
            return ui.number(**props).props("dense outlined").classes("w-full")

    def on_change():
        refresh_markers(map_widget, count_label)

    range_widgets: dict[str, tuple] = {}

    def add_range_filter(key: str, title: str, low, high, step, decimals: int, value_type, unit: str | None = None):
        fmt = f"%.{decimals}f"
        with filter_shell(title):
            if unit:
                ui.label(unit).classes("text-xs text-gray-400")
            with ui.row().classes("w-full gap-2"):
                min_widget = filter_number(
                    "Min", value=low, min=low, max=high, step=step, format=fmt,
                    on_change=lambda e, k=key, lo=low, vt=value_type: (
                        filters.update({f"{k}_min": vt(e.value or lo)}), on_change(),
                    ),
                )
                max_widget = filter_number(
                    "Max", value=high, min=low, max=high, step=step, format=fmt,
                    on_change=lambda e, k=key, hi=high, vt=value_type: (
                        filters.update({f"{k}_max": vt(e.value or hi)}), on_change(),
                    ),
                )
        range_widgets[key] = (min_widget, max_widget)

    RANGE_FILTER_SPECS = [
        ("age", "Age at onset", AGE_MIN, AGE_MAX, 1, 0, int, None),
        ("ph", "pH", PH_MIN, PH_MAX, 0.01, 2, float, None),
        ("bikarb", "Bicarbonate", BIKARB_MIN, BIKARB_MAX, 0.1, 1, float, "mmol/L"),
        ("glucose", "Glucose", GLUCOSE_MIN, GLUCOSE_MAX, 1, 0, float, "mg/dL"),
        #("year", "Year of onset", y_min, y_max, 1, 0, int, None),  # min/max number inputs (current)
        # To try the slider version instead: comment out the "year" line above,
    ]

    with ui.row().classes("w-full h-screen gap-0 overflow-hidden bg-gray-100"):
        with ui.column().classes("no-print w-80 h-full shrink-0 overflow-y-auto border-r border-gray-200 bg-white px-5 py-4 gap-5"):
            with ui.column().classes("gap-1"):
                ui.label("DKA Hotspot Map").classes("text-xl font-semibold text-gray-900")
                count_label = ui.label(f"{len(patients)} of {len(patients)} cases shown").classes("text-sm text-gray-500")

            with ui.column().classes("gap-2 rounded-md bg-gray-50 p-3"):
                ui.label("Marker legend").classes("text-xs font-semibold uppercase text-gray-500")
                with ui.row().classes("items-center gap-4 text-xs text-gray-700"):
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("location_on", color="blue").classes("text-base")
                        ui.label("Male")
                    with ui.row().classes("items-center gap-1"):
                        ui.icon("location_on", color="pink").classes("text-base")
                        ui.label("Female")
                #ui.label("Lower pH appears darker within each color.").classes("text-xs text-gray-500")
            
            
            #add_range_filter("age", "Age at onset", AGE_MIN, AGE_MAX, 1, 0, int)

            with filter_shell("Sex"):
                sex_checks: dict[str, ui.checkbox] = {}

                def on_sex_change():
                    filters["sex"] = {s for s, cb in sex_checks.items() if cb.value}
                    on_change()

                with ui.row().classes("w-full gap-2"):
                    for sex_val in ("Male", "Female"):
                        cb = ui.checkbox(sex_val, value=True, on_change=lambda _: on_sex_change())
                        cb.props("dense").classes("flex-1 rounded-md border border-gray-200 px-2 py-1")
                        sex_checks[sex_val] = cb

            for key, title, low, high, step, decimals, value_type, unit in RANGE_FILTER_SPECS:
                add_range_filter(key, title, low, high, step, decimals, value_type, unit)

            # --- Alternative "Year of onset" filter: two-handle slider ---
            # Disabled for now. To switch to this version: comment out the
            # ("year", ...) line in RANGE_FILTER_SPECS above, then uncomment
            # this whole block plus the two lines it needs in reset_filters below.
            
            with filter_shell("Year of onset"):
                # Left/right labels track the currently selected min/max year and
                # update live as the handles move — no separate static readout needed.
                with ui.row().classes("w-full items-center justify-between"):
                    year_min_label = ui.label(str(y_min)).classes("text-xs font-medium text-gray-400")
                    year_max_label = ui.label(str(y_max)).classes("text-xs font-medium text-gray-400")

                def on_year_slider_change(e):
                    # ui.range's on_change event gives e.value as {'min': ..., 'max': ...}
                    # rather than a single number, because it has two draggable handles.
                    year_min = int(e.value["min"])
                    year_max = int(e.value["max"])
                    filters.update(year_min=year_min, year_max=year_max)
                    year_min_label.set_text(str(year_min))
                    year_max_label.set_text(str(year_max))
                    on_change()  # re-filter the map markers with the new year range

                year_slider = ui.range(
                    min=y_min,
                    max=y_max,
                    step=1,
                    value={"min": y_min, "max": y_max},  # start with the full range selected
                    on_change=on_year_slider_change,
                ).props('color=blue-7 thumb-size=18px track-size=6px').classes("w-full px-1")

            def reset_filters():
                fresh = default_filters(patients)
                for cb in sex_checks.values():
                    cb.set_value(True)
                for key, (min_widget, max_widget) in range_widgets.items():
                    min_widget.set_value(fresh[f"{key}_min"])
                    max_widget.set_value(fresh[f"{key}_max"])
                # If using the slider version above, uncomment these lines
                # (and comment out the "year" line in RANGE_FILTER_SPECS instead):
                # year_slider.set_value({"min": fresh["year_min"], "max": fresh["year_max"]})
                # year_min_label.set_text(str(fresh["year_min"]))
                # year_max_label.set_text(str(fresh["year_max"]))
                filters.clear()
                filters.update(fresh)
                on_change()

            ui.button("Reset filters", icon="restart_alt", on_click=reset_filters) \
                .props("outline").classes("w-full text-gray-700")

            def export_csv():
                matched = [p for p in patients if patient_matches(p, filters)]
                csv_bytes = patients_to_csv(matched)
                ui.download(csv_bytes, filename="dka_filtered_cases.csv", media_type="text/csv")

            # --- Original: stacked full-width buttons ---
            ui.button("Export CSV", icon="download", on_click=export_csv) \
                .props("outline").classes("w-full text-gray-700")
            
            ui.button("Print map", icon="print", on_click=lambda: ui.run_javascript("window.print()")) \
                .props("outline").classes("w-full text-gray-700")

            # # --- Alternative: side by side, compact ---
            # with ui.row().classes("w-full gap-2"):
            #     ui.button("Export CSV", icon="download", on_click=export_csv) \
            #         .props("outline dense size=sm").classes("flex-1 text-gray-700")
            #     ui.button("Print", icon="print", on_click=lambda: ui.run_javascript("window.print()")) \
            #         .props("outline dense size=sm").classes("flex-1 text-gray-700")

        with ui.column().classes("flex-1 h-full gap-0"):
            with ui.row().classes("no-print h-14 w-full items-center border-b border-gray-200 bg-white px-5 gap-2"):
                with ui.column().classes("gap-0"):
                    ui.label("Diabetic Ketoacidosis Analysis").classes("text-base font-semibold text-gray-900")
                    ui.label(f"Signed in as {username} ({role})").classes("text-xs text-gray-500")
                ui.space()
                ui.button("Hotspots", icon="local_fire_department",
                          on_click=lambda: ui.navigate.to("/hotspot")) \
                    .props("flat").classes("text-blue-700")
                if role in {"scientist", "admin"}:
                    ui.button("Add Data", icon="add_circle",
                              on_click=lambda: ui.navigate.to("/add_data")) \
                        .props("flat").classes("text-blue-700")
                if role == "admin":
                    ui.button("Cases", icon="edit_note",
                              on_click=lambda: ui.navigate.to("/admin/cases")) \
                        .props("flat").classes("text-blue-700")
                    ui.button("Users", icon="admin_panel_settings",
                              on_click=lambda: ui.navigate.to("/admin/users")) \
                        .props("flat").classes("text-blue-700")
                ui.button(icon="logout", on_click=lambda: ui.navigate.to("/logout")) \
                    .props("flat round").classes("text-gray-600").tooltip("Log out")

            map_widget = ui.leaflet(center=MAP_CENTER, zoom=9).classes("w-full flex-1 print-target")
            map_widget.on("init", lambda _: refresh_markers(map_widget, count_label))

            # Leaflet caches the map's pixel size at load time and has no idea our
            # print CSS just resized its container to fill the page — without this,
            # it only renders tiles for the original on-screen size, leaving the
            # rest of the printed page blank. `beforeprint`/`afterprint` are native
            # browser events that fire right as the print layout kicks in/out, so
            # we nudge Leaflet to recompute its size at exactly those moments.
            ui.run_javascript(f"""
                window.addEventListener('beforeprint', () => {{
                    const el = getElement({map_widget.id});
                    if (el && el.map) el.map.invalidateSize();
                }});
                window.addEventListener('afterprint', () => {{
                    const el = getElement({map_widget.id});
                    if (el && el.map) el.map.invalidateSize();
                }});
            """)
