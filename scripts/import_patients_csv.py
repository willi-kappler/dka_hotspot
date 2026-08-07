import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from storage.patients_db import import_csv_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Import patient CSV rows into SQLite.")
    parser.add_argument(
        "csv_file",
        nargs="?",
        default=PROJECT_ROOT / "src" / "data" / "dka_sample_data_50km.csv",
        type=Path,
        help="CSV file to import. Defaults to the current fake 50km sample data.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Clear existing patient rows before importing.",
    )
    args = parser.parse_args()

    imported_count = import_csv_file(args.csv_file, replace=args.replace)
    print(f"Imported {imported_count} patient rows from {args.csv_file}")


if __name__ == "__main__":
    main()
