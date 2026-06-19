from nicegui import ui, app
from services.map_markers import MAP_CENTER, create_patient_marker
from services.patient_filters import default_filters, patient_matches, year_range
from storage.patients_csv import load_patient_rows


@ui.page("/map")
def map_page():
    if not app.storage.user.get("role"):
        ui.navigate.to("/")
        return

    role = app.storage.user["role"]
    patients = load_patient_rows()
    filters = default_filters(patients)

    active_markers: list = []

    def refresh_markers(m, count_label):
        for marker in active_markers:
            marker.run_method("remove")
        active_markers.clear()

        matched = [p for p in patients if patient_matches(p, filters)]
        count_label.set_text(f"{len(matched)} cases shown")

        for p in matched:
            marker = create_patient_marker(m, p)
            if marker:
                active_markers.append(marker)

    # ── Layout ────────────────────────────────────────────────────────────
    with ui.row().classes("w-full h-screen gap-0 overflow-hidden"):

        # ── Sidebar ───────────────────────────────────────────────────────
        with ui.column().classes("w-72 h-full bg-gray-50 border-r overflow-y-auto p-4 gap-4 shrink-0"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Filters").classes("text-xl font-bold text-blue-700")
                ui.button(icon="logout", on_click=lambda: ui.navigate.to("/logout")) \
                    .props("flat round").tooltip("Log out")

            count_label = ui.label(f"{len(patients)} cases shown").classes("text-sm text-gray-500")

            with ui.row().classes("w-full items-center gap-4 text-xs text-gray-600"):
                with ui.row().classes("items-center gap-1"):
                    ui.icon("location_on", color="blue").classes("text-base")
                    ui.label("Male")
                with ui.row().classes("items-center gap-1"):
                    ui.icon("location_on", color="pink").classes("text-base")
                    ui.label("Female")

            def on_change():
                refresh_markers(map_widget, count_label)

            # ── Age ──
            with ui.card().classes("w-full p-3 gap-2"):
                ui.label("Age at onset").classes("font-semibold text-sm")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label("Min").classes("text-xs w-6")
                    age_min_input = ui.number(
                        value=1, min=1, max=48, step=1, format="%.0f",
                        on_change=lambda e: (filters.update(age_min=int(e.value or 1)), on_change()),
                    ).classes("flex-1")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label("Max").classes("text-xs w-6")
                    age_max_input = ui.number(
                        value=48, min=1, max=48, step=1, format="%.0f",
                        on_change=lambda e: (filters.update(age_max=int(e.value or 48)), on_change()),
                    ).classes("flex-1")

            # ── Sex ──
            with ui.card().classes("w-full p-3 gap-2"):
                ui.label("Sex").classes("font-semibold text-sm")
                sex_checks: dict[str, ui.checkbox] = {}

                def on_sex_change():
                    filters["sex"] = {s for s, cb in sex_checks.items() if cb.value}
                    on_change()

                for sex_val in ("Male", "Female"):
                    cb = ui.checkbox(sex_val, value=True, on_change=lambda _: on_sex_change())
                    sex_checks[sex_val] = cb

            # ── Year ──
            @ui.refreshable
            def year_filter_ui():
                y_min, y_max = year_range(patients)
                with ui.card().classes("w-full p-3 gap-1"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label("Year of onset").classes("font-semibold text-sm")
                        yr_label = ui.label(
                            f"{filters['year_min']} – {filters['year_max']}"
                        ).classes("text-xs text-gray-500")

                    def on_year_slider(e):
                        lo, hi = int(e.value["min"]), int(e.value["max"])
                        yr_label.set_text(f"{lo} – {hi}")
                        filters["year_min"] = lo
                        filters["year_max"] = hi
                        on_change()

                    ui.range(
                        min=y_min, max=y_max, step=1,
                        value={"min": filters["year_min"], "max": filters["year_max"]},
                        on_change=on_year_slider,
                    ).classes("w-full")

            year_filter_ui()

            # ── Blood glucose ──
            with ui.card().classes("w-full p-3 gap-2"):
                ui.label("Blood glucose (mg/dL)").classes("font-semibold text-sm")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label("Min").classes("text-xs w-6")
                    gluc_min = ui.number(
                        value=150, min=150, max=789, step=1, format="%.0f",
                        on_change=lambda e: (filters.update(glucose_min=float(e.value or 150)), on_change()),
                    ).classes("flex-1")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label("Max").classes("text-xs w-6")
                    gluc_max = ui.number(
                        value=789, min=150, max=789, step=1, format="%.0f",
                        on_change=lambda e: (filters.update(glucose_max=float(e.value or 789)), on_change()),
                    ).classes("flex-1")

            # ── pH ──
            with ui.card().classes("w-full p-3 gap-2"):
                ui.label("pH").classes("font-semibold text-sm")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label("Min").classes("text-xs w-6")
                    ph_min = ui.number(
                        value=6.65, min=6.65, max=7.35, step=0.01, format="%.2f",
                        on_change=lambda e: (filters.update(ph_min=float(e.value or 6.65)), on_change()),
                    ).classes("flex-1")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label("Max").classes("text-xs w-6")
                    ph_max = ui.number(
                        value=7.35, min=6.65, max=7.35, step=0.01, format="%.2f",
                        on_change=lambda e: (filters.update(ph_max=float(e.value or 7.35)), on_change()),
                    ).classes("flex-1")

            # ── Bicarbonate ──
            with ui.card().classes("w-full p-3 gap-2"):
                ui.label("Bicarbonate (mmol/L)").classes("font-semibold text-sm")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label("Min").classes("text-xs w-6")
                    bik_min = ui.number(
                        value=1.5, min=1.5, max=22.0, step=0.1, format="%.1f",
                        on_change=lambda e: (filters.update(bikarb_min=float(e.value or 1.5)), on_change()),
                    ).classes("flex-1")
                with ui.row().classes("items-center gap-2 w-full"):
                    ui.label("Max").classes("text-xs w-6")
                    bik_max = ui.number(
                        value=22.0, min=1.5, max=22.0, step=0.1, format="%.1f",
                        on_change=lambda e: (filters.update(bikarb_max=float(e.value or 22.0)), on_change()),
                    ).classes("flex-1")

            # ── Reset ──
            def reset_filters():
                y_min, y_max = year_range(patients)
                age_min_input.set_value(1)
                age_max_input.set_value(48)
                for cb in sex_checks.values():
                    cb.set_value(True)
                filters["year_min"] = y_min
                filters["year_max"] = y_max
                year_filter_ui.refresh()
                gluc_min.set_value(150)
                gluc_max.set_value(789)
                ph_min.set_value(6.65)
                ph_max.set_value(7.35)
                bik_min.set_value(1.5)
                bik_max.set_value(22.0)
                filters.update({
                    "age_min": 1, "age_max": 48,
                    "year_min": y_min, "year_max": y_max,
                    "sex": {"Male", "Female"},
                    "glucose_min": 150.0, "glucose_max": 789.0,
                    "ph_min": 6.65, "ph_max": 7.35,
                    "bikarb_min": 1.5, "bikarb_max": 22.0,
                })
                on_change()

            ui.button("Reset filters", on_click=reset_filters).classes("w-full bg-blue-600 text-white")

        # ── Map ───────────────────────────────────────────────────────────
        with ui.column().classes("flex-1 h-full gap-0"):
            with ui.row().classes("w-full items-center bg-blue-700 px-6 py-3"):
                ui.label("Diabete Ketoacidosis Analyses").classes("text-white text-2xl font-bold")
                ui.space()
                if role == "scientist":
                    ui.button("Add Data", icon="add_circle",
                              on_click=lambda: ui.navigate.to("/add_data")) \
                        .props("flat color=white")

            map_widget = ui.leaflet(center=MAP_CENTER, zoom=8).classes("w-full flex-1")
            map_widget.on("init", lambda _: refresh_markers(map_widget, count_label))
