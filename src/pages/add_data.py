import csv
import io
from pathlib import Path
from nicegui import ui, app, events

DATA_FILE = Path(__file__).parent.parent / "data" / "dka_sample_data.csv"

REQUIRED_COLUMNS = {
    "age at onset", "sex", "zipcode", "state",
    "month of onset", "year of onset", "a1c",
    "glucose", "bikarb", "ph", "duration of symptoms", "lat", "lon",
}


def append_rows(rows: list[dict]):
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(REQUIRED_COLUMNS))
        writer.writerows(rows)


@ui.page("/add_data")
def add_data_page():
    if app.storage.user.get("role") != "scientist":
        ui.navigate.to("/")
        return

    with ui.column().classes("w-full h-screen gap-0"):

        # ── Header ────────────────────────────────────────────────────────
        with ui.row().classes("w-full items-center bg-green-700 px-6 py-3 gap-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/map")) \
                .props("flat round color=white").tooltip("Back to map")
            ui.label("Add Data").classes("text-white text-2xl font-bold")

        # ── Tabs ──────────────────────────────────────────────────────────
        with ui.column().classes("flex-1 overflow-y-auto p-6 gap-6 items-center"):
            with ui.card().classes("w-full max-w-2xl p-0"):
                with ui.tabs().classes("w-full") as tabs:
                    tab_single = ui.tab("Single record", icon="person_add")
                    tab_csv    = ui.tab("Upload CSV", icon="upload_file")

                with ui.tab_panels(tabs, value=tab_single).classes("w-full"):

                    # ── Single record ─────────────────────────────────────
                    with ui.tab_panel(tab_single):
                        with ui.column().classes("w-full p-4 gap-3"):
                            ui.label("New patient record").classes("text-lg font-semibold")

                            with ui.grid(columns=2).classes("w-full gap-3"):
                                age    = ui.number("Age at onset", min=0, max=120, step=1, format="%.0f").classes("w-full")
                                year   = ui.number("Year of onset", min=1900, max=2100, step=1, format="%.0f").classes("w-full")
                                month  = ui.number("Month of onset", min=1, max=12, step=1, format="%.0f").classes("w-full")
                                dur    = ui.number("Duration of symptoms (days)", min=0, step=1, format="%.0f").classes("w-full")
                                gluc   = ui.number("Blood glucose (mg/dL)", min=0, step=1, format="%.0f").classes("w-full")
                                a1c    = ui.number("HbA1c (%)", min=0, max=20, step=0.1, format="%.1f").classes("w-full")
                                ph     = ui.number("pH", min=6.0, max=8.0, step=0.01, format="%.2f").classes("w-full")
                                bik    = ui.number("Bicarbonate (mmol/L)", min=0, max=40, step=0.1, format="%.1f").classes("w-full")
                                lat    = ui.number("Latitude", step=0.0001, format="%.4f").classes("w-full")
                                lon    = ui.number("Longitude", step=0.0001, format="%.4f").classes("w-full")

                            with ui.row().classes("w-full gap-3"):
                                sex    = ui.select(["Male", "Female"], label="Sex").classes("flex-1")
                                zipcode = ui.input("ZIP code").classes("flex-1")
                                state   = ui.input("State").classes("flex-1")

                            notice = ui.label("").classes("text-sm")

                            def save_single():
                                required = [age, year, month, gluc, ph, bik, lat, lon, sex, zipcode, state]
                                if any(f.value is None or f.value == "" for f in required):
                                    notice.set_text("Please fill in all fields.")
                                    notice.classes("text-red-500", remove="text-green-600")
                                    return
                                append_rows([{
                                    "age at onset": int(age.value),
                                    "sex": sex.value,
                                    "zipcode": zipcode.value,
                                    "state": state.value,
                                    "month of onset": int(month.value),
                                    "year of onset": int(year.value),
                                    "a1c": a1c.value or "",
                                    "glucose": int(gluc.value),
                                    "bikarb": bik.value,
                                    "ph": ph.value,
                                    "duration of symptoms": int(dur.value) if dur.value else "",
                                    "lat": lat.value,
                                    "lon": lon.value,
                                }])
                                notice.set_text("Record saved successfully.")
                                notice.classes("text-green-600", remove="text-red-500")
                                for field in [age, year, month, dur, gluc, a1c, ph, bik, lat, lon]:
                                    field.set_value(None)
                                sex.set_value(None)
                                zipcode.set_value("")
                                state.set_value("")

                            ui.button("Save record", icon="save", on_click=save_single) \
                                .classes("bg-green-600 text-white")

                    # ── CSV upload ────────────────────────────────────────
                    with ui.tab_panel(tab_csv):
                        with ui.column().classes("w-full p-4 gap-4"):
                            ui.label("Upload a CSV file").classes("text-lg font-semibold")
                            ui.label(
                                "The file must have these columns: " +
                                ", ".join(sorted(REQUIRED_COLUMNS))
                            ).classes("text-xs text-gray-500")

                            csv_notice = ui.label("").classes("text-sm")

                            def handle_upload(e: events.UploadEventArguments):
                                try:
                                    content = e.content.read().decode("utf-8")
                                    reader = csv.DictReader(io.StringIO(content))
                                    rows = list(reader)
                                    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
                                    if missing:
                                        csv_notice.set_text(f"Missing columns: {', '.join(sorted(missing))}")
                                        csv_notice.classes("text-red-500", remove="text-green-600")
                                        return
                                    append_rows(rows)
                                    csv_notice.set_text(f"{len(rows)} records imported successfully.")
                                    csv_notice.classes("text-green-600", remove="text-red-500")
                                except Exception as ex:
                                    csv_notice.set_text(f"Error reading file: {ex}")
                                    csv_notice.classes("text-red-500", remove="text-green-600")

                            ui.upload(
                                label="Choose CSV file",
                                on_upload=handle_upload,
                            ).props("accept=.csv").classes("w-full")

                            csv_notice
