
import pytest

import rate_limit
from auth import authenticate
from rate_limit import MAX_ATTEMPTS, LockedOutError
from storage.users_db import create_user, set_user_active


@pytest.fixture(autouse=True)
def clean_slate():
    rate_limit._failed_attempts.clear()
    yield
    rate_limit._failed_attempts.clear()


def test_valid_credentials_return_the_role(temp_db):
    create_user("alice", "correct-horse-battery", "scientist")
    assert authenticate("alice", "correct-horse-battery") == "scientist"


def test_a_wrong_password_returns_none(temp_db):
    create_user("alice", "correct-horse-battery", "scientist")
    assert authenticate("alice", "wrong") is None


def test_an_unknown_user_returns_none(temp_db):
    assert authenticate("nobody", "whatever") is None


def test_a_deactivated_account_cannot_log_in(temp_db):
    create_user("alice", "correct-horse-battery", "user")
    set_user_active("alice", False)
    assert authenticate("alice", "correct-horse-battery") is None


def test_repeated_failures_lock_the_account(temp_db):
    create_user("alice", "correct-horse-battery", "user")
    for _ in range(MAX_ATTEMPTS):
        assert authenticate("alice", "wrong") is None
    with pytest.raises(LockedOutError):
        authenticate("alice", "wrong")


def test_lockout_applies_even_to_the_correct_password(temp_db):
    create_user("alice", "correct-horse-battery", "user")
    for _ in range(MAX_ATTEMPTS):
        authenticate("alice", "wrong")
    with pytest.raises(LockedOutError):
        authenticate("alice", "correct-horse-battery")


def test_a_successful_login_resets_the_failure_count(temp_db):
    create_user("alice", "correct-horse-battery", "user")
    for _ in range(MAX_ATTEMPTS - 1):
        authenticate("alice", "wrong")
    assert authenticate("alice", "correct-horse-battery") == "user"
    assert "alice" not in rate_limit._failed_attempts


def test_an_unknown_username_is_throttled_too(temp_db):
    for _ in range(MAX_ATTEMPTS):
        authenticate("ghost", "wrong")
    with pytest.raises(LockedOutError):
        authenticate("ghost", "wrong")



def test_a_successful_login_is_audited_with_the_role(temp_db):
    from storage import audit_db

    create_user("alice", "correct-horse-battery", "scientist")
    authenticate("alice", "correct-horse-battery")
    entry = audit_db.recent(action=audit_db.LOGIN_SUCCEEDED)[0]
    assert entry["actor"] == "alice"
    assert "scientist" in entry["detail"]


def test_a_failed_login_is_audited(temp_db):
    from storage import audit_db

    create_user("alice", "correct-horse-battery", "user")
    authenticate("alice", "wrong-password-here")
    assert audit_db.recent(action=audit_db.LOGIN_FAILED)[0]["actor"] == "alice"


def test_an_attempt_while_locked_out_is_audited_separately(temp_db):
    from storage import audit_db

    create_user("alice", "correct-horse-battery", "user")
    for _ in range(MAX_ATTEMPTS):
        authenticate("alice", "wrong-password-here")
    with pytest.raises(LockedOutError):
        authenticate("alice", "wrong-password-here")
    assert audit_db.recent(action=audit_db.LOGIN_BLOCKED)


def test_the_audit_trail_never_records_the_attempted_password(temp_db):
    from storage import audit_db

    create_user("alice", "correct-horse-battery", "user")
    authenticate("alice", "hunter2-was-the-guess")
    for entry in audit_db.recent():
        assert "hunter2" not in f"{entry['target']}{entry['detail']}"
