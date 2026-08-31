
import pytest

from storage import audit_db
from storage.audit_db import failed_logins_since, recent, record
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
