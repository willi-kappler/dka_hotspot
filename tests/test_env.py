
import env
from env import get_env


def test_the_environment_wins_over_the_env_file(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("SECRET=from-file\n", encoding="utf-8")
    monkeypatch.setattr(env, "ENV_FILE", path)
    monkeypatch.setenv("SECRET", "from-environment")
    assert get_env("SECRET") == "from-environment"


def test_it_falls_back_to_the_env_file(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("SECRET=from-file\n", encoding="utf-8")
    monkeypatch.setattr(env, "ENV_FILE", path)
    monkeypatch.delenv("SECRET", raising=False)
    assert get_env("SECRET") == "from-file"


def test_quotes_and_whitespace_are_stripped(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text('A="double"\nB=\'single\'\nC=  spaced  \n', encoding="utf-8")
    monkeypatch.setattr(env, "ENV_FILE", path)
    for key in "ABC":
        monkeypatch.delenv(key, raising=False)
    assert get_env("A") == "double"
    assert get_env("B") == "single"
    assert get_env("C") == "spaced"


def test_a_value_containing_an_equals_sign_survives(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("SECRET=abc=def==\n", encoding="utf-8")
    monkeypatch.setattr(env, "ENV_FILE", path)
    monkeypatch.delenv("SECRET", raising=False)
    assert get_env("SECRET") == "abc=def=="


def test_a_missing_key_or_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(env, "ENV_FILE", tmp_path / "nonexistent")
    monkeypatch.delenv("ABSENT", raising=False)
    assert get_env("ABSENT") == ""


def test_comments_and_blank_lines_are_skipped(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("\n# a comment\nSECRET=value\n", encoding="utf-8")
    monkeypatch.setattr(env, "ENV_FILE", path)
    monkeypatch.delenv("SECRET", raising=False)
    assert get_env("SECRET") == "value"
