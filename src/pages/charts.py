"""ECharts options for the analysis page."""

from services.models import TERM_LABELS

BLUE, TEAL, RED, SLATE = "#2563eb", "#0f766e", "#b91c1c", "#64748b"
GRADIENT = {"Lower": "#93c5fd", "Middle": "#3b82f6", "Higher": "#1e3a8a"}


def _base() -> dict:
    return {
        "animationDuration": 300,
        "textStyle": {"fontFamily": "Inter, ui-sans-serif, system-ui"},
        "grid": {"left": 62, "right": 26, "top": 34, "bottom": 46},
    }


def _percent_axis(name: str = "Share of case records") -> dict:
    return {
        "type": "value",
        "name": name,
        "nameLocation": "middle",
        "nameGap": 44,
        "axisLabel": {"formatter": "{value}%"},
        "min": 0,
    }


def forest(model: dict, title: str) -> dict:
    """Build a forest plot on a log axis."""
    terms = list(reversed(model.get("terms", [])))
    labels = [TERM_LABELS.get(term["term"], term["term"]) for term in terms]

    whiskers = [
        {
            "type": "line",
            "data": [[term["ci_low"], index], [term["ci_high"], index]],
            "showSymbol": False,
            "silent": True,
            "lineStyle": {"color": SLATE, "width": 2},
            "z": 2,
        }
        for index, term in enumerate(terms)
    ]

    points = {
        "type": "scatter",
        "data": [
            {
                "value": [term["estimate"], index],
                "itemStyle": {
                    "color": BLUE if (term["ci_low"] > 1 or term["ci_high"] < 1)
                    else "#ffffff",
                    "borderColor": BLUE,
                    "borderWidth": 2,
                },
            }
            for index, term in enumerate(terms)
        ],
        "symbolSize": 13,
        "z": 3,
    }

    bounds = [term["ci_low"] for term in terms] + [term["ci_high"] for term in terms]
    lowest = min([*bounds, 1.0]) / 1.25
    highest = max([*bounds, 1.0]) * 1.25

    options = _base()
    options.update({
        "title": {"text": title, "left": 0, "top": 0,
                  "textStyle": {"fontSize": 13, "fontWeight": 600}},
        "grid": {"left": 190, "right": 40, "top": 44, "bottom": 52},
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}: {c}",
        },
        "xAxis": {
            "type": "log",
            "name": f"{model.get('measure', 'Estimate')} (95% CI)",
            "nameLocation": "middle",
            "nameGap": 32,
            "min": round(lowest, 3),
            "max": round(highest, 3),
            "axisLabel": {"formatter": "{value}"},
            "splitLine": {"lineStyle": {"type": "dashed", "opacity": 0.4}},
        },
        "yAxis": {
            "type": "category",
            "data": labels,
            "axisLabel": {"fontSize": 11, "width": 175, "overflow": "truncate"},
            "axisTick": {"show": False},
        },
        "series": [
            *whiskers,
            points,
            {
                "type": "line",
                "markLine": {
                    "silent": True,
                    "symbol": "none",
                    "label": {"show": False},
                    "lineStyle": {"color": "#94a3b8", "type": "dashed"},
                    "data": [{"xAxis": 1}],
                },
                "data": [],
            },
        ],
    })
    return options


def annual_trend(rows: list[dict]) -> dict:
    """Build an annual trend with a confidence band."""
    years = [str(row["year"]) for row in rows]
    estimate = [round((row["proportion"] or 0) * 100, 1) for row in rows]
    lower = [round((row["ci_low"] or 0) * 100, 1) for row in rows]
    span = [
        round(((row["ci_high"] or 0) - (row["ci_low"] or 0)) * 100, 1) for row in rows
    ]
    counts = [f"{row['successes']}/{row['total']}" for row in rows]

    options = _base()
    options.update({
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": years, "boundaryGap": False},
        "yAxis": _percent_axis("DKA among case records"),
        "series": [
            {
                "name": "lower", "type": "line", "stack": "band",
                "data": lower, "lineStyle": {"opacity": 0},
                "showSymbol": False, "silent": True, "tooltip": {"show": False},
            },
            {
                "name": "95% CI", "type": "line", "stack": "band",
                "data": span, "lineStyle": {"opacity": 0},
                "areaStyle": {"color": BLUE, "opacity": 0.15},
                "showSymbol": False, "silent": True, "tooltip": {"show": False},
            },
            {
                "name": "DKA share", "type": "line", "data": estimate,
                "smooth": False, "symbolSize": 7,
                "lineStyle": {"color": BLUE, "width": 3},
                "itemStyle": {"color": BLUE},
                "z": 3,
            },
            {
                "name": "counts", "type": "line", "data": counts,
                "lineStyle": {"opacity": 0}, "showSymbol": False,
                "tooltip": {"show": True},
            },
        ],
    })
    return options


