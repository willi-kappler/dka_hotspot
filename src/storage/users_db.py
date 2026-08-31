"""User accounts and password management."""

import bcrypt

from db import get_connection, init_db
from storage import audit_db

ROLES = {"user", "scientist", "admin"}

MIN_PASSWORD_LENGTH = 12

# bcrypt ignores bytes after this limit.
MAX_PASSWORD_BYTES = 72


def validate_password(password: str) -> None:
    """Raise ValueError if the password cannot be used."""
    if password is None or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters. "
            "A memorable passphrase of several words is stronger than a short "
            "string with substitutions."
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes; bcrypt "
            "ignores anything beyond that."
        )


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hash_bytes)


def create_user(username: str, password: str, role: str, actor: str | None = None) -> None:
    if role not in ROLES:
        raise ValueError("Role must be 'user', 'scientist', or 'admin'.")

    clean_username = username.strip()
    if not clean_username:
        raise ValueError("Username is required.")
    validate_password(password)

    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (clean_username, hash_password(password), role),
        )
    audit_db.record(audit_db.USER_CREATED, actor, clean_username, f"role={role}")


def list_users() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, username, role, is_active, created_at
            FROM users
            ORDER BY username
            """
        ).fetchall()
    return [dict(row) for row in rows]


def set_user_active(username: str, is_active: bool, actor: str | None = None) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_active = ? WHERE username = ?",
            (1 if is_active else 0, username.strip()),
        )
    audit_db.record(
        audit_db.USER_ACTIVATED if is_active else audit_db.USER_DEACTIVATED,
        actor, username.strip(),
    )


def set_user_role(username: str, role: str, actor: str | None = None) -> None:
    if role not in ROLES:
        raise ValueError("Role must be 'user', 'scientist', or 'admin'.")

    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (role, username.strip()),
        )
    audit_db.record(audit_db.USER_ROLE_CHANGED, actor, username.strip(), f"role={role}")


def reset_user_password(username: str, password: str, actor: str | None = None) -> None:
    if not password:
        raise ValueError("Password is required.")
    validate_password(password)

    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(password), username.strip()),
        )
    audit_db.record(audit_db.USER_PASSWORD_RESET, actor, username.strip())


def find_active_user(username: str):
    init_db()
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT username, password_hash, role
            FROM users
            WHERE username = ? AND is_active = 1
            """,
            (username.strip(),),
        ).fetchone()


def authenticate_user(username: str, password: str) -> str | None:
    user = find_active_user(username)
    if user and check_password(password, user["password_hash"]):
        return user["role"]
    return None
