"""Append-only audit trail."""

import logging
import threading
from datetime import date, datetime, timedelta, timezone

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

RETENTION_DAYS = 90

_compaction_lock = threading.Lock()
_last_compaction_date: date | None = None


def compact_old_entries(now: datetime | None = None) -> int:
    """Replace detailed entries older than the retention period with daily counts."""
    current = now or datetime.now(timezone.utc)
    cutoff = (current - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_summary (day, action, event_count)
            SELECT substr(at, 1, 10), action, COUNT(*)
            FROM audit_log
            WHERE at < ?
            GROUP BY substr(at, 1, 10), action
            ON CONFLICT (day, action) DO UPDATE SET
                event_count = audit_summary.event_count + excluded.event_count
            """,
            (cutoff,),
        )
        deleted = conn.execute("DELETE FROM audit_log WHERE at < ?", (cutoff,))
        return deleted.rowcount


def _compact_if_due(now: datetime | None = None) -> None:
    """Run compaction no more than once per UTC calendar day."""
    global _last_compaction_date
    current = now or datetime.now(timezone.utc)
    today = current.date()
    with _compaction_lock:
        if _last_compaction_date == today:
            return
        compact_old_entries(current)
        _last_compaction_date = today


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
        return

    try:
        _compact_if_due()
    except Exception:
        logger.exception("Could not compact old audit entries")


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
