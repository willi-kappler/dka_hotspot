"""Import PLZ-5 cases and optionally derive aggregate onsets."""

import argparse
import getpass
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from db import get_connection, init_db  # noqa: E402
from services.epidemiology import (  # noqa: E402
    frame_check,
    is_dka,
    is_gradeable,
    split_manifestations,
)
from storage import audit_db  # noqa: E402
from storage.cases_db import (  # noqa: E402
    classification_disagreements,
    import_csv_file,
    load_cases,
)
from storage.onsets_db import upsert_onsets  # noqa: E402


def derive_onsets(cases: list[dict]) -> list[dict]:
    eligibility = split_manifestations(cases)
    if eligibility["unknown_new_onset"]:
        raise ValueError(
            f"{len(eligibility['unknown_new_onset'])} cases have unknown new_onset status"
        )
    grouped: dict[tuple[str, int, str], list[int]] = defaultdict(lambda: [0, 0])
    skipped = 0
    ungradeable = 0
    for case in eligibility["eligible"]:
        kreis = case.get("kreis_ags")
        if not kreis:
            skipped += 1
            continue
        if not is_gradeable(case):
            ungradeable += 1
            continue
        key = (case["clinic"], case["year_of_onset"], kreis)
        grouped[key][0] += 1
        grouped[key][1] += 1 if is_dka(case) else 0
    if skipped:
        print(f"  {skipped} cases have no Landkreis and are not counted.")
    if ungradeable:
        print(f"  {ungradeable} cases have insufficient pH/bicarbonate data and "
              "are excluded from both the numerator and the denominator.")
    return [
        {
            "clinic": clinic, "year": year, "kreis_ags": kreis,
            "manifestations": manifestations, "dka_cases": dka,
        }
        for (clinic, year, kreis), (manifestations, dka) in sorted(grouped.items())
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--replace", action="store_true",
                        help="clear existing cases before importing")
    parser.add_argument("--derive-onsets", action="store_true",
                        help="count the denominator from the case file itself")
    parser.add_argument(
        "--confirm-complete-cohort",
        action="store_true",
        help="confirm that the file contains every manifestation; required with --derive-onsets",
    )
    arguments = parser.parse_args()

    if arguments.derive_onsets and not arguments.confirm_complete_cohort:
        raise SystemExit(
            "--derive-onsets requires --confirm-complete-cohort. Outcome prevalence "
            "cannot establish that the source contains every manifestation."
        )

    init_db()
    count = import_csv_file(arguments.csv_file, replace=arguments.replace)
    audit_db.record(
        audit_db.CASES_REPLACED if arguments.replace else audit_db.CASES_IMPORTED,
        actor=getpass.getuser(),
        target=arguments.csv_file.name,
        detail=f"rows={count}",
    )
    print(f"Imported {count} cases from {arguments.csv_file}")

    cases = load_cases()
    eligibility = split_manifestations(cases)
    missing_new_onset = len(eligibility["unknown_new_onset"])
    if missing_new_onset:
        print(
            f"{missing_new_onset} cases have no new_onset flag. It is left null "
            "rather than assumed — ask the clinics which records are first "
            "manifestations before reporting the endpoint."
        )

    disagreements = classification_disagreements()
    if disagreements:
        print(
            f"{len(disagreements)} cases where the reported DKA grade differs "
            "from the ISPAD recomputation from pH and bicarbonate:"
        )
        for row in disagreements[:10]:
            print(f"  case {row['id']} ({row['pseudonym']}): reported "
                  f"{row['reported']}, derived {row['derived']} "
                  f"(pH {row['ph']}, bicarbonate {row['bicarbonate']})")
        if len(disagreements) > 10:
            print(f"  ... and {len(disagreements) - 10} more")
        print("  Both are stored. The analysis uses the derived grade.")

    if not arguments.derive_onsets:
        print("\nNo denominator written. The overview map and the area-level "
              "endpoint stay blocked until onsets are loaded — pass "
              "--derive-onsets, or import the clinics' own aggregate return.")
        return

    if missing_new_onset:
        raise SystemExit(
            "Cannot derive manifestations while any case has unknown new_onset status."
        )

    eligible = eligibility["eligible"]
    gradeable = [case for case in eligible if is_gradeable(case)]
    check = frame_check(eligible)
    share = check["share"]
    if check["suspicious"]:
        print(
            f"WARNING: only {share:.1%} of gradeable first manifestations are "
            "non-DKA. This may be a selected extract; the explicit completeness "
            "confirmation, not this prevalence check, authorises derivation."
        )

    with get_connection() as conn:
        conn.execute("DELETE FROM onsets")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'onsets'")
    rows = upsert_onsets(derive_onsets(cases))
    audit_db.record(
        audit_db.ONSETS_IMPORTED,
        actor=getpass.getuser(),
        target=arguments.csv_file.name,
        detail=f"rows={rows} (derived from case file)",
    )
    total = sum(1 for case in gradeable if is_dka(case))
    print(f"\nDerived {rows} denominator rows from the case file "
          f"({total} of {len(gradeable)} gradeable manifestations in DKA, "
          f"{share:.1%} non-DKA).")
    print("These are counted from the case records, not supplied by the "
          "clinics. Replace them with the real aggregate return when it arrives.")


if __name__ == "__main__":
    main()
