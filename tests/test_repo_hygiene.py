"""Repository invariants that are cheap to check and expensive to get wrong.

Each of these exists because of a specific failure mode, not for tidiness.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bead_data.validate import InputError, load_records, validate_records

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"
EXAMPLES = REPO / "examples"

DATA_SUFFIXES = {".json", ".csv", ".parquet"}


# --------------------------------------------------------------- import hygiene


def test_no_test_module_imports_another_test_module() -> None:
    """This exact mistake passed locally and failed in CI.

    ``python -m pytest`` puts the working directory on ``sys.path``; the ``pytest``
    console script does not. So ``from tests.test_aggregate import ...`` resolves
    under one invocation and raises ModuleNotFoundError under the other. Shared
    builders belong in ``helpers.py``, which pytest makes importable either way.
    """
    offenders = []
    pattern = re.compile(r"^\s*(?:from|import)\s+(?:tests\.)?(test_\w+)", re.MULTILINE)

    for path in sorted(TESTS.glob("test_*.py")):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name} imports {match.group(1)}")

    assert not offenders, (
        "test modules must not import each other; move shared code to helpers.py. "
        f"Found: {offenders}"
    )


def test_helpers_is_importable_without_package_context() -> None:
    """Guards the fix itself, not just the symptom."""
    import helpers

    assert callable(helpers.make_test)
    assert callable(helpers.speed)
    assert callable(helpers.latency)


# ------------------------------------------------------------- example data


def example_data_files() -> list[Path]:
    return sorted(
        p for p in EXAMPLES.rglob("*") if p.is_file() and p.suffix.lower() in DATA_SUFFIXES
    )


def test_every_example_file_is_accounted_for() -> None:
    """Either an example validates, or its filename says it does not."""
    unexpected = []

    for path in example_data_files():
        deliberately_invalid = ".invalid." in path.name
        try:
            records, kind = load_records(path)
        except InputError as exc:
            unexpected.append(f"{path.name}: unreadable: {exc}")
            continue

        report = validate_records(records, kind, path)
        if deliberately_invalid and report.ok:
            unexpected.append(f"{path.name}: named invalid but every record validates")
        elif not deliberately_invalid and not report.ok:
            unexpected.append(
                f"{path.name}: {report.invalid_count} invalid record(s): "
                f"{[e.format() for e in report.errors][:2]}"
            )

    assert not unexpected, unexpected


def test_documented_invalid_example_breaks_in_distinct_ways() -> None:
    """The invalid example teaches three failure classes; it should keep doing so."""
    path = EXAMPLES / "synthetic_factory_export.invalid.csv"
    records, kind = load_records(path)
    report = validate_records(records, kind, path)

    assert report.invalid_count >= 3, "expected at least three broken rows"
    assert len({e.field_path for e in report.errors}) >= 3, (
        "the broken rows should fail on different fields, not the same one three times"
    )


# ------------------------------------------------- synthetic data guarantees


def test_examples_contain_no_real_looking_identifiers() -> None:
    """No real subscriber or location data, ever. This checks rather than trusts.

    Location ids must use the obviously synthetic ``BSL-`` prefix, and nothing may
    look like an email address or a routable public IP.
    """
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    problems: list[str] = []

    for path in example_data_files():
        text = path.read_text(encoding="utf-8", errors="ignore")

        for found in set(email.findall(text)):
            if not found.endswith((".example", ".invalid", ".test", ".localhost")):
                problems.append(f"{path.name}: email-like value {found!r}")

        for found in set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)):
            problems.append(f"{path.name}: IP-like value {found!r}")

    assert not problems, problems


def test_all_example_location_ids_are_synthetic() -> None:
    problems: list[str] = []
    for path in example_data_files():
        if path.suffix.lower() != ".json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else [payload]
        for record in records:
            for key in ("location_ref", "location_id"):
                value = record.get(key)
                if value is not None and not str(value).startswith("BSL-1002"):
                    problems.append(f"{path.name}: {key}={value!r} is not obviously synthetic")
    assert not problems, problems[:5]


def test_example_organisations_are_fictional() -> None:
    """Provenance must name an Example organisation, not a real one."""
    problems: list[str] = []
    for path in example_data_files():
        if path.suffix.lower() != ".json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else [payload]
        for record in records:
            org = (record.get("provenance") or {}).get("source_org", "")
            if org and not org.startswith("Example "):
                problems.append(f"{path.name}: source_org={org!r}")
    assert not problems, sorted(set(problems))[:5]


# ------------------------------------------------------------ project files


@pytest.mark.parametrize(
    "filename",
    ["README.md", "LICENSE", "NOTICE", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md"],
)
def test_expected_project_files_exist(filename: str) -> None:
    path = REPO / filename
    assert path.is_file(), f"{filename} is missing"
    assert path.stat().st_size > 0, f"{filename} is empty"


def test_changelog_mentions_the_current_version() -> None:
    from bead_data import __version__

    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert __version__ in changelog, (
        f"CHANGELOG.md does not mention version {__version__}"
    )
