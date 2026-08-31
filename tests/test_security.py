
import pytest

import security
from security import (
    DEVELOPMENT,
    MIN_SECRET_LENGTH,
    PRODUCTION,
    SESSION_MAX_AGE_SECONDS,
    ConfigurationError,
    check_secret,
    environment,
    generate_secret,
    is_production,
    session_middleware_kwargs,
    startup_report,
)

STRONG = "x7Kq2mVp9LtRw4Nc8ZbY6hJd3FgS5aQe1UoIvTnMlPkXjHrB"


@pytest.fixture
def env_mode(monkeypatch):
    def set_mode(value):
        monkeypatch.setattr(security, "get_env",
                            lambda key: value if key == "DKA_ENV" else "")
    return set_mode



def test_development_is_the_default(env_mode):
    env_mode("")
    assert environment() == DEVELOPMENT
    assert is_production() is False


def test_production_must_be_asked_for_explicitly(env_mode):
    env_mode("production")
    assert environment() == PRODUCTION
    assert is_production() is True


@pytest.mark.parametrize("value", ["prod", "PRODUCTION ", "Production"])
def test_production_is_matched_case_insensitively_but_not_abbreviated(env_mode, value):
    env_mode(value)
    expected = PRODUCTION if value.strip().lower() == "production" else DEVELOPMENT
    assert environment() == expected


def test_an_unrecognised_environment_falls_back_to_development(env_mode):
    env_mode("staging-ish")
    assert environment() == DEVELOPMENT



def test_a_strong_secret_has_no_problems():
    assert check_secret(STRONG, production=True) == []


def test_a_missing_secret_is_reported():
    problems = check_secret("", production=True)
    assert problems and "not set" in problems[0]


@pytest.mark.parametrize("placeholder", ["secret", "changeme", "CHANGEME", "nicegui", "test"])
def test_placeholder_secrets_are_rejected(placeholder):
    problems = check_secret(placeholder, production=True)
    assert any("placeholder" in problem for problem in problems)


def test_a_short_secret_is_rejected():
    problems = check_secret("aB3dE6gH9jK", production=True)
    assert any(str(MIN_SECRET_LENGTH) in problem for problem in problems)


def test_a_secret_at_the_minimum_length_is_accepted():
    assert check_secret(STRONG[:MIN_SECRET_LENGTH], production=True) == []


def test_a_long_but_repetitive_secret_is_rejected():
    problems = check_secret("abababababababababababababababababababab", production=True)
    assert any("variety" in problem for problem in problems)


def test_generated_secrets_pass_their_own_check():
    for _ in range(10):
        assert check_secret(generate_secret(), production=True) == []


def test_generated_secrets_are_not_repeated():
    assert len({generate_secret() for _ in range(20)}) == 20



def test_production_cookies_are_secure_strict_and_expiring():
    settings = session_middleware_kwargs(production=True)
    assert settings["https_only"] is True
    assert settings["same_site"] == "strict"
    assert settings["max_age"] == SESSION_MAX_AGE_SECONDS


def test_the_session_expires_within_a_working_day():
    assert 0 < SESSION_MAX_AGE_SECONDS <= 12 * 3600


def test_development_relaxes_only_the_secure_flag():
    development = session_middleware_kwargs(production=False)
    production = session_middleware_kwargs(production=True)
    assert development["https_only"] is False
    assert development["same_site"] == production["same_site"]
    assert development["max_age"] == production["max_age"]



def test_production_refuses_to_start_without_a_secret(env_mode):
    env_mode("production")
    with pytest.raises(ConfigurationError, match="not set"):
        startup_report("")


def test_production_refuses_to_start_with_a_weak_secret(env_mode):
    env_mode("production")
    with pytest.raises(ConfigurationError, match="placeholder"):
        startup_report("changeme")


def test_the_production_failure_explains_how_to_generate_one(env_mode):
    env_mode("production")
    with pytest.raises(ConfigurationError, match="token_urlsafe"):
        startup_report("short")


def test_production_starts_with_a_strong_secret(env_mode):
    env_mode("production")
    settings, warnings = startup_report(STRONG)
    assert settings["https_only"] is True
    assert warnings == []


def test_development_starts_with_a_weak_secret_but_warns(env_mode):
    env_mode("development")
    settings, warnings = startup_report("short")
    assert settings["https_only"] is False
    assert any("DEVELOPMENT" in warning for warning in warnings)
    assert any("at least" in warning for warning in warnings)


def test_development_always_warns_that_it_is_not_production(env_mode):
    env_mode("development")
    _, warnings = startup_report(STRONG)
    assert any("DEVELOPMENT" in warning for warning in warnings)
