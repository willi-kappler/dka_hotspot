from nicegui import ui, app
from auth import authenticate
from rate_limit import LockedOutError


def login_page():
    with ui.column().classes("w-full h-screen items-center justify-center gap-6"):
        ui.label("DKA Hotspot Analysis Map").classes("text-4xl font-bold text-blue-700")
        ui.label("Please log in to continue").classes("text-gray-400")

        with ui.card().classes("w-80 p-6 gap-4"):
            username = ui.input("Username").classes("w-full")
            password = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")
            error = ui.label("").classes("text-red-500 text-sm")

            def try_login():
                try:
                    role = authenticate(username.value.strip(), password.value)
                except LockedOutError as ex:
                    error.text = str(ex)
                    return

                if role:
                    app.storage.user["role"] = role
                    app.storage.user["username"] = username.value.strip()
                    ui.navigate.to("/map")
                else:
                    error.text = "Invalid username or password."

            password.on("keydown.enter", lambda _: try_login())
            ui.button("Log in", on_click=try_login).classes("w-full bg-blue-600 text-white")
