import bcrypt

from db import get_connection, init_db

ROLES = {"user", "scientist", "admin"}


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hash_bytes)


def create_user(username: str, password: str, role: str) -> None:
    if role not in ROLES:
        raise ValueError("Role must be 'user', 'scientist', or 'admin'.")

    clean_username = username.strip()
    if not clean_username:
        raise ValueError("Username is required.")

    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (clean_username, hash_password(password), role),
        )


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


def set_user_active(username: str, is_active: bool) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_active = ? WHERE username = ?",
            (1 if is_active else 0, username.strip()),
        )


def set_user_role(username: str, role: str) -> None:
    if role not in ROLES:
        raise ValueError("Role must be 'user', 'scientist', or 'admin'.")

    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (role, username.strip()),
        )


def reset_user_password(username: str, password: str) -> None:
    if not password:
        raise ValueError("Password is required.")

    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hash_password(password), username.strip()),
        )


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
