import logging

from nicegui import ui, app
from env import get_env
from pages.login import login_page
from pages import map_view, add_data, admin, admin_cases, hotspot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def get_role() -> str | None:
    return app.storage.user.get("role")


@ui.page("/")
def index():
    if get_role():
        ui.navigate.to("/map")
    else:
        login_page()


@ui.page("/logout")
def logout():
    app.storage.user.clear()
    ui.navigate.to("/")


if __name__ in {"__main__", "__mp_main__"}:
    storage_secret = get_env("NICEGUI_STORAGE_SECRET")
    if not storage_secret:
        raise RuntimeError(
            "Set NICEGUI_STORAGE_SECRET in the environment or local .env file before running the app."
        )
    ui.run(title="DKA Hotspot Analysis Map", port=8080, storage_secret=storage_secret)