def severity_donut(rows: list[dict]) -> dict:
    colours = {
        "Severe": RED, "Moderate": "#f97316", "Mild": "#facc15",
        "No DKA": "#cbd5e1", "Unknown": "#e2e8f0",
    }
    return {
        "animationDuration": 300,
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"bottom": 0, "type": "scroll"},
        "series": [{
            "type": "pie",
            "radius": ["48%", "72%"],
            "center": ["50%", "44%"],
            "avoidLabelOverlap": True,
            "label": {"formatter": "{b}\n{c}"},
            "data": [
                {"name": row["label"], "value": row["count"],
                 "itemStyle": {"color": colours.get(row["label"], SLATE)}}
                for row in rows
            ],
        }],
    }


def _grouped_share(rows: list[dict], key: str, name: str, colour_map=None) -> dict:
    """Build grouped proportions with confidence intervals."""
    labels = [f"{row['label']} (n={row['cases']})" for row in rows]

    def pct(row, bound):
        return round((row[key][bound] or 0) * 100, 1)

    values = [pct(row, "proportion") for row in rows]

    whiskers = [
        [
            {"coord": [index, pct(row, "ci_low")]},
            {"coord": [index, pct(row, "ci_high")]},
        ]
        for index, row in enumerate(rows)
    ]

    options = _base()
    options.update({
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "xAxis": {"type": "category", "data": labels, "axisLabel": {"fontSize": 11}},
        "yAxis": _percent_axis(name),
        "series": [
            {
                "name": name,
                "type": "bar",
                "data": [
                    {"value": value,
                     "itemStyle": {"color": (colour_map or {}).get(row["label"], BLUE)}}
                    for value, row in zip(values, rows)
                ],
                "barMaxWidth": 64,
                "label": {"show": True, "position": "top", "formatter": "{c}%"},
                "markLine": {
                    "silent": True,
                    "symbol": ["none", "none"],
                    "label": {"show": False},
                    "lineStyle": {"color": "#0f172a", "width": 2, "type": "solid"},
                    "emphasis": {"disabled": True},
                    "data": whiskers,
                },
            },
        ],
    })
    return options


def deprivation_gradient(rows: list[dict], key: str = "severe") -> dict:
    name = "Severe DKA" if key == "severe" else "DKA among case records"
    return _grouped_share(rows, key, name, GRADIENT)


def age_gradient(rows: list[dict], key: str = "dka") -> dict:
    return _grouped_share(rows, key, "DKA among case records")


def sex_gradient(rows: list[dict], key: str = "dka") -> dict:
    return _grouped_share(
        rows, key, "DKA among case records", {"Male": BLUE, "Female": "#ec4899"}
    )


def duration_box(rows: list[dict]) -> dict:
    """Median symptom duration per deprivation tertile with the interquartile range."""
    labels = [f"{row['label']} (n={row['n']})" for row in rows]
    options = _base()
    options.update({
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "category", "data": labels, "axisLabel": {"fontSize": 11}},
        "yAxis": {
            "type": "value", "name": "Days of symptoms",
            "nameLocation": "middle", "nameGap": 44, "min": 0,
        },
        "series": [
            {
                "type": "boxplot",
                "data": [
                    [row["q1"], row["q1"], row["median"], row["q3"], row["q3"]]
                    for row in rows
                ],
                "itemStyle": {"color": "#e0f2fe", "borderColor": TEAL, "borderWidth": 2},
                "boxWidth": [20, 55],
            },
        ],
    })
    return options


def period_windows(pandemic: dict) -> dict:
    """The three fixed calendar windows, with intervals."""
    windows = [pandemic["before"], pandemic["during"], pandemic["after"]]
    rows = [
        {
            "label": window["label"],
            "cases": window["total"],
            "share": window,
        }
        for window in windows
    ]
    colours = {
        windows[0]["label"]: SLATE,
        windows[1]["label"]: RED,
        windows[2]["label"]: SLATE,
    }
    return _grouped_share(rows, "share", "DKA among case records", colours)


def district_shares(rows: list[dict]) -> dict:
    """Pooled proportion per district, with intervals and denominators."""
    usable = [row for row in rows if row["total"] > 0]
    prepared = [
        {"label": row["kreis"], "cases": row["total"], "share": row}
        for row in usable
    ]
    colours = {
        row["kreis"]: ("#94a3b8" if row["no_local_clinic"] else BLUE)
        for row in usable
    }
    return _grouped_share(prepared, "share", "DKA at manifestation", colours)
