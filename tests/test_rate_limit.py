
import pytest

import rate_limit
from rate_limit import (
    LOCKOUT_SECONDS,
    MAX_ATTEMPTS,
    LockedOutError,
    check_not_locked_out,
    record_failure,
    record_success,
)


@pytest.fixture(autouse=True)
def clean_slate():
    rate_limit._failed_attempts.clear()
    yield
    rate_limit._failed_attempts.clear()


@pytest.fixture
def clock(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now["t"])
    return now


def test_a_fresh_username_is_not_locked_out():
    check_not_locked_out("alice")


def test_lockout_begins_only_after_the_limit_is_reached(clock):
    for _ in range(MAX_ATTEMPTS - 1):
        record_failure("alice")
    check_not_locked_out("alice")            # still allowed at 4 failures

    record_failure("alice")
    with pytest.raises(LockedOutError):
        check_not_locked_out("alice")


def test_the_lockout_message_says_how_long_to_wait(clock):
    for _ in range(MAX_ATTEMPTS):
        record_failure("alice")
    with pytest.raises(LockedOutError, match="seconds"):
        check_not_locked_out("alice")


def test_a_successful_login_clears_the_counter(clock):
    for _ in range(MAX_ATTEMPTS - 1):
        record_failure("alice")
    record_success("alice")
    for _ in range(MAX_ATTEMPTS - 1):
        record_failure("alice")
    check_not_locked_out("alice")


def test_the_lockout_expires(clock):
    for _ in range(MAX_ATTEMPTS):
        record_failure("alice")
    with pytest.raises(LockedOutError):
        check_not_locked_out("alice")

    clock["t"] += LOCKOUT_SECONDS + 1
    check_not_locked_out("alice")            # expired, and the entry is dropped
    assert "alice" not in rate_limit._failed_attempts


def test_lockout_is_measured_from_the_first_failure_in_the_window(clock):
    record_failure("alice")
    clock["t"] += 100
    for _ in range(MAX_ATTEMPTS - 1):
        record_failure("alice")
    with pytest.raises(LockedOutError):
        check_not_locked_out("alice")

    clock["t"] += LOCKOUT_SECONDS - 100 + 1
    check_not_locked_out("alice")


def test_failures_spread_beyond_the_window_do_not_accumulate(clock):
    for _ in range(MAX_ATTEMPTS - 1):
        record_failure("alice")
    clock["t"] += LOCKOUT_SECONDS + 1
    for _ in range(MAX_ATTEMPTS - 1):
        record_failure("alice")
    check_not_locked_out("alice")


def test_usernames_are_throttled_independently(clock):
    for _ in range(MAX_ATTEMPTS):
        record_failure("alice")
    with pytest.raises(LockedOutError):
        check_not_locked_out("alice")
    check_not_locked_out("bob")
