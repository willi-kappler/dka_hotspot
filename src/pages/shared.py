"""Chrome shared across pages."""

from nicegui import app, ui

RESEARCH_ROLES = {"scientist", "admin"}


def current_role() -> str | None:
    return app.storage.user.get("role")


def require(*roles: str) -> bool:
    """Redirect and return False when the signed-in user lacks the role."""
    role = current_role()
    if not role:
        ui.navigate.to("/")
        return False
    if roles and role not in roles:
        ui.navigate.to("/overview")
        return False
    return True


def header(title: str, subtitle: str = ""):
    role = current_role()
    with ui.row().classes(
        "h-14 w-full shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-5 "
        "no-print"
    ):
        with ui.column().classes("gap-0"):
            ui.label(title).classes("text-base font-semibold text-slate-900")
            if subtitle:
                ui.label(subtitle).classes("text-xs text-slate-500")
        ui.space()
        ui.button("Overview", icon="map", on_click=lambda: ui.navigate.to("/overview")) \
            .props("flat dense").classes("text-blue-700")
        if role in RESEARCH_ROLES:
            ui.button("Case map", icon="scatter_plot",
                      on_click=lambda: ui.navigate.to("/map")) \
                .props("flat dense").classes("text-blue-700")
            ui.button("Analysis", icon="query_stats",
                      on_click=lambda: ui.navigate.to("/analysis")) \
                .props("flat dense").classes("text-blue-700")
            ui.button("Data", icon="upload_file",
                      on_click=lambda: ui.navigate.to("/data")) \
                .props("flat dense").classes("text-blue-700")
        if role == "admin":
            ui.button("Users", icon="admin_panel_settings",
                      on_click=lambda: ui.navigate.to("/admin/users")) \
                .props("flat dense").classes("text-blue-700")
        ui.button(icon="logout", on_click=lambda: ui.navigate.to("/logout")) \
            .props("flat round dense").classes("text-slate-600").tooltip("Log out")


def notice(text: str, tone: str = "info"):
    palette = {
        "info": ("bg-blue-50 border-blue-200 text-blue-900", "info", "blue-7"),
        "warn": ("bg-amber-50 border-amber-200 text-amber-900", "warning_amber", "amber-8"),
        "blocked": ("bg-slate-100 border-slate-300 text-slate-700", "pending", "slate-6"),
    }[tone]
    with ui.row().classes(
        f"w-full items-start gap-3 rounded-lg border p-4 {palette[0]}"
    ):
        ui.icon(palette[1], color=palette[2]).classes("text-xl")
        ui.label(text).classes("flex-1 text-sm leading-relaxed")


def percent(value: float | None, decimals: int = 1) -> str:
    return "—" if value is None else f"{value * 100:.{decimals}f}%"


def interval(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return "—"
    return f"{low * 100:.1f}–{high * 100:.1f}%"
