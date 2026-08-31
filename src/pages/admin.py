import logging
from datetime import datetime, timedelta, timezone
from sqlite3 import IntegrityError

from nicegui import app, ui

from storage import audit_db
from storage.users_db import (
    create_user,
    list_users,
    reset_user_password,
    set_user_active,
    set_user_role,
)

logger = logging.getLogger(__name__)


def _actor() -> str:
    """Return the signed-in administrator."""
    return app.storage.user.get("username") or "unknown"


@ui.page("/admin/users")
def admin_users_page():
    if app.storage.user.get("role") != "admin":
        ui.navigate.to("/")
        return

    with ui.column().classes("w-full min-h-screen gap-0 bg-gray-50"):
        with ui.row().classes("h-14 w-full items-center border-b border-gray-200 bg-white px-6 gap-4"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/overview")) \
                .props("flat round").tooltip("Back to map")
            ui.label("User Admin").classes("text-lg font-semibold text-gray-900")

        with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-6"):
            notice = ui.label("").classes("text-sm")

            with ui.card().classes("w-full p-4 gap-4"):
                ui.label("Create user").classes("text-base font-semibold")
                with ui.grid(columns=3).classes("w-full gap-3"):
                    username = ui.input("Username").props("outlined dense").classes("w-full")
                    role = ui.select(["user", "scientist", "admin"], value="user", label="Role").props("outlined dense").classes("w-full")
                    password = ui.input("Temporary password", password=True, password_toggle_button=True).props("outlined dense").classes("w-full")

                def save_user():
                    if not username.value or not password.value or not role.value:
                        notice.set_text("Please fill in username, password, and role.")
                        notice.classes("text-red-500", remove="text-green-600")
                        return
                    try:
                        create_user(username.value, password.value, role.value,
                                    actor=_actor())
                    except IntegrityError:
                        notice.set_text(f"Username '{username.value.strip()}' already exists.")
                        notice.classes("text-red-500", remove="text-green-600")
                        return
                    except ValueError as ex:
                        notice.set_text(str(ex))
                        notice.classes("text-red-500", remove="text-green-600")
                        return
                    except Exception:
                        logger.exception("Failed to create user %r", username.value.strip())
                        notice.set_text("Could not create user. Please try again.")
                        notice.classes("text-red-500", remove="text-green-600")
                        return

                    notice.set_text(f"Created {role.value} user: {username.value.strip()}")
                    notice.classes("text-green-600", remove="text-red-500")
                    username.set_value("")
                    password.set_value("")
                    role.set_value("user")
                    users_table.refresh()

                ui.button("Create user", icon="person_add", on_click=save_user) \
                    .classes("bg-blue-700 text-white")

            @ui.refreshable
            def users_table():
                with ui.card().classes("w-full p-0 gap-0"):
                    with ui.row().classes("w-full items-center border-b border-gray-200 px-4 py-3"):
                        ui.label("Existing users").classes("text-base font-semibold")
                        ui.space()
                        ui.label("Passwords are never displayed. Use reset to set a new temporary password.") \
                            .classes("text-xs text-gray-500")

                    for user in list_users():
                        is_current_user = user["username"] == app.storage.user.get("username")
                        with ui.row().classes("w-full items-center gap-3 border-b border-gray-100 px-4 py-3"):
                            status = "Active" if user["is_active"] else "Inactive"
                            status_classes = "text-green-700 bg-green-50" if user["is_active"] else "text-gray-500 bg-gray-100"

                            with ui.column().classes("gap-0 w-44 shrink-0"):
                                ui.label(user["username"]).classes("font-medium text-gray-900")
                                ui.label(status).classes(f"w-fit rounded px-2 py-0.5 text-xs {status_classes}")

                            role_select = ui.select(
                                ["user", "scientist", "admin"],
                                value=user["role"],
                                label="Role",
                                on_change=lambda e, u=user["username"]: (
                                    set_user_role(u, e.value, actor=_actor()),
                                    notice.set_text(f"Updated role for {u}."),
                                    notice.classes("text-green-600", remove="text-red-500"),
                                    users_table.refresh(),
                                ),
                            ).props("outlined dense").classes("w-40")
                            if is_current_user:
                                role_select.disable()

                            reset_password = ui.input(
                                "New temporary password",
                                password=True,
                                password_toggle_button=True,
                            ).props("outlined dense").classes("flex-1 min-w-48")

                            def save_password(target_username=user["username"], password_input=reset_password):
                                if not password_input.value:
                                    notice.set_text("Enter a new temporary password first.")
                                    notice.classes("text-red-500", remove="text-green-600")
                                    return
                                try:
                                    reset_user_password(target_username, password_input.value,
                                                        actor=_actor())
                                except ValueError as ex:
                                    notice.set_text(str(ex))
                                    notice.classes("text-red-500", remove="text-green-600")
                                    return
                                except Exception:
                                    logger.exception("Failed to reset password for %r", target_username)
                                    notice.set_text("Could not reset password. Please try again.")
                                    notice.classes("text-red-500", remove="text-green-600")
                                    return
                                password_input.set_value("")
                                notice.set_text(f"Reset password for {target_username}.")
                                notice.classes("text-green-600", remove="text-red-500")

                            ui.button("Reset", icon="key", on_click=save_password).props("outline") \
                                .classes("text-blue-700")

                            if user["is_active"]:
                                deactivate_button = ui.button(
                                    "Deactivate",
                                    icon="block",
                                    on_click=lambda u=user["username"]: (
                                        set_user_active(u, False, actor=_actor()),
                                        notice.set_text(f"Deactivated {u}."),
                                        notice.classes("text-green-600", remove="text-red-500"),
                                        users_table.refresh(),
                                    ),
                                ).props("outline").classes("text-red-600")
                                if is_current_user:
                                    deactivate_button.disable()
                            else:
                                ui.button(
                                    "Reactivate",
                                    icon="check_circle",
                                    on_click=lambda u=user["username"]: (
                                        set_user_active(u, True, actor=_actor()),
                                        notice.set_text(f"Reactivated {u}."),
                                        notice.classes("text-green-600", remove="text-red-500"),
                                        users_table.refresh(),
                                    ),
                                ).props("outline").classes("text-green-700")

            users_table()

            with ui.card().classes("w-full p-0 gap-0"):
                with ui.row().classes(
                    "w-full items-center border-b border-gray-200 px-4 py-3"
                ):
                    ui.label("Audit trail").classes("text-base font-semibold")
                    ui.space()
                    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                    failures = audit_db.failed_logins_since(since)
                    ui.label(
                        f"{failures} failed or blocked logins in the last 7 days"
                    ).classes(
                        "text-xs " + ("text-red-600 font-medium" if failures > 20
                                      else "text-gray-500")
                    )
                entries = audit_db.recent(limit=200)
                if not entries:
                    ui.label("No entries yet.").classes("px-4 py-3 text-sm text-gray-500")
                else:
                    ui.table(
                        columns=[
                            {"name": "at", "label": "When (UTC)", "field": "at",
                             "align": "left", "sortable": True},
                            {"name": "actor", "label": "Who", "field": "actor",
                             "align": "left", "sortable": True},
                            {"name": "action", "label": "Action", "field": "action",
                             "align": "left", "sortable": True},
                            {"name": "target", "label": "Target", "field": "target",
                             "align": "left"},
                            {"name": "detail", "label": "Detail", "field": "detail",
                             "align": "left"},
                        ],
                        rows=entries,
                        row_key="id",
                        pagination={"rowsPerPage": 15},
                    ).props("flat dense").classes("w-full")
                ui.label(
                    "Append-only: nothing in the application edits or deletes "
                    "these rows. Passwords and patient identifiers are never "
                    "recorded here."
                ).classes("px-4 py-2 text-xs text-gray-500")
