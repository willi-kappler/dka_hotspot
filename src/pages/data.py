"""Data import for manifestation case records."""

import logging

from nicegui import app, events, ui

from pages.shared import header, require
from services.epidemiology import frame_check
from storage import audit_db, cases_db

logger = logging.getLogger(__name__)
OUTLINED_DENSE = "outlined dense"
SECTION_TITLE_CLASSES = "text-base font-semibold text-slate-900"

CASE_TEMPLATE = (
    "pseudo_id,center,sex,age_at_onset,date_of_onset,zip_code,"
    "migration_background,new_onset,symptom_duration_days,referral_pathway,ph_venous,"
    "bicarbonate_mmol_l,hba1c_percent,glucose_mg_dl,dka,dka_severity\n"
    "10001,TUE,f,7.4,2024-03,72074,no,yes,14,pediatrician,7.05,4.2,12.4,412,yes,severe"
)


def _manual_input(label: str, **kwargs):
    return ui.input(label, **kwargs).props(OUTLINED_DENSE)

@ui.page("/data")
def data_page():
    if not require("scientist", "admin"):
        return

    with ui.column().classes("w-full min-h-screen gap-0 bg-slate-50"):
        header("Data", "Import manifestation case records")

        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-6"):

            with ui.card().classes("w-full p-5 gap-4 shadow-none border border-slate-200"):
                with ui.column().classes("gap-0"):
                    ui.label("Case records").classes(SECTION_TITLE_CLASSES)
                    ui.label(
                        "Pseudonymised patient rows, one per manifestation. "
                        "Needs a five-digit postcode inside the pilot region; "
                        "the Landkreis is filled in from it."
                    ).classes("text-xs text-slate-500")
                ui.code(CASE_TEMPLATE, language="csv").classes("w-full text-xs")
                case_notice = ui.label("").classes("text-sm")

                def upload_cases(event: events.UploadEventArguments):
                    try:
                        text = event.content.read().decode("utf-8")
                        rows = cases_db.parse_csv(text)
                        count = cases_db.add_cases(rows)
                    except ValueError as error:
                        case_notice.set_text(str(error))
                        case_notice.classes("text-red-600", remove="text-green-700")
                        return
                    except Exception:
                        logger.exception("Case import failed")
                        audit_db.record(
                            audit_db.CASES_IMPORTED,
                            app.storage.user.get("username"),
                            detail="failed",
                        )
                        case_notice.set_text("Could not import the file.")
                        case_notice.classes("text-red-600", remove="text-green-700")
                        return
                    audit_db.record(
                        audit_db.CASES_IMPORTED,
                        app.storage.user.get("username"),
                        target=event.name or "",
                        detail=f"rows={count}",
                    )
                    batch = frame_check(rows)
                    if batch["suspicious"]:
                        case_notice.set_text(
                            f"{count} cases imported, but only {batch['non_dka']} "
                            f"of {batch['n']} ({batch['share']:.0%}) are not in "
                            "ketoacidosis. This may be a DKA-selected extract. "
                            "Confirm against the clinic's complete manifestation "
                            "return before reporting."
                        )
                        case_notice.classes("text-red-600", remove="text-green-700")
                        return
                    case_notice.set_text(
                        f"{count} cases imported "
                        f"({batch['share']:.0%} not in ketoacidosis). Import "
                        "prevalence does not by itself prove cohort completeness."
                    )
                    case_notice.classes("text-green-700", remove="text-red-600")

                ui.upload(label="Choose CSV", on_upload=upload_cases) \
                    .props("accept=.csv").classes("w-full")

            with ui.card().classes("w-full p-5 gap-4 shadow-none border border-slate-200"):
                ui.label("Add one case record").classes(SECTION_TITLE_CLASSES)
                ui.label(
                    "Enter one complete manifestation without preparing a CSV file."
                ).classes("text-xs text-slate-500")
                with ui.grid(columns=2).classes("w-full gap-3"):
                    pseudonym = _manual_input("Pseudonym")
                    clinic = ui.select(
                        ["TUE", "RT"], label="Clinic", with_input=True
                    ).props(OUTLINED_DENSE)
                    age = _manual_input("Age at onset", validation={
                        "required": lambda value: bool(value),
                    })
                    sex = ui.select(
                        {"m": "Male", "f": "Female"}, label="Sex"
                    ).props(OUTLINED_DENSE)
                    date = _manual_input("Date of onset (YYYY-MM)")
                    postcode = _manual_input("Five-digit postcode")
                    migration = ui.select(
                        {"yes": "Yes", "no": "No", "unknown": "Unknown"},
                        label="Migration background", value="unknown",
                    ).props(OUTLINED_DENSE)
                    new_onset = ui.select(
                        {"yes": "Yes", "no": "No"}, label="New onset"
                    ).props(OUTLINED_DENSE)
                    duration = _manual_input("Symptom duration (days)")
                    referral = ui.select(
                        ["Pediatrician", "Emergency_self", "Other", "Unknown"],
                        label="Referral pathway", value="Unknown",
                    ).props(OUTLINED_DENSE)
                    ph = _manual_input("Venous pH")
                    bicarbonate = _manual_input("Bicarbonate (mmol/L)")
                    hba1c = _manual_input("HbA1c (%)")
                    glucose = _manual_input("Glucose (mg/dL)")
                    dka = ui.select(
                        {"yes": "Yes", "no": "No"}, label="DKA"
                    ).props(OUTLINED_DENSE)
                    severity = ui.select(
                        ["none", "mild", "moderate", "severe"],
                        label="DKA severity", value="none",
                    ).props("outlined dense")
                manual_notice = ui.label("").classes("text-sm")

                def add_single_case():
                    values = {
                        "pseudonym": pseudonym.value,
                        "clinic": clinic.value,
                        "age_at_onset": age.value,
                        "sex": sex.value,
                        "date_of_onset": date.value,
                        "plz5": postcode.value,
                        "migration_background": migration.value,
                        "new_onset": new_onset.value,
                        "duration_of_symptoms": duration.value,
                        "referral_pathway": referral.value,
                        "ph": ph.value,
                        "bicarbonate": bicarbonate.value,
                        "hba1c": hba1c.value,
                        "glucose": glucose.value,
                        "dka_reported": dka.value,
                        "dka_severity_reported": severity.value,
                    }
                    try:
                        errors = cases_db.validate([values])
                        if errors:
                            raise ValueError(errors[0])
                        cases_db.add_cases([values])
                    except (TypeError, ValueError) as error:
                        manual_notice.set_text(str(error))
                        manual_notice.classes("text-red-600", remove="text-green-700")
                        return
                    except Exception:
                        logger.exception("Single case import failed")
                        manual_notice.set_text("Could not add the case.")
                        manual_notice.classes("text-red-600", remove="text-green-700")
                        return
                    audit_db.record(
                        audit_db.CASES_IMPORTED,
                        app.storage.user.get("username"),
                        detail="rows=1 (manual entry)",
                    )
                    manual_notice.set_text("Case added.")
                    manual_notice.classes("text-green-700", remove="text-red-600")

                ui.button("Add case", icon="person_add", on_click=add_single_case) \
                    .props("unelevated").classes("self-start bg-blue-700 text-white")

            disagreements = cases_db.classification_disagreements()
            if disagreements:
                with ui.card().classes("w-full p-5 gap-3 shadow-none border border-slate-200"):
                    with ui.column().classes("gap-0"):
                        ui.label("DKA classification disagreements").classes(
                            "text-base font-semibold text-slate-900"
                        )
                        ui.label(
                            f"{len(disagreements)} of the loaded cases carry a "
                            "reported DKA grade that differs from the ISPAD "
                            "grade recomputed from pH and bicarbonate. Both are "
                            "stored; the analysis uses the recomputed one. Most "
                            "such rows are missing one of the two values, or sit "
                            "just inside the bicarbonate criterion with a normal pH."
                        ).classes("text-xs text-slate-500 leading-relaxed")
                    ui.table(
                        columns=[
                            {"name": "id", "label": "ID", "field": "id", "align": "left"},
                            {"name": "pseudonym", "label": "Pseudonym", "field": "pseudonym", "align": "left"},
                            {"name": "reported", "label": "Reported", "field": "reported", "align": "left"},
                            {"name": "derived", "label": "Recomputed", "field": "derived", "align": "left"},
                            {"name": "ph", "label": "pH", "field": "ph", "align": "right"},
                            {"name": "bicarbonate", "label": "Bicarbonate", "field": "bicarbonate", "align": "right"},
                        ],
                        rows=[
                            {**row,
                             "ph": "—" if row["ph"] is None else row["ph"],
                             "bicarbonate": "—" if row["bicarbonate"] is None
                             else row["bicarbonate"]}
                            for row in disagreements
                        ],
                        row_key="id",
                        pagination={"rowsPerPage": 10},
                    ).props("flat dense").classes("w-full")
