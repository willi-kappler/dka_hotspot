"""Append-only audit trail."""

import logging
from datetime import datetime, timezone

from db import get_connection, init_db

logger = logging.getLogger(__name__)

LOGIN_SUCCEEDED = "login.succeeded"
LOGIN_FAILED = "login.failed"
LOGIN_BLOCKED = "login.blocked"

USER_CREATED = "user.created"
USER_ROLE_CHANGED = "user.role_changed"
USER_ACTIVATED = "user.activated"
USER_DEACTIVATED = "user.deactivated"
USER_PASSWORD_RESET = "user.password_reset"

CASES_IMPORTED = "data.cases_imported"
CASES_REPLACED = "data.cases_replaced"
ONSETS_IMPORTED = "data.onsets_imported"

SYSTEM_ACTOR = "system"


def record(action: str, actor: str | None = None, target: str = "", detail: str = "") -> None:
    """Append an audit entry without interrupting the audited action."""
    try:
        init_db()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (at, actor, action, target, detail)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    (actor or SYSTEM_ACTOR).strip() or SYSTEM_ACTOR,
                    action,
                    str(target).strip(),
                    str(detail).strip(),
                ),
            )
    except Exception:
        logger.exception("Could not write audit entry %r", action)


def recent(limit: int = 200, action: str | None = None) -> list[dict]:
    """Return recent entries, newest first."""
    init_db()
    query = "SELECT id, at, actor, action, target, detail FROM audit_log"
    parameters: list = []
    if action:
        query += " WHERE action = ?"
        parameters.append(action)
    query += " ORDER BY id DESC LIMIT ?"
    parameters.append(int(limit))
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(query, parameters).fetchall()]


def failed_logins_since(iso_timestamp: str) -> int:
    """Count failed and blocked logins since a timestamp."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM audit_log
            WHERE action IN (?, ?) AND at >= ?
            """,
            (LOGIN_FAILED, LOGIN_BLOCKED, iso_timestamp),
        ).fetchone()
    return row["n"]
