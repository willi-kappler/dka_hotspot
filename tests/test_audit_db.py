
from datetime import datetime, timedelta, timezone

import pytest

import storage.audit_db as audit_module
from db import get_connection
from storage import audit_db
from storage.audit_db import compact_old_entries, failed_logins_since, recent, record
from storage.users_db import (
    create_user,
    reset_user_password,
    set_user_active,
    set_user_role,
)

PASSPHRASE = "a-valid-passphrase"


def test_an_entry_records_actor_action_and_target(temp_db):
    record(audit_db.USER_CREATED, actor="admin", target="alice", detail="role=user")
    entry = recent()[0]
    assert entry["actor"] == "admin"
    assert entry["action"] == audit_db.USER_CREATED
    assert entry["target"] == "alice"
    assert entry["detail"] == "role=user"


def test_entries_come_back_newest_first(temp_db):
    for name in ("first", "second", "third"):
        record(audit_db.USER_CREATED, actor="admin", target=name)
    assert [e["target"] for e in recent()] == ["third", "second", "first"]


def test_the_limit_is_respected(temp_db):
    for index in range(10):
        record(audit_db.LOGIN_FAILED, actor=f"u{index}")
    assert len(recent(limit=3)) == 3


def test_entries_can_be_filtered_by_action(temp_db):
    record(audit_db.LOGIN_FAILED, actor="alice")
    record(audit_db.LOGIN_SUCCEEDED, actor="alice")
    assert len(recent(action=audit_db.LOGIN_FAILED)) == 1


def test_an_absent_actor_is_attributed_to_the_system(temp_db):
    record(audit_db.CASES_IMPORTED, actor=None, detail="rows=500")
    assert recent()[0]["actor"] == audit_db.SYSTEM_ACTOR
    record(audit_db.CASES_IMPORTED, actor="   ")
    assert recent()[0]["actor"] == audit_db.SYSTEM_ACTOR


def test_timestamps_are_utc_and_sortable(temp_db):
    record(audit_db.LOGIN_SUCCEEDED, actor="alice")
    at = recent()[0]["at"]
    assert at.endswith("+00:00"), "timestamps must be unambiguous across zones"


def test_auditing_never_breaks_the_action_it_records(monkeypatch, temp_db):
    def explode(*_args, **_kwargs):
        raise RuntimeError("database is gone")

    monkeypatch.setattr(audit_db, "get_connection", explode)
    record(audit_db.LOGIN_SUCCEEDED, actor="alice")   # must not raise


def test_failed_login_counter_covers_failures_and_blocks(temp_db):
    record(audit_db.LOGIN_FAILED, actor="alice")
    record(audit_db.LOGIN_BLOCKED, actor="alice")
    record(audit_db.LOGIN_SUCCEEDED, actor="alice")
    assert failed_logins_since("2000-01-01T00:00:00+00:00") == 2
    assert failed_logins_since("2999-01-01T00:00:00+00:00") == 0



def test_creating_a_user_is_audited_with_the_role_granted(temp_db):
    create_user("alice", PASSPHRASE, "admin", actor="root")
    entry = recent()[0]
    assert entry["action"] == audit_db.USER_CREATED
    assert entry["actor"] == "root"
    assert entry["target"] == "alice"
    assert "admin" in entry["detail"]


def test_a_role_change_is_audited(temp_db):
    create_user("alice", PASSPHRASE, "user", actor="root")
    set_user_role("alice", "admin", actor="root")
    entry = recent()[0]
    assert entry["action"] == audit_db.USER_ROLE_CHANGED
    assert "admin" in entry["detail"]


def test_deactivation_and_reactivation_are_distinguishable(temp_db):
    create_user("alice", PASSPHRASE, "user", actor="root")
    set_user_active("alice", False, actor="root")
    assert recent()[0]["action"] == audit_db.USER_DEACTIVATED
    set_user_active("alice", True, actor="root")
    assert recent()[0]["action"] == audit_db.USER_ACTIVATED


def test_a_password_reset_is_audited_without_the_password(temp_db):
    create_user("alice", PASSPHRASE, "user", actor="root")
    reset_user_password("alice", "a-brand-new-passphrase", actor="root")
    entry = recent()[0]
    assert entry["action"] == audit_db.USER_PASSWORD_RESET
    assert "passphrase" not in entry["detail"].lower()
    assert entry["detail"] == ""


def test_no_audit_entry_anywhere_contains_a_password_or_hash(temp_db):
    create_user("alice", PASSPHRASE, "admin", actor="root")
    set_user_role("alice", "user", actor="root")
    reset_user_password("alice", "another-fresh-passphrase", actor="root")
    for entry in recent():
        blob = f"{entry['target']} {entry['detail']}".lower()
        assert "passphrase" not in blob
        assert "$2b$" not in blob, "a bcrypt hash must never reach the trail"


def test_a_failed_create_leaves_no_audit_entry(temp_db):
    with pytest.raises(ValueError):
        create_user("alice", "short", "user", actor="root")
    assert recent() == []


def _insert_audit_entry(at: datetime, action: str, actor: str = "tester") -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (at, actor, action, target, detail)
            VALUES (?, ?, ?, '', '')
            """,
            (at.isoformat(timespec="seconds"), actor, action),
        )


def test_old_entries_are_replaced_with_daily_action_counts(temp_db):
    now = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)
    old = now - timedelta(days=audit_db.RETENTION_DAYS + 1)
    recent_at = now - timedelta(days=10)
    _insert_audit_entry(old, audit_db.LOGIN_FAILED, "alice")
    _insert_audit_entry(old + timedelta(hours=1), audit_db.LOGIN_FAILED, "bob")
    _insert_audit_entry(old, audit_db.LOGIN_BLOCKED, "alice")
    _insert_audit_entry(recent_at, audit_db.LOGIN_FAILED, "carol")

    assert compact_old_entries(now) == 3

    with get_connection() as conn:
        summaries = conn.execute(
            "SELECT day, action, event_count FROM audit_summary ORDER BY action"
        ).fetchall()
    assert [(row["day"], row["action"], row["event_count"]) for row in summaries] == [
        (old.date().isoformat(), audit_db.LOGIN_BLOCKED, 1),
        (old.date().isoformat(), audit_db.LOGIN_FAILED, 2),
    ]
    assert [entry["actor"] for entry in recent()] == ["carol"]


def test_compaction_is_idempotent(temp_db):
    now = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)
    _insert_audit_entry(now - timedelta(days=100), audit_db.LOGIN_FAILED)
    assert compact_old_entries(now) == 1
    assert compact_old_entries(now) == 0
    with get_connection() as conn:
        count = conn.execute("SELECT event_count FROM audit_summary").fetchone()[0]
    assert count == 1


def test_an_entry_at_the_retention_boundary_remains_detailed(temp_db):
    now = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)
    _insert_audit_entry(now - timedelta(days=audit_db.RETENTION_DAYS), audit_db.LOGIN_FAILED)
    assert compact_old_entries(now) == 0
    assert len(recent()) == 1


def test_automatic_compaction_runs_at_most_once_per_utc_day(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_module, "_last_compaction_date", None)
    monkeypatch.setattr(audit_module, "compact_old_entries", lambda now: calls.append(now))
    first = datetime(2026, 8, 31, 8, tzinfo=timezone.utc)

    audit_module._compact_if_due(first)
    audit_module._compact_if_due(first + timedelta(hours=10))
    audit_module._compact_if_due(first + timedelta(days=1))

    assert calls == [first, first + timedelta(days=1)]
