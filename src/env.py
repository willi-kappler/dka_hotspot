import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def get_env(key: str) -> str:
    """Return an environment variable, falling back to the project .env file."""
    value = os.getenv(key)
    if value:
        return value

    if not ENV_FILE.exists():
        return ""

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        file_key, separator, file_value = line.partition("=")
        if separator and file_key.strip() == key:
            return file_value.strip().strip('"').strip("'")

    return ""
