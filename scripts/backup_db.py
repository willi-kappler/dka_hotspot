"""Create, verify, and rotate SQLite backups."""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from db import DB_FILE  # noqa: E402

BACKUP_DIR = PROJECT_ROOT / "backups"
DEFAULT_KEEP = 14
FILENAME_FORMAT = "app-%Y%m%d-%H%M%S.db"


def verify(path: Path) -> bool:
    """Integrity-check a database file. True if SQLite reports it sound."""
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                print(f"  integrity_check: {result}")
                return False
            tables = {
                row[0] for row in
                conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            missing = {"users", "cases", "onsets", "audit_log"} - tables
            if missing:
                print(f"  missing tables: {', '.join(sorted(missing))}")
                return False
    except sqlite3.Error as error:
        print(f"  cannot open: {error}")
        return False
    return True


def row_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("cases", "onsets", "users", "audit_log")
        }


def take_backup(source: Path, directory: Path) -> Path:
    """Write a consistent snapshot and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / datetime.now(timezone.utc).strftime(FILENAME_FORMAT)

    source_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()
    return target


def rotate(directory: Path, keep: int) -> list[Path]:
    """Delete all but the ``keep`` most recent backups. Returns what was removed."""
    backups = sorted(directory.glob("app-*.db"))
    removed = []
    for path in backups[:-keep] if keep > 0 else []:
        path.unlink()
        removed.append(path)
    return removed


def list_backups(directory: Path) -> None:
    backups = sorted(directory.glob("app-*.db"), reverse=True)
    if not backups:
        print(f"No backups in {directory}")
        return
    print(f"{len(backups)} backup(s) in {directory}:")
    for path in backups:
        size = path.stat().st_size / 1024
        print(f"  {path.name}  {size:8.0f} KiB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DB_FILE)
    parser.add_argument("--directory", type=Path, default=BACKUP_DIR)
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                        help=f"how many backups to retain (default {DEFAULT_KEEP})")
    parser.add_argument("--list", action="store_true", help="list backups and exit")
    parser.add_argument("--verify", type=Path, metavar="FILE",
                        help="integrity-check an existing backup and exit")
    arguments = parser.parse_args()

    if arguments.list:
        list_backups(arguments.directory)
        return

    if arguments.verify:
        print(f"Verifying {arguments.verify}")
        if not verify(arguments.verify):
            raise SystemExit("FAILED — this backup is not restorable.")
        print(f"  ok — {row_counts(arguments.verify)}")
        return

    if not arguments.source.exists():
        raise SystemExit(f"No database at {arguments.source}")

    target = take_backup(arguments.source, arguments.directory)
    print(f"Wrote {target}")

    if not verify(target):
        target.unlink(missing_ok=True)
        raise SystemExit("Backup failed verification and was discarded.")
    print(f"  verified — {row_counts(target)}")

    for removed in rotate(arguments.directory, arguments.keep):
        print(f"  rotated out {removed.name}")


if __name__ == "__main__":
    main()
