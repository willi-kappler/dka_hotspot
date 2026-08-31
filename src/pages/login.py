from nicegui import app, ui

from auth import authenticate
from rate_limit import LockedOutError


def login_page():
    with ui.column().classes("w-full h-screen items-center justify-center gap-6 bg-slate-50"):
        with ui.column().classes("items-center gap-1"):
            ui.label("DKA-Hotspot-Analyse").classes("text-3xl font-bold text-blue-800")
            ui.label(
                "Ketoacidosis at type 1 diabetes manifestation · "
                "Tübingen, Reutlingen, Zollernalbkreis"
            ).classes("text-sm text-slate-500")

        with ui.card().classes("w-96 p-6 gap-4 shadow-sm"):
            username = ui.input("Username").props("outlined dense").classes("w-full")
            password = ui.input(
                "Password", password=True, password_toggle_button=True
            ).props("outlined dense").classes("w-full")
            error = ui.label("").classes("text-red-600 text-sm")

            def try_login():
                try:
                    role = authenticate(username.value.strip(), password.value)
                except LockedOutError as exception:
                    error.text = str(exception)
                    return
                if role:
                    app.storage.user["role"] = role
                    app.storage.user["username"] = username.value.strip()
                    ui.navigate.to("/overview")
                else:
                    error.text = "Invalid username or password."

            password.on("keydown.enter", lambda _: try_login())
            ui.button("Log in", on_click=try_login).classes("w-full bg-blue-700 text-white")
