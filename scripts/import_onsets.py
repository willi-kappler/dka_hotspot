"""Import aggregate manifestation counts from CSV."""

import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from storage import audit_db  # noqa: E402
from storage.onsets_db import import_csv_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    arguments = parser.parse_args()
    count = import_csv_file(arguments.csv_file)
    audit_db.record(
        audit_db.ONSETS_IMPORTED,
        actor=getpass.getuser(),
        target=arguments.csv_file.name,
        detail=f"rows={count}",
    )
    print(f"Imported {count} denominator rows from {arguments.csv_file}")


if __name__ == "__main__":
    main()
