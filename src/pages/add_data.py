import logging

from nicegui import app, events, ui

from services.geocoding import geocode_patient_row
from storage.patients_db import (
    REQUIRED_COLUMNS,
    append_patient_rows,
    coords_by_zipcode,
    parse_patient_csv,
)

logger = logging.getLogger(__name__)


def zipcode_key(row: dict) -> tuple[str, str]:
    return row.get("zipcode", "").strip(), row.get("state", "").strip()


@ui.page("/add_data")
def add_data_page():
    if app.storage.user.get("role") not in {"scientist", "admin"}:
        ui.navigate.to("/")
        return

    def field_number(label: str, **props):
        return ui.number(label, **props).props("outlined dense").classes("w-full")

    def field_input(label: str, **props):
        return ui.input(label, **props).props("outlined dense").classes("w-full")

    def section(title: str):
        with ui.column().classes("w-full gap-3 border-b border-gray-100 pb-5"):
            ui.label(title).classes("text-xs font-semibold uppercase text-gray-500")
            return ui.grid(columns=2).classes("w-full gap-3")

    with ui.column().classes("w-full min-h-screen gap-0 bg-gray-50"):
        with ui.row().classes("h-14 w-full items-center border-b border-gray-200 bg-white px-6 gap-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/map")) \
                .props("flat round").tooltip("Back to map")
            with ui.column().classes("gap-0"):
                ui.label("Add Data").classes("text-lg font-semibold text-gray-900")
                ui.label("Create one case or import a CSV file into the database.").classes("text-xs text-gray-500")

        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-6"):
            with ui.card().classes("w-full p-0 gap-0"):
                with ui.tabs().classes("w-full border-b border-gray-200") as tabs:
                    tab_single = ui.tab("Single record", icon="person_add")
                    tab_csv = ui.tab("Upload CSV", icon="upload_file")

                with ui.tab_panels(tabs, value=tab_single).classes("w-full"):
                    with ui.tab_panel(tab_single):
                        with ui.column().classes("w-full gap-5 p-5"):
                            notice = ui.label("").classes("text-sm")
                            ui.label("* Required fields. Optional fields can be left blank.") \
                                .classes("text-xs text-gray-500")

                            with section("Patient"):
                                age = field_number("Age at onset *", min=0, max=120, step=1, format="%.0f")
                                sex = ui.select(["Male", "Female"], label="Sex *").props("outlined dense").classes("w-full")

                            with section("Onset"):
                                year = field_number("Year of onset *", min=1900, max=2100, step=1, format="%.0f")
                                month = field_number("Month of onset *", min=1, max=12, step=1, format="%.0f")
                                dur = field_number("Duration of symptoms (days, optional)", min=0, step=1, format="%.0f")

                            with section("Lab values"):
                                gluc = field_number("Glucose (mg/dL) *", min=0, step=1, format="%.0f")
                                a1c = field_number("HbA1c (%, optional)", min=0, max=20, step=0.1, format="%.1f")
                                ph = field_number("pH *", min=6.0, max=8.0, step=0.01, format="%.2f")
                                bik = field_number("Bicarbonate (mmol/L) *", min=0, max=40, step=0.1, format="%.1f")

                            with section("Location"):
                                zipcode = field_input("ZIP code *")
                                state = field_input("State *")

                            def save_single():
                                required = [age, year, month, gluc, ph, bik, sex, zipcode, state]
                                if any(f.value is None or f.value == "" for f in required):
                                    notice.set_text("Please fill in all required fields.")
                                    notice.classes("text-red-500", remove="text-green-600")
                                    return
                                try:
                                    row_data = {
                                        "age at onset": int(age.value),
                                        "sex": sex.value,
                                        "zipcode": zipcode.value,
                                        "state": state.value,
                                        "month of onset": int(month.value),
                                        "year of onset": int(year.value),
                                        "a1c": round(float(a1c.value), 1) if a1c.value else "",
                                        "glucose": int(gluc.value),
                                        "bikarb": round(float(bik.value), 1),
                                        "ph": round(float(ph.value), 2),
                                        "duration of symptoms": int(dur.value) if dur.value else "",
                                    }
                                    occupied = coords_by_zipcode().get(zipcode_key(row_data), set())
                                    row = geocode_patient_row(row_data, occupied)
                                    append_patient_rows([row])
                                    notice.set_text("Record saved to database.")
                                    notice.classes("text-green-600", remove="text-red-500")
                                    for field in [age, year, month, dur, gluc, a1c, ph, bik]:
                                        field.set_value(None)
                                    sex.set_value(None)
                                    zipcode.set_value("")
                                    state.set_value("")
                                except (ValueError, RuntimeError) as ex:
                                    notice.set_text(str(ex))
                                    notice.classes("text-red-500", remove="text-green-600")
                                except Exception:
                                    logger.exception("Failed to save patient record")
                                    notice.set_text("Could not save record. Please try again.")
                                    notice.classes("text-red-500", remove="text-green-600")

                            with ui.row().classes("w-full justify-end"):
                                ui.button("Save record", icon="save", on_click=save_single) \
                                    .classes("bg-blue-700 text-white")

                    with ui.tab_panel(tab_csv):
                        with ui.column().classes("w-full gap-5 p-5"):
                            csv_notice = ui.label("").classes("text-sm")

                            with ui.column().classes("w-full gap-2 rounded-md bg-gray-50 p-4"):
                                ui.label("CSV import").classes("text-sm font-semibold text-gray-900")
                                ui.label(
                                    "Required columns: " + ", ".join(sorted(REQUIRED_COLUMNS - {"a1c"}))
                                ).classes("text-xs text-gray-500")
                                ui.label("HbA1c and duration of symptoms may be blank; all other values are required.") \
                                    .classes("text-xs text-gray-500")

                            def handle_upload(e: events.UploadEventArguments):
                                try:
                                    content = e.content.read().decode("utf-8")
                                    rows = parse_patient_csv(content)
                                    occupied_by_zip = coords_by_zipcode()
                                    geocoded_rows = []
                                    for row in rows:
                                        occupied = occupied_by_zip.setdefault(zipcode_key(row), set())
                                        geocoded = geocode_patient_row(row, occupied)
                                        occupied.add((geocoded["lat"], geocoded["lon"]))
                                        geocoded_rows.append(geocoded)
                                    append_patient_rows(geocoded_rows)
                                except (ValueError, RuntimeError) as ex:
                                    csv_notice.set_text(str(ex))
                                    csv_notice.classes("text-red-500", remove="text-green-600")
                                    return
                                except Exception:
                                    logger.exception("Failed to import CSV upload")
                                    csv_notice.set_text("Could not import file. Please try again.")
                                    csv_notice.classes("text-red-500", remove="text-green-600")
                                    return

                                csv_notice.set_text(f"{len(geocoded_rows)} records imported into the database.")
                                csv_notice.classes("text-green-600", remove="text-red-500")

                            ui.upload(
                                label="Choose CSV file",
                                on_upload=handle_upload,
                            ).props("accept=.csv").classes("w-full")
