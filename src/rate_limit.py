"""Per-process login throttling by username."""

import threading
import time

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300

_lock = threading.Lock()
_failed_attempts: dict[str, tuple[int, float]] = {}


class LockedOutError(Exception):
    pass


def check_not_locked_out(username: str) -> None:
    with _lock:
        count, first_failed_at = _failed_attempts.get(username, (0, 0.0))
        if count < MAX_ATTEMPTS:
            return

        remaining = LOCKOUT_SECONDS - (time.monotonic() - first_failed_at)
        if remaining <= 0:
            _failed_attempts.pop(username, None)
            return

    raise LockedOutError(f"Too many failed attempts. Try again in {int(remaining) + 1} seconds.")


def record_failure(username: str) -> None:
    with _lock:
        count, first_failed_at = _failed_attempts.get(username, (0, time.monotonic()))
        if time.monotonic() - first_failed_at > LOCKOUT_SECONDS:
            count, first_failed_at = 0, time.monotonic()
        _failed_attempts[username] = (count + 1, first_failed_at)


def record_success(username: str) -> None:
    with _lock:
        _failed_attempts.pop(username, None)
