"""Analysis dashboard for scientists."""

from nicegui import ui

from pages import charts
from pages.shared import header, interval, notice, percent, require
from services import summaries
from services.epidemiology import (
    MIN_NON_DKA_SHARE,
    frame_check,
    is_dka,
    is_gradeable,
    is_severe,
    split_manifestations,
)
from services.models import TERM_LABELS, duration_model, severity_model
from storage.cases_db import load_cases

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
        ui.label(
            f"{model['measure']}s from {model['n']} cases across "
            f"{model['clusters']} postcode areas. Filled points mark intervals "
            f"that exclude 1. Standard errors clustered on the postcode — "
            f"deprivation is shared across an area, so its effective sample "
            f"size is {model['clusters']}, not {model['n']}."
        ).classes("text-xs text-slate-500 leading-relaxed")
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
    if not require("scientist", "admin"):
        return

    loaded_cases = load_cases()
    with ui.column().classes("w-full min-h-screen gap-0 bg-slate-50"):
        header("Analysis", f"{len(loaded_cases)} case records")

        with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):

            if not loaded_cases:
                notice("No cases loaded yet. Import them under Data.", tone="blocked")
                return
            else:
                eligibility = split_manifestations(loaded_cases)
                unknown_onset = len(eligibility["unknown_new_onset"])
                if unknown_onset:
                    notice(
                        f"{unknown_onset} case records have no confirmed new-onset "
                        "status. This endpoint is DKA at first manifestation, so "
                        "the page cannot decide whether those rows belong in its "
                        "cohort. Resolve their new_onset values before reporting.",
                        tone="blocked",
                    )
                    return

                cases = eligibility["eligible"]
                excluded_onset = len(eligibility["not_new_onset"])
                if excluded_onset:
                    notice(
                        f"{excluded_onset} known-diabetes episodes are excluded; "
                        "only confirmed first manifestations are analysed.",
                        tone="warn",
                    )
                if not cases:
                    notice("No confirmed first manifestations are available.", tone="blocked")
                    return

                cohort = frame_check(cases)
                if cohort["suspicious"]:
                    notice(
                        f"Only {cohort['non_dka']} of {cohort['n']} gradeable "
                        f"records ({cohort['share']:.0%}) are not in "
                        f"ketoacidosis, below the {MIN_NON_DKA_SHARE:.0%} sanity "
                        "threshold. This may be a DKA-selected extract. The "
                        "threshold is only a warning and cannot prove whether a "
                        "cohort is complete.",
                        tone="warn",
                    )
                notice(
                    "Results are based on data received from participating clinics.",
                    tone="warn",
                )

                gradeable = [case for case in cases if is_gradeable(case)]
                ungradeable = len(cases) - len(gradeable)
                graded = len(gradeable)
                dka = sum(1 for case in gradeable if is_dka(case))
                severe = sum(1 for case in gradeable if is_severe(case))
                areas = len({case.get("plz5") for case in cases if case.get("plz5")})

                with ui.row().classes("w-full gap-4 flex-wrap"):
                    _kpi("Case records", str(len(cases)),
                         f"{ungradeable} cannot be graded from pH or bicarbonate"
                         if ungradeable else "all gradeable from pH or bicarbonate",
                         "text-slate-900")
                    _kpi("In ketoacidosis",
                         percent(dka / graded) if graded else "—",
                         f"{dka} of {graded}", "text-blue-700")
                    _kpi("Severe",
                         percent(severe / graded) if graded else "—",
                         f"{severe} of {graded}", "text-red-700")
                    _kpi("Postcode areas", str(areas),
                         "with at least one case", "text-teal-700")

                if ungradeable:
                    notice(
                        f"{ungradeable} of {len(cases)} records have insufficient "
                        "pH/bicarbonate information to confirm or exclude DKA, so "
                        "they cannot be classified and "
                        "are excluded from every share on this page — numerator and "
                        "denominator alike. Counting them as non-DKA would be an "
                        "imputation, and it would pull every percentage down.",
                        tone="warn",
                    )

                with ui.column().classes("gap-1 pt-2"):
                    ui.label("Case-level analyses").classes(
                        "text-xl font-bold tracking-tight text-slate-900"
                    )
                    ui.label(
                        "Associations among observed first manifestations. Clinic "
                        "participation and selective capture can limit how far they "
                        "generalise beyond these records."
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
                        "Severe DKA by deprivation",
                        "Tertiles cut within the pilot region, not nationally",
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
                            ui.label(
                                "Negative binomial, dispersion "
                                + (
                                    f"estimated at \u03b1 = {model['alpha']:.3f}"
                                    if model.get("alpha_estimated")
                                    else f"held at \u03b1 = {model['alpha']:.3f} "
                                         "because the fit did not converge"
                                )
                                + f". {model['n']} cases across {model['clusters']} "
                                "postcode areas, standard errors clustered on the "
                                "postcode."
                            ).classes("text-xs text-slate-500 leading-relaxed")
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
            pandemic = summaries.pandemic_comparison(cases)

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
                        f"Linear trend across {trend['n_groups']} years: "
                        f"z = {trend['statistic']:.2f}, p = {trend['p_value']:.3f} "
                        "(Cochran–Armitage). The shaded band is why this should be "
                        "read with the counts, not on its own."
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
                    "Pooled across the whole period; grey means no participating clinic",
                ):
                    ui.echart(charts.district_shares(districts)).classes("w-full h-72")
                with _card(
                    "Lockdown period",
                    "Fixed calendar windows, so the comparison is stable across filters",
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
                        "This contrast cannot separate the pandemic from the "
                        "underlying trend: a steady rise across 2014–2025 would "
                        "land here as a lockdown effect. Read it against the "
                        "annual trend above, not on its own."
                    ).classes("text-xs text-slate-500 leading-relaxed")
