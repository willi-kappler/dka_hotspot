from nicegui import ui, app
from pages.login import login_page
from pages import map_view, add_data


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
    ui.run(title="DKA Hotspot Analysis Map", port=8080, storage_secret="dkw-secret-key") #will change 
