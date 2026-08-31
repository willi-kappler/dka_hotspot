import logging

from nicegui import app, ui

from db import init_db
from env import get_env
from pages import (  # noqa: F401  (importing registers the routes)
    admin,
    analysis,
    data,
    map_view,
    overview,
)
from pages.login import login_page
from security import ConfigurationError, is_production, startup_report

DEFAULT_PORT = 8081

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@ui.page("/")
def index():
    if app.storage.user.get("role"):
        ui.navigate.to("/overview")
    else:
        login_page()


@ui.page("/logout")
def logout():
    app.storage.user.clear()
    ui.navigate.to("/")


if __name__ in {"__main__", "__mp_main__"}:
    init_db()
    storage_secret = get_env("NICEGUI_STORAGE_SECRET")

    try:
        cookie_settings, warnings = startup_report(storage_secret)
    except ConfigurationError as error:
        raise SystemExit(f"\n{error}\n") from None
    for warning in warnings:
        logging.getLogger(__name__).warning(warning)

    try:
        port = int(get_env("DKA_PORT") or DEFAULT_PORT)
    except ValueError:
        raise SystemExit(f"DKA_PORT must be a number, got {get_env('DKA_PORT')!r}") from None

    ui.run(
        title="DKA-Hotspot-Analyse",
        port=port,
        storage_secret=storage_secret,
        session_middleware_kwargs=cookie_settings,
        reload=not is_production(),
    )
