
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def source_files():
    return list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").glob("*.py"))


def test_every_environment_variable_is_documented():
    used = set()
    for path in source_files():
        used |= set(re.findall(r'get_env\(\s*["\']([A-Z_]+)["\']', path.read_text()))
    documented = set(re.findall(
        r"^([A-Z_]+)=", (ROOT / ".env.example").read_text(), re.MULTILINE
    ))
    assert used <= documented, f"undocumented: {sorted(used - documented)}"


def test_env_example_carries_no_actual_values():
    for line in (ROOT / ".env.example").read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            assert value.strip() in ("", "development"), (
                f"{key} appears to carry a real value in .env.example"
            )


def test_the_real_env_file_is_ignored():
    ignored = (ROOT / ".gitignore").read_text()
    assert re.search(r"^\.env$", ignored, re.MULTILINE), ".env must be gitignored"


def test_the_database_is_ignored():
    ignored = (ROOT / ".gitignore").read_text()
    assert "app.db" in ignored


def test_src_data_is_deny_by_default():
    ignored = (ROOT / ".gitignore").read_text()
    assert re.search(r"^src/data/\*$", ignored, re.MULTILINE), (
        "src/data must be excluded by default, with explicit re-inclusions"
    )


@pytest.mark.parametrize("name", [
    "GISD_PLZ5_Baden-Wuerttemberg.tsv",
    "landkreise_baden_wuerttemberg.geojson",
    "plz5_reference_pilot_region.csv",
    "plz5_coordinates.csv",
])
def test_the_data_files_the_application_reads_are_present(name):
    assert (ROOT / "src" / "data" / name).exists()


def test_no_source_file_contains_something_shaped_like_a_committed_secret():
    patterns = [
        re.compile(r'(?i)(api[_-]?key|secret|password|token)\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']'),
    ]
    offenders = []
    for path in source_files():
        for pattern in patterns:
            for match in pattern.finditer(path.read_text()):
                offenders.append(f"{path.relative_to(ROOT)}: {match.group()[:60]}")
    assert not offenders, offenders


def test_backups_are_never_committed():
    ignored = (ROOT / ".gitignore").read_text()
    assert re.search(r"^backups/$", ignored, re.MULTILINE)
