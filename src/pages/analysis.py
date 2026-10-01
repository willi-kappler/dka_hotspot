"""Analysis dashboard for all"""

from nicegui import ui

from pages import charts
from pages.shared import header, interval, notice, percent, require
from services import summaries
from services.endpoint import MIN_DENOMINATOR
from services.epidemiology import (
    frame_check,
    is_dka,
    is_gradeable,
    is_severe,
    split_manifestations,
)
from services.geography import KREISE_WITHOUT_CLINIC, PILOT_KREISE
from services.models import TERM_LABELS, duration_model, severity_model
from storage.cases_db import load_cases

FILTER_LABEL = "text-xs font-semibold uppercase tracking-wide text-slate-500"

MODEL_COLUMNS = [
    {"name": "term", "label": "Term", "field": "term", "align": "left"},
    {"name": "estimate", "label": "Estimate", "field": "estimate", "align": "right"},
    {"name": "ci", "label": "95% CI", "field": "ci", "align": "right"},
    {"name": "p", "label": "p", "field": "p", "align": "right"},
]


def _card(title: str, subtitle: str = ""):
    container = ui.card().classes(
        "w-full p-5 gap-2 shadow-none border border-slate-200 bg-white"
    )
    with container:
        with ui.column().classes("gap-0"):
            ui.label(title).classes("text-sm font-semibold text-slate-900")
            if subtitle:
                ui.label(subtitle).classes("text-xs text-slate-500")
    return container


def _kpi(label: str, value: str, note: str, accent: str):
    with ui.card().classes(
        "flex-1 min-w-40 p-4 gap-1 shadow-none border border-slate-200 bg-white"
    ):
        ui.label(label).classes(
            "text-xs font-semibold uppercase tracking-wide text-slate-500"
        )
        ui.label(value).classes(f"text-3xl font-bold tracking-tight {accent}")
        ui.label(note).classes("text-xs text-slate-500")


def _model_block(title: str, subtitle: str, model: dict):
    with _card(title, subtitle):
        if not model.get("available"):
            notice(model.get("reason", "Not available."), tone="blocked")
            return
        ui.echart(charts.forest(model, "")).classes("w-full h-72")
        ui.label("Filled points are statistically significant.").classes("text-xs text-slate-500 leading-relaxed")
        with ui.expansion("Exact values").classes("w-full text-sm"):
            ui.table(
                columns=MODEL_COLUMNS,
                rows=[
                    {
                        "term": TERM_LABELS.get(term["term"], term["term"]),
                        "estimate": f"{term['estimate']:.2f}",
                        "ci": f"{term['ci_low']:.2f}–{term['ci_high']:.2f}",
                        "p": "<0.001" if term["p_value"] < 0.001 else f"{term['p_value']:.3f}",
                    }
                    for term in model["terms"]
                ],
                row_key="term",
            ).props("flat dense hide-pagination").classes("w-full")


