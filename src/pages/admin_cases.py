import logging

from nicegui import app, ui

from services.geocoding import geocode_patient_row
from storage.patients_db import (
    coords_by_zipcode,
    delete_patient,
    get_patient,
    update_patient,
)

logger = logging.getLogger(__name__)


@ui.page("/admin/cases")
def admin_cases_page():
    if app.storage.user.get("role") != "admin":
        ui.navigate.to("/")
        return

    loaded = {"case": None}

    def field_number(label: str, **props):
        return ui.number(label, **props).props("outlined dense").classes("w-full")

    def field_input(label: str, **props):
        return ui.input(label, **props).props("outlined dense").classes("w-full")

    with ui.column().classes("w-full min-h-screen gap-0 bg-gray-50"):
        with ui.row().classes("h-14 w-full items-center border-b border-gray-200 bg-white px-6 gap-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/map")) \
                .props("flat round").tooltip("Back to map")
            with ui.column().classes("gap-0"):
                ui.label("Case Admin").classes("text-lg font-semibold text-gray-900")
                ui.label("Look up a case by ID to correct or delete a faulty record.").classes("text-xs text-gray-500")

        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-6"):
            notice = ui.label("").classes("text-sm")

            def show_error(text: str):
                notice.set_text(text)
                notice.classes("text-red-500", remove="text-green-600")

            def show_success(text: str):
                notice.set_text(text)
                notice.classes("text-green-600", remove="text-red-500")

            with ui.card().classes("w-full p-4 gap-4"):
                ui.label("Find case").classes("text-base font-semibold")
                with ui.row().classes("w-full items-end gap-3"):
                    case_id_input = ui.number("Case ID", min=1, step=1, format="%.0f") \
                        .props("outlined dense").classes("w-40")

                    def load_case():
                        if not case_id_input.value:
                            show_error("Enter a case ID first.")
                            return
                        case = get_patient(int(case_id_input.value))
                        if not case:
                            loaded["case"] = None
                            case_editor.refresh()
                            show_error(f"No case with ID {int(case_id_input.value)}.")
                            return
                        loaded["case"] = case
                        case_editor.refresh()
                        show_success(f"Loaded case {case['id']}.")

                    case_id_input.on("keydown.enter", lambda _: load_case())
                    ui.button("Load", icon="search", on_click=load_case).classes("bg-blue-700 text-white")

            @ui.refreshable
            def case_editor():
                case = loaded["case"]
                if not case:
                    return

                with ui.card().classes("w-full p-4 gap-4"):
                    with ui.row().classes("w-full items-center"):
                        ui.label(f"Case {case['id']}").classes("text-base font-semibold")
                        ui.space()
                        ui.label(f"Created: {case['created_at']}").classes("text-xs text-gray-500")

                    with ui.grid(columns=3).classes("w-full gap-3"):
                        age = field_number("Age at onset *", min=0, max=120, step=1, format="%.0f",
                                           value=case["age at onset"])
                        sex = ui.select(["Male", "Female"], label="Sex *", value=case["sex"]) \
                            .props("outlined dense").classes("w-full")
                        dur = field_number("Duration of symptoms (days, optional)", min=0, step=1, format="%.0f",
                                           value=case["duration of symptoms"])
                        year = field_number("Year of onset *", min=1900, max=2100, step=1, format="%.0f",
                                            value=case["year of onset"])
                        month = field_number("Month of onset *", min=1, max=12, step=1, format="%.0f",
                                             value=case["month of onset"])
                        a1c = field_number("HbA1c (%, optional)", min=0, max=20, step=0.1, format="%.1f",
                                           value=case["a1c"])
                        gluc = field_number("Glucose (mg/dL) *", min=0, step=1, format="%.0f",
                                            value=case["glucose"])
                        ph = field_number("pH *", min=6.0, max=8.0, step=0.01, format="%.2f",
                                          value=case["ph"])
                        bik = field_number("Bicarbonate (mmol/L) *", min=0, max=40, step=0.1, format="%.1f",
                                           value=case["bikarb"])
                        zipcode = field_input("ZIP code *", value=str(case["zipcode"]))
                        state = field_input("State *", value=str(case["state"]))

                    def save_case():
                        required = [age, year, month, gluc, ph, bik, sex, zipcode, state]
                        if any(f.value is None or f.value == "" for f in required):
                            show_error("Please fill in all required fields.")
                            return
                        try:
                            row_data = {
                                "age at onset": int(age.value),
                                "sex": sex.value,
                                "zipcode": zipcode.value.strip(),
                                "state": state.value.strip(),
                                "month of onset": int(month.value),
                                "year of onset": int(year.value),
                                "a1c": round(float(a1c.value), 1) if a1c.value else "",
                                "glucose": int(gluc.value),
                                "bikarb": round(float(bik.value), 1),
                                "ph": round(float(ph.value), 2),
                                "duration of symptoms": int(dur.value) if dur.value else "",
                            }
                            location_changed = (
                                row_data["zipcode"] != str(case["zipcode"]).strip()
                                or row_data["state"] != str(case["state"]).strip()
                            )
                            if location_changed:
                                occupied = coords_by_zipcode().get(
                                    (row_data["zipcode"], row_data["state"]), set()
                                )
                                row = geocode_patient_row(row_data, occupied)
                            else:
                                row = {**row_data, "lat": case["lat"], "lon": case["lon"]}
                            update_patient(case["id"], row)
                        except (ValueError, RuntimeError) as ex:
                            show_error(str(ex))
                            return
                        except Exception:
                            logger.exception("Failed to update case %s", case["id"])
                            show_error("Could not save changes. Please try again.")
                            return

                        loaded["case"] = get_patient(case["id"])
                        case_editor.refresh()
                        show_success(f"Saved changes to case {case['id']}.")

                    with ui.dialog() as confirm_dialog, ui.card().classes("gap-4"):
                        ui.label(f"Delete case {case['id']}?").classes("text-base font-semibold")
                        ui.label(
                            f"{case['sex']}, age {case['age at onset']}, "
                            f"ZIP {case['zipcode']} ({case['state']}), "
                            f"onset {case['month of onset']}/{case['year of onset']}"
                        ).classes("text-sm text-gray-600")
                        ui.label("This cannot be undone.").classes("text-sm text-red-600")
                        with ui.row().classes("w-full justify-end gap-2"):
                            ui.button("Cancel", on_click=confirm_dialog.close).props("flat")

                            def delete_case():
                                try:
                                    delete_patient(case["id"])
                                except Exception:
                                    logger.exception("Failed to delete case %s", case["id"])
                                    confirm_dialog.close()
                                    show_error("Could not delete case. Please try again.")
                                    return
                                confirm_dialog.close()
                                loaded["case"] = None
                                case_editor.refresh()
                                show_success(f"Deleted case {case['id']}.")

                            ui.button("Delete", icon="delete_forever", on_click=delete_case) \
                                .classes("bg-red-600 text-white")

                    with ui.row().classes("w-full justify-between"):
                        ui.button("Delete case", icon="delete", on_click=confirm_dialog.open) \
                            .props("outline").classes("text-red-600")
                        ui.button("Save changes", icon="save", on_click=save_case) \
                            .classes("bg-blue-700 text-white")

            case_editor()
