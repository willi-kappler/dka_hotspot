from rate_limit import check_not_locked_out, record_failure, record_success
from storage.users_db import authenticate_user


def authenticate(username: str, password: str) -> str | None:
    """Return role if credentials match an active database user.

    Raises LockedOutError if this username has failed too many times recently.
    """
    check_not_locked_out(username)

    role = authenticate_user(username, password)
    if role:
        record_success(username)
        return role

    record_failure(username)
    return None
