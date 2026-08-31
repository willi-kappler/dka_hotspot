"""Session and startup security settings."""

import logging
import secrets

from env import get_env

logger = logging.getLogger(__name__)

PRODUCTION = "production"
DEVELOPMENT = "development"

SESSION_MAX_AGE_SECONDS = 8 * 60 * 60

MIN_SECRET_LENGTH = 32

PLACEHOLDER_SECRETS = {
    "secret", "changeme", "change-me", "password", "nicegui",
    "your-secret-key", "storage-secret", "test", "dev", "development",
}


class ConfigurationError(RuntimeError):
    """Raised for unsafe production configuration."""


def environment() -> str:
    """Return the current environment."""
    value = (get_env("DKA_ENV") or DEVELOPMENT).strip().lower()
    return PRODUCTION if value == PRODUCTION else DEVELOPMENT


def is_production() -> bool:
    return environment() == PRODUCTION


def generate_secret() -> str:
    """Generate a storage secret."""
    return secrets.token_urlsafe(48)


def check_secret(secret: str, production: bool) -> list[str]:
    """Return storage-secret validation errors."""
    problems = []
    if not secret:
        problems.append(
            "NICEGUI_STORAGE_SECRET is not set. Session cookies cannot be "
            "signed without it."
        )
        return problems
    if secret.strip().lower() in PLACEHOLDER_SECRETS:
        problems.append(
            f"NICEGUI_STORAGE_SECRET is a placeholder value ({secret!r}). "
            "Anyone can forge a session cookie claiming any role."
        )
    if len(secret) < MIN_SECRET_LENGTH:
        problems.append(
            f"NICEGUI_STORAGE_SECRET is {len(secret)} characters; at least "
            f"{MIN_SECRET_LENGTH} are needed to make the cookie signature "
            "impractical to attack offline."
        )
    if len(set(secret)) < 8:
        problems.append(
            "NICEGUI_STORAGE_SECRET has very little variety in its characters, "
            "which suggests it was typed rather than generated."
        )
    return problems


def session_middleware_kwargs(production: bool) -> dict:
    """Cookie settings for Starlette's SessionMiddleware."""
    return {
        "max_age": SESSION_MAX_AGE_SECONDS,
        "same_site": "strict",
        "https_only": production,
    }


def startup_report(secret: str) -> tuple[dict, list[str]]:
    """Validate configuration and return cookie settings and warnings."""
    production = is_production()
    problems = check_secret(secret, production)

    if problems and production:
        raise ConfigurationError(
            "Refusing to start in production with an unsafe configuration:\n  - "
            + "\n  - ".join(problems)
            + "\n\nGenerate one with:\n  python3 -c \"import secrets; "
              "print(secrets.token_urlsafe(48))\""
        )

    warnings = []
    if not production:
        warnings.append(
            "Running in DEVELOPMENT mode: session cookies are not marked Secure"
        )
    warnings.extend(problems)
    return session_middleware_kwargs(production), warnings
