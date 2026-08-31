
import sqlite3
import threading

import pytest
from backup_db import rotate, row_counts, take_backup, verify


@pytest.fixture
def populated(temp_db):
    from factories import case, onset

    from storage.cases_db import add_cases
    from storage.onsets_db import upsert_onsets
    from storage.users_db import create_user

    add_cases([case(pseudonym=f"P{i:03d}") for i in range(25)])
    upsert_onsets([onset()])
    create_user("alice", "a-valid-passphrase", "scientist")
    return temp_db


def test_a_backup_is_verifiable_and_carries_the_rows(populated, tmp_path):
    target = take_backup(populated, tmp_path / "backups")
    assert target.exists()
    assert verify(target) is True
    assert row_counts(target)["cases"] == 25
    assert row_counts(target)["users"] == 1


def test_the_backup_is_a_separate_file_that_does_not_track_the_source(populated, tmp_path):
    from factories import case

    from storage.cases_db import add_cases

    target = take_backup(populated, tmp_path / "backups")
    add_cases([case(pseudonym="LATER")])
    assert row_counts(target)["cases"] == 25, "a snapshot must not follow the source"


def test_a_backup_taken_during_concurrent_writes_stays_consistent(populated, tmp_path):
    from factories import case

    from storage.cases_db import add_cases

    stop = threading.Event()
    errors = []

    def writer():
        index = 0
        while not stop.is_set() and index < 200:
            try:
                add_cases([case(pseudonym=f"W{index:04d}")])
            except sqlite3.OperationalError:
                pass          # lock contention is expected and not a failure
            except Exception as error:
                errors.append(error)
            index += 1

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        target = take_backup(populated, tmp_path / "backups")
    finally:
        stop.set()
        thread.join(timeout=30)

    assert not errors, errors
    assert verify(target) is True
    counts = row_counts(target)
    assert counts["cases"] >= 25


def test_verify_rejects_a_file_that_is_not_a_database(tmp_path):
    junk = tmp_path / "not-a-db.db"
    junk.write_bytes(b"this is not a SQLite file" * 100)
    assert verify(junk) is False


def test_verify_rejects_a_database_missing_the_expected_tables(tmp_path):
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).execute("CREATE TABLE unrelated (x INTEGER)")
    assert verify(empty) is False


def test_verify_rejects_a_missing_file(tmp_path):
    assert verify(tmp_path / "nonexistent.db") is False


def test_rotation_keeps_the_most_recent(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    names = [f"app-2026010{n}-000000.db" for n in range(1, 6)]
    for name in names:
        (directory / name).write_bytes(b"x")

    removed = rotate(directory, keep=2)
    remaining = sorted(p.name for p in directory.glob("app-*.db"))
    assert remaining == names[-2:]
    assert len(removed) == 3


def test_rotation_with_fewer_backups_than_the_limit_removes_nothing(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    (directory / "app-20260101-000000.db").write_bytes(b"x")
    assert rotate(directory, keep=14) == []


def test_rotation_of_zero_keeps_everything(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    (directory / "app-20260101-000000.db").write_bytes(b"x")
    assert rotate(directory, keep=0) == []


def test_backup_filenames_sort_chronologically(populated, tmp_path):
    from datetime import datetime, timezone

    from backup_db import FILENAME_FORMAT

    earlier = datetime(2026, 1, 2, tzinfo=timezone.utc).strftime(FILENAME_FORMAT)
    later = datetime(2026, 11, 30, tzinfo=timezone.utc).strftime(FILENAME_FORMAT)
    assert earlier < later
