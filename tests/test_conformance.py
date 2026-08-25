"""Run the reference implementation against the language-agnostic conformance suite.

The suite under `conformance/` is the contract the schemas offer to any
implementation, in any language. If the reference implementation does not pass its
own published vectors, the vectors are worthless to everyone else.

These tests are deliberately strict about *which* fields get blamed, not merely
that validation failed. An implementation that rejects a bad record while pointing
at the wrong field has not really helped whoever has to fix the data.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bead_data.validate import validate_records

REPO = Path(__file__).resolve().parents[1]
CONFORMANCE = REPO / "conformance"
MANIFEST = CONFORMANCE / "manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def load_cases() -> list[dict]:
    manifest = load_manifest()
    cases = []
    for entry in manifest["cases"]:
        payload = json.loads((CONFORMANCE / entry["path"]).read_text(encoding="utf-8"))
        cases.append(payload)
    return cases


ALL_CASES = load_cases()
VALID_CASES = [c for c in ALL_CASES if c["valid"]]
INVALID_CASES = [c for c in ALL_CASES if not c["valid"]]


def ids(cases: list[dict]) -> list[str]:
    return [c["name"] for c in cases]


# --------------------------------------------------------------- suite shape


def test_manifest_matches_the_case_files() -> None:
    manifest = load_manifest()
    listed = {entry["path"] for entry in manifest["cases"]}
    on_disk = {str(p.relative_to(CONFORMANCE)) for p in (CONFORMANCE / "cases").rglob("*.json")}
    assert listed == on_disk, (
        f"manifest and disk disagree. "
        f"only in manifest={sorted(listed - on_disk)}, "
        f"only on disk={sorted(on_disk - listed)}"
    )
    assert manifest["case_count"] == len(on_disk)


def test_suite_is_current() -> None:
    """The suite is generated; a stale copy would misrepresent the contract."""
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "gen_conformance.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_suite_covers_every_schema() -> None:
    covered = {c["schema"] for c in ALL_CASES}
    assert covered == {"performance", "location", "baba"}


def test_suite_has_both_outcomes_for_every_schema() -> None:
    for schema in ("performance", "location", "baba"):
        subset = [c for c in ALL_CASES if c["schema"] == schema]
        assert any(c["valid"] for c in subset), f"{schema}: no valid case"
        assert any(not c["valid"] for c in subset), f"{schema}: no invalid case"


@pytest.mark.parametrize("case", ALL_CASES, ids=ids(ALL_CASES))
def test_every_case_is_self_describing(case: dict) -> None:
    """A case an implementer cannot understand is a case they will ignore."""
    assert case["description"].strip()
    assert case["rationale"].strip()
    assert case["schema"] in ("performance", "location", "baba")
    assert isinstance(case["instance"], dict)
    if not case["valid"]:
        assert case["expect_fields"], f"{case['name']}: invalid case blames no field"


# ------------------------------------------------------- the vectors themselves


@pytest.mark.parametrize("case", VALID_CASES, ids=ids(VALID_CASES))
def test_valid_cases_are_accepted(case: dict) -> None:
    report = validate_records([case["instance"]], case["schema"])
    assert report.ok, (
        f"{case['name']} should validate but did not: " f"{[e.format() for e in report.errors]}"
    )


@pytest.mark.parametrize("case", INVALID_CASES, ids=ids(INVALID_CASES))
def test_invalid_cases_are_rejected(case: dict) -> None:
    report = validate_records([case["instance"]], case["schema"])
    assert not report.ok, f"{case['name']} should have been rejected but validated"


@pytest.mark.parametrize("case", INVALID_CASES, ids=ids(INVALID_CASES))
def test_invalid_cases_blame_the_expected_fields(case: dict) -> None:
    """Rejecting for the wrong reason does not help whoever has to fix the data."""
    report = validate_records([case["instance"]], case["schema"])
    blamed = {e.field_path for e in report.errors}
    expected = set(case["expect_fields"])
    missing = expected - blamed
    assert not missing, (
        f"{case['name']}: expected these fields to be blamed but they were not: "
        f"{sorted(missing)}. Actually blamed: {sorted(blamed)}"
    )


# ------------------------------------------------------------------ coverage


def test_suite_exercises_every_cross_field_rule() -> None:
    """Every documented cross-field rule needs a published vector."""
    names = {c["name"] for c in ALL_CASES}
    required = {
        "crossfield/period_end_before_start",
        "crossfield/download_passing_exceeds_total",
        "crossfield/upload_passing_exceeds_total",
        "crossfield/latency_passing_exceeds_total",
        "crossfield/installed_without_install_date",
        "crossfield/active_without_install_date",
        "crossfield/certification_path_missing_letter_fields",
        "crossfield/waiver_path_missing_tracker_fields",
        "crossfield/both_compliance_paths_present",
        "crossfield/waiver_path_with_certification_ref",
    }
    assert required <= names, f"missing cross-field vectors: {sorted(required - names)}"


def test_suite_pins_the_speedtest_trap() -> None:
    """The most likely wrong answer deserves an explicit vector."""
    case = next(c for c in ALL_CASES if c["name"].endswith("enum_measurement_method_speedtest"))
    assert not case["valid"]
    assert case["instance"]["measurement_method"] == "speedtest"
