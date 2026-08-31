"""Authentication and login auditing."""

import logging

from rate_limit import LockedOutError, check_not_locked_out, record_failure, record_success
from storage import audit_db
from storage.users_db import authenticate_user

logger = logging.getLogger(__name__)


def authenticate(username: str, password: str) -> str | None:
    """Return the role for valid credentials."""
    clean_username = (username or "").strip()

    try:
        check_not_locked_out(clean_username)
    except LockedOutError:
        audit_db.record(audit_db.LOGIN_BLOCKED, clean_username)
        logger.warning("Login attempt for %r while locked out", clean_username)
        raise

    role = authenticate_user(clean_username, password)
    if role:
        record_success(clean_username) # wipes failure counter
        audit_db.record(audit_db.LOGIN_SUCCEEDED, clean_username, detail=f"role={role}")
        return role

    record_failure(clean_username)
    audit_db.record(audit_db.LOGIN_FAILED, clean_username)
    logger.info("Failed login for %r", clean_username)
    return None
