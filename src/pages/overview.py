"""Public district overview."""

from html import escape

from nicegui import ui

from pages.shared import header, interval, notice, percent, require
from services import endpoint
from services.geography import (
    KREISE_WITHOUT_CLINIC,
    pilot_boundaries,
    pilot_view,
)
from storage.cases_db import load_cases

# Fixed bands keep periods comparable.
BANDS = (
    (0.00, "#dbeafe", "under 20%"),
    (0.20, "#93c5fd", "20–30%"),
    (0.30, "#60a5fa", "30–40%"),
    (0.40, "#2563eb", "40–50%"),
    (0.50, "#1e3a8a", "50% and above"),
)
NEUTRAL = "#e2e8f0"


def band_colour(value: float | None, sufficient: bool) -> str:
    if value is None or not sufficient:
        return NEUTRAL
    colour = BANDS[0][1]
    for threshold, band, _ in BANDS:
        if value >= threshold:
            colour = band
    return colour


@ui.page("/overview")
def overview_page():
    if not require():
        return

    onsets = endpoint.from_cases(load_cases())
    years = sorted({row["year"] for row in onsets}) or [2014, 2025]
    state = {"year_min": years[0], "year_max": years[-1]}
    layers: list[dict] = []

    with ui.column().classes("w-full h-screen gap-0"):
        header(
            "DKA at diabetes manifestation",
            "Share of new type 1 diagnoses presenting in ketoacidosis",
        )

        if not onsets:
            with ui.column().classes("w-full max-w-3xl mx-auto p-8 gap-5"):
                notice(
                    "No case records have been loaded yet, so the map cannot be "
                    "drawn. District figures are counted from the case records "
                    "themselves — both the number of manifestations and how many "
                    "presented in ketoacidosis — so there is nothing to show here "
                    "until they are imported.",
                    tone="blocked",
                )
                ui.button(
                    "Go to Data import", icon="upload_file",
                    on_click=lambda: ui.navigate.to("/data"),
                ).props("unelevated").classes("self-start bg-blue-700 text-white")
            return

        with ui.row().classes("w-full flex-1 min-h-0 gap-0"):
            with ui.column().classes(
                "w-72 h-full shrink-0 overflow-y-auto border-r border-slate-200 "
                "bg-white px-5 py-4 gap-5"
            ):
                ui.label("Period").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-500"
                )
                with ui.row().classes("w-full justify-between"):
                    low_label = ui.label(str(years[0])).classes("text-xs text-slate-500")
                    high_label = ui.label(str(years[-1])).classes("text-xs text-slate-500")

                def on_year_change(event):
                    state["year_min"] = int(event.value["min"])
                    state["year_max"] = int(event.value["max"])
                    low_label.set_text(str(state["year_min"]))
                    high_label.set_text(str(state["year_max"]))
                    refresh()

                ui.range(
                    min=years[0], max=years[-1], step=1,
                    value={"min": years[0], "max": years[-1]},
                    on_change=on_year_change,
                ).props("color=blue-7 thumb-size=18px").classes("w-full px-1")

                ui.separator()
                ui.label("Legend").classes(
                    "text-xs font-semibold uppercase tracking-wide text-slate-500"
                )
                for _, colour, label in BANDS:
                    with ui.row().classes("items-center gap-2"):
                        ui.html(
                            f'<span style="display:inline-block;width:16px;height:16px;'
                            f'border:1px solid #cbd5e1;background:{colour}"></span>'
                        )
                        ui.label(label).classes("text-xs text-slate-600")
                with ui.row().classes("items-center gap-2"):
                    ui.html(
                        f'<span style="display:inline-block;width:16px;height:16px;'
                        f'border:1px solid #cbd5e1;background:{NEUTRAL}"></span>'
                    )
                    ui.label(
                        f"under {endpoint.MIN_DENOMINATOR} manifestations"
                    ).classes("text-xs text-slate-600")

                ui.separator()
                summary = ui.label().classes("text-sm text-slate-700 leading-relaxed")

            centre, zoom = pilot_view()
            map_widget = ui.leaflet(center=centre, zoom=zoom).classes("h-full flex-1")

        with ui.row().classes(
            "w-full shrink-0 border-t border-slate-200 bg-white px-5 py-3 gap-6"
        ):
            table = ui.table(
                columns=[
                    {"name": "kreis", "label": "Landkreis", "field": "kreis", "align": "left"},
                    {"name": "share", "label": "DKA share", "field": "share", "align": "right"},
                    {"name": "ci", "label": "95% CI", "field": "ci", "align": "right"},
                    {"name": "counts", "label": "DKA / manifestations", "field": "counts", "align": "right"},
                    {"name": "note", "label": "Note", "field": "note", "align": "left"},
                ],
                rows=[], row_key="kreis",
            ).props("flat dense hide-pagination").classes("w-full")

    def district_rows() -> list[dict]:
        return endpoint.by_kreis(onsets, state["year_min"], state["year_max"])

    def tooltip(row: dict) -> str:
        lines = [f"<b>{escape(row['kreis'])}</b>"]
        if row["total"] == 0:
            lines.append("No manifestations reported")
        elif not row["sufficient"]:
            lines.append(
                f"{row['successes']} of {row['total']} manifestations in DKA"
            )
            lines.append(
                f"<i>Too few to report a percentage "
                f"(under {endpoint.MIN_DENOMINATOR})</i>"
            )
        else:
            lines.append(f"DKA at manifestation: <b>{percent(row['proportion'])}</b>")
            lines.append(f"95% CI: {interval(row['ci_low'], row['ci_high'])}")
            lines.append(f"{row['successes']} of {row['total']} manifestations")
        if row["no_local_clinic"]:
            lines.append(
                "<i>No participating clinic in this district — "
                "children treated locally are not captured</i>"
            )
        return "<br>".join(lines)

    def refresh():
        rows = district_rows()
        by_ags = {row["ags"]: row for row in rows}
        for layer in layers:
            row = by_ags.get(layer["ags"])
            if not row:
                continue
            layer["layer"].run_method(
                "setStyle", {"fillColor": band_colour(row["proportion"], row["sufficient"])}
            )
            layer["layer"].run_method("unbindTooltip")
            layer["layer"].run_method("bindTooltip", tooltip(row), {"sticky": True})

        pooled = endpoint.overall(onsets, state["year_min"], state["year_max"])
        if pooled["proportion"] is None:
            summary.set_text("No manifestations reported for this period.")
        else:
            summary.set_text(
                f"Across {state['year_min']}–{state['year_max']}, "
                f"{pooled['successes']} of {pooled['total']} new type 1 "
                f"manifestations presented in ketoacidosis "
                f"({percent(pooled['proportion'])}, 95% CI "
                f"{interval(pooled['ci_low'], pooled['ci_high'])})."
            )

        table.rows = [
            {
                "kreis": row["kreis"],
                "share": percent(row["proportion"]) if row["sufficient"] else "—",
                "ci": interval(row["ci_low"], row["ci_high"]) if row["sufficient"] else "—",
                "counts": f"{row['successes']} / {row['total']}",
                "note": (
                    "no participating clinic" if row["no_local_clinic"]
                    else "" if row["sufficient"]
                    else f"under {endpoint.MIN_DENOMINATOR} manifestations"
                ),
            }
            for row in rows
        ]
        table.update()

    def draw():
        rows = {row["ags"]: row for row in district_rows()}
        for feature in pilot_boundaries()["features"]:
            ags = str(feature["properties"]["AGS"]).zfill(5)
            row = rows.get(ags)
            polygon = map_widget.generic_layer(
                name="geoJSON",
                args=[feature, {"style": {
                    "color": "#475569",
                    "weight": 1.4,
                    "fillColor": band_colour(
                        row["proportion"] if row else None,
                        bool(row and row["sufficient"]),
                    ),
                    "fillOpacity": 0.8,
                    "dashArray": "4" if ags in KREISE_WITHOUT_CLINIC else None,
                }}],
            )
            layers.append({"layer": polygon, "ags": ags})
        refresh()

    map_widget.on("init", lambda _: draw())
