"""Import pseudonymised case records from a CSV file."""

import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from storage import audit_db  # noqa: E402
from storage.cases_db import import_csv_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--replace", action="store_true",
                        help="clear existing cases before importing")
    arguments = parser.parse_args()
    count = import_csv_file(arguments.csv_file, replace=arguments.replace)
    audit_db.record(
        audit_db.CASES_REPLACED if arguments.replace else audit_db.CASES_IMPORTED,
        actor=getpass.getuser(),
        target=arguments.csv_file.name,
        detail=f"rows={count}",
    )
    print(f"Imported {count} cases from {arguments.csv_file}")


if __name__ == "__main__":
    main()
