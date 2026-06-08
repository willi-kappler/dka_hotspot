CREDENTIALS: dict[str, dict] = {
    "user":      {"password": "user123",  "role": "user"},
    "scientist": {"password": "sci123",   "role": "scientist"},
}


def authenticate(username: str, password: str) -> str | None:
    """Return role if credentials match, else None."""
    entry = CREDENTIALS.get(username)
    if entry and entry["password"] == password:
        return entry["role"]
    return None
