
import pytest
from factories import case, onset


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    import db

    monkeypatch.setattr(db, "DB_FILE", tmp_path / "test.db")
    db.init_db()
    return tmp_path / "test.db"


@pytest.fixture
def make_case():
    return case


@pytest.fixture
def make_onset():
    return onset