@ui.page("/analysis")
def analysis_page():
    if not require("scientist", "admin", "user"):
        return

    loaded_cases = load_cases()
    with ui.column().classes("w-full min-h-screen gap-0 bg-slate-50"):
        header("Analysis", f"{len(loaded_cases)} case records")

        with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
            if not loaded_cases:
                notice("No cases loaded yet. Import them under Data.", tone="blocked")
                return

            # Cohort-level checks run on the full dataset, before any filter.
            eligibility = split_manifestations(loaded_cases)
            unknown_onset = len(eligibility["unknown_new_onset"])
            if unknown_onset:
                notice(
                    "Some case records are missing the new-onset field. "
                    "Fill it in under Data.",
                    tone="blocked",
                )
                return

            all_cases = eligibility["eligible"]
            excluded_onset = len(eligibility["not_new_onset"])
            if excluded_onset:
                notice(
                    "Cases with known diabetes are excluded.",
                    tone="warn",
                )
            if not all_cases:
                notice("No confirmed first manifestations are available.", tone="blocked")
                return

            cohort = frame_check(all_cases)
            if cohort["suspicious"]:
                notice(
                    "Unusually few cases without DKA. Check that the clinic "
                    "sent all new diagnoses.",
                    tone="warn",
                )
            notice(
                "Results are based on data received from participating clinics.",
                tone="warn",
            )

            all_years = sorted({case["year_of_onset"] for case in all_cases})
            filters = {
                "districts": set(PILOT_KREISE),
                "year_min": all_years[0],
                "year_max": all_years[-1],
            }

            district_names = {
                ags: name + (" (no clinic)" if ags in KREISE_WITHOUT_CLINIC else "")
                for ags, name in PILOT_KREISE.items()
            }

            def on_districts(event):
                # Nothing picked means all districts. The field shows a summary
                # rather than every name, so it stays one line at any count.
                chosen = event.value or []
                filters["districts"] = set(chosen) or set(PILOT_KREISE)
                if not chosen:
                    summary = "All districts"
                elif len(chosen) == 1:
                    summary = district_names[chosen[0]]
                else:
                    summary = f"{len(chosen)} districts"
                district_select.props["display-value"] = summary
                results.refresh()

            def on_years(event):
                filters["year_min"] = int(event.value["min"])
                filters["year_max"] = int(event.value["max"])
                year_label.set_text(f"{filters['year_min']}–{filters['year_max']}")
                results.refresh()

            with ui.row().classes(
                "w-full items-center gap-x-8 gap-y-3 flex-wrap rounded-lg border "
                "border-slate-200 bg-white px-5 py-3"
            ):
                district_select = ui.select(
                    district_names, multiple=True, value=[], label="District",
                    with_input=True, on_change=on_districts,
                ).props('outlined dense display-value="All districts"').classes("w-72")
                with ui.row().classes("items-center gap-3 flex-1 min-w-64"):
                    ui.label("Years").classes(FILTER_LABEL)
                    ui.range(
                        min=all_years[0], max=all_years[-1], step=1,
                        value={"min": all_years[0], "max": all_years[-1]},
                        on_change=on_years,
                    ).props("color=blue-7 thumb-size=18px").classes("flex-1")
                    year_label = ui.label(f"{all_years[0]}–{all_years[-1]}").classes(
                        "text-sm text-slate-700"
                    )

            @ui.refreshable
            def results():
                _results(
                    summaries.filter_cases(all_cases, filters["districts"],
                                           filters["year_min"], filters["year_max"]),
                    # The pandemic windows are fixed calendar years, so this card
                    # follows the district filter but not the year filter.
                    summaries.filter_cases(all_cases, filters["districts"]),
                )

            results()


def _results(cases: list[dict], pandemic_cases: list[dict]):
    """Everything below the filter bar, drawn for the filtered cases."""
    gradeable = [case for case in cases if is_gradeable(case)]
    graded = len(gradeable)
    if graded < MIN_DENOMINATOR:
        notice(
            f"Too few cases match these filters ({graded}). Widen the filters.",
            tone="blocked",
        )
        return

    ungradeable = len(cases) - graded
    dka = sum(1 for case in gradeable if is_dka(case))
    severe = sum(1 for case in gradeable if is_severe(case))
    areas = len({case.get("plz5") for case in cases if case.get("plz5")})

    with ui.row().classes("w-full gap-4 flex-wrap"):
        _kpi("Case records", str(len(cases)),
             f"{ungradeable} cannot be graded from pH or bicarbonate"
             if ungradeable else "all gradeable from pH or bicarbonate",
             "text-slate-900")
        _kpi("In ketoacidosis", percent(dka / graded), f"{dka} of {graded}",
             "text-blue-700")
        _kpi("Severe", percent(severe / graded), f"{severe} of {graded}",
             "text-red-700")
        _kpi("Postcode areas", str(areas), "with at least one case", "text-teal-700")

    if ungradeable:
        notice(
            "Some records are missing pH or bicarbonate and are left out "
            "of the percentages.",
            tone="warn",
        )

    with ui.column().classes("gap-1 pt-2"):
        ui.label("Case-level analyses").classes(
            "text-xl font-bold tracking-tight text-slate-900"
        )
        ui.label(
            "These analyses include confirmed first manifestations "
            "recorded by participating clinics and may not represent "
            "all cases in the region."
        ).classes("text-sm text-slate-500")

    with ui.grid(columns=2).classes("w-full gap-4"):
        with _card(
            "How they presented",
            "All case records by biochemical severity",
        ):
            ui.echart(
                charts.severity_donut(summaries.severity_mix(cases))
            ).classes("w-full h-72")

        deprivation = summaries.by_deprivation(cases)
        with _card(
            "Severe DKA by GISD deprivation tertile",
            "GISD tertiles calculated within the pilot region, not nationally",
        ):
            if deprivation:
                ui.echart(
                    charts.deprivation_gradient(deprivation, "severe")
                ).classes("w-full h-72")
            else:
                notice("No cases carry a usable postcode.", tone="blocked")

    with ui.grid(columns=2).classes("w-full gap-4"):
        with _card("DKA by age at onset", "Whiskers are 95% intervals"):
            ui.echart(
                charts.age_gradient(summaries.by_age_band(cases))
            ).classes("w-full h-72")
        with _card("DKA by sex", "Whiskers are 95% intervals"):
            ui.echart(
                charts.sex_gradient(summaries.by_sex(cases))
            ).classes("w-full h-72")

    _model_block(
        "Adjusted risk of severe DKA",
        "Deprivation, age, sex, onset year and migration background",
        severity_model(cases),
    )

    durations = summaries.duration_by_deprivation(cases)
    with ui.grid(columns=2).classes("w-full gap-4"):
        with _card(
            "Symptom duration by deprivation",
            "Median and interquartile range, in days before diagnosis",
        ):
            if durations:
                ui.echart(charts.duration_box(durations)).classes(
                    "w-full h-72"
                )
            else:
                notice("No case records symptom duration.", tone="blocked")
        with _card(
            "Adjusted symptom duration",
            "The most direct measure of delayed recognition available",
        ):
            model = duration_model(cases)
            if model.get("available"):
                ui.echart(charts.forest(model, "")).classes("w-full h-72")
                ui.label("Filled points are statistically significant.").classes("text-xs text-slate-500 leading-relaxed")
            else:
                notice(model.get("reason", "Not available."), tone="blocked")

    with ui.column().classes("gap-1 pt-4"):
        ui.label("Case-level area summaries").classes(
            "text-xl font-bold tracking-tight text-slate-900"
        )
        ui.label(
            "All percentages use gradeable, confirmed first manifestations "
            "in the uploaded records as the denominator."
        ).classes("text-sm text-slate-500")

    years = sorted({case["year_of_onset"] for case in cases})
    pooled = summaries.overall(cases)
    trend = summaries.year_trend(cases)
    annual = summaries.by_year(cases)
    districts = summaries.by_kreis(cases)
    pandemic = summaries.pandemic_comparison(pandemic_cases)

    with _card(
        "Annual trend",
        f"{pooled['successes']} of {pooled['total']} case records "
        f"presented in DKA over {years[0]}–{years[-1]}: "
        f"{percent(pooled['proportion'])} "
        f"({interval(pooled['ci_low'], pooled['ci_high'])})",
    ):
        ui.echart(charts.annual_trend(annual)).classes("w-full h-80")
        if trend["p_value"] is not None:
            ui.label(
                f"Trend over time: p = {trend['p_value']:.2f}."
            ).classes("text-xs text-slate-500 leading-relaxed")
        with ui.expansion("Annual counts").classes("w-full text-sm"):
            ui.table(
                columns=[
                    {"name": "year", "label": "Year", "field": "year", "align": "left"},
                    {"name": "share", "label": "DKA share", "field": "share", "align": "right"},
                    {"name": "ci", "label": "95% CI", "field": "ci", "align": "right"},
                    {"name": "counts", "label": "DKA / case records", "field": "counts", "align": "right"},
                ],
                rows=[
                    {
                        "year": row["year"],
                        "share": percent(row["proportion"]),
                        "ci": interval(row["ci_low"], row["ci_high"]),
                        "counts": f"{row['successes']} / {row['total']}",
                    }
                    for row in annual
                ],
                row_key="year",
            ).props("flat dense hide-pagination").classes("w-full")

    with ui.grid(columns=2).classes("w-full gap-4"):
        with _card(
            "By district",
            "Pooled across the selected period; grey means no participating clinic",
        ):
            ui.echart(charts.district_shares(districts)).classes("w-full h-72")
        with _card(
            "Pandemic period (2020–2021)",
            "Fixed calendar windows: follows the district filter, ignores the year filter",
        ):
            ui.echart(charts.period_windows(pandemic)).classes("w-full h-72")
            ratio = pandemic["during_vs_before"]
            if ratio["ratio"] is not None:
                ui.label(
                    f"2020–2021 vs 2014–2019: risk ratio "
                    f"{ratio['ratio']:.2f} "
                    f"({ratio['ci_low']:.2f}–{ratio['ci_high']:.2f})"
                ).classes("text-sm font-medium text-slate-900")
            ui.label(
                "Any difference in 2020–2021 may reflect the longer-term "
                "trend rather than the pandemic itself. Compare this "
                "result with the annual trend above."
            ).classes("text-xs text-slate-500 leading-relaxed")
