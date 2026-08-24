"""CLI contract: exit codes and failure output format.

The exit codes are the part other people's scripts depend on, so they are pinned
here. 0 means every record validated, 1 means the input was readable but some
record is invalid, 2 means nothing could be validated at all.
"""

from __future__ import annotations

import json
import re

import pytest
from click.testing import CliRunner

from bead_data.cli import EXIT_INVALID, EXIT_OK, EXIT_USAGE, main

FAILURE_LINE = re.compile(r"^record \d+: [^:]+: .+$")


@pytest.fixture
def run():
    runner = CliRunner()

    def _run(*args: str):
        return runner.invoke(main, list(args))

    return _run


# ------------------------------------------------------------------ exit code 0


@pytest.mark.parametrize(
    "filename",
    ["performance_valid.json", "performance_valid.csv", "location_valid.json", "baba_valid.json"],
)
def test_exit_zero_on_valid_file(run, data_dir, filename) -> None:
    result = run("validate", str(data_dir / filename))
    assert result.exit_code == EXIT_OK, result.output
    assert "2 valid, 0 invalid" in result.output


def test_exit_zero_with_explicit_schema(run, data_dir) -> None:
    result = run("validate", str(data_dir / "baba_valid.json"), "--schema", "baba")
    assert result.exit_code == EXIT_OK, result.output


def test_multiple_file_arguments_are_totalled(run, data_dir) -> None:
    result = run(
        "validate",
        str(data_dir / "performance_valid.json"),
        str(data_dir / "baba_valid.json"),
    )
    assert result.exit_code == EXIT_OK, result.output
    assert "4 valid, 0 invalid" in result.output


def test_directory_argument_is_walked(run, tmp_path, data_dir) -> None:
    """A state office receives an evidence bundle as a directory, not as one file."""
    bundle = tmp_path / "bundle"
    (bundle / "nested").mkdir(parents=True)
    for name in ("performance_valid.json", "baba_valid.json"):
        (bundle / name).write_bytes((data_dir / name).read_bytes())
    (bundle / "nested" / "location_valid.json").write_bytes(
        (data_dir / "location_valid.json").read_bytes()
    )
    (bundle / "README.txt").write_text("ignore me", encoding="utf-8")

    result = run("validate", str(bundle))
    assert result.exit_code == EXIT_OK, result.output
    assert "6 valid, 0 invalid" in result.output


# ------------------------------------------------------------------ exit code 1


def test_exit_one_on_invalid_record(run, tmp_path, performance_record) -> None:
    target = tmp_path / "bad.json"
    target.write_text(json.dumps([{**performance_record, "uptime_pct": 101}]), encoding="utf-8")

    result = run("validate", str(target))
    assert result.exit_code == EXIT_INVALID
    assert "0 valid, 1 invalid" in result.output


def test_failure_output_format(run, tmp_path, performance_record) -> None:
    """Each failure is one line: record <n>: <field>: <message>."""
    records = [
        performance_record,
        {**performance_record, "measurement_method": "speedtest"},
    ]
    target = tmp_path / "mixed.json"
    target.write_text(json.dumps(records), encoding="utf-8")

    result = run("validate", str(target))
    assert result.exit_code == EXIT_INVALID

    lines = [ln for ln in result.output.splitlines() if ln.startswith("record ")]
    assert lines, result.output
    for line in lines:
        assert FAILURE_LINE.match(line), f"unexpected failure line: {line!r}"
    assert "record 2: measurement_method:" in result.output
    assert "1 valid, 1 invalid" in result.output


def test_quiet_keeps_summary_only(run, tmp_path, performance_record) -> None:
    target = tmp_path / "bad.json"
    target.write_text(json.dumps([{**performance_record, "uptime_pct": 101}]), encoding="utf-8")

    result = run("validate", str(target), "--quiet")
    assert result.exit_code == EXIT_INVALID
    assert "record 1:" not in result.output
    assert "0 valid, 1 invalid" in result.output


def test_mismatched_explicit_schema_fails_loudly(run, data_dir) -> None:
    """Pinning the wrong schema must fail, never pass by coincidence."""
    result = run("validate", str(data_dir / "performance_valid.json"), "--schema", "location")
    assert result.exit_code == EXIT_INVALID
    assert "0 valid, 2 invalid" in result.output


# ------------------------------------------------------------------ exit code 2


def test_exit_two_on_malformed_input(run, data_dir) -> None:
    result = run("validate", str(data_dir / "malformed.json"))
    assert result.exit_code == EXIT_USAGE
    assert "invalid JSON" in result.output


def test_exit_two_on_missing_file(run, tmp_path) -> None:
    result = run("validate", str(tmp_path / "absent.json"))
    assert result.exit_code == EXIT_USAGE
    assert "not a file" in result.output


def test_exit_two_on_unsupported_suffix(run, tmp_path) -> None:
    target = tmp_path / "evidence.xlsx"
    target.write_bytes(b"nope")
    result = run("validate", str(target))
    assert result.exit_code == EXIT_USAGE
    assert "unsupported file type" in result.output


def test_exit_two_on_empty_directory(run, tmp_path) -> None:
    result = run("validate", str(tmp_path))
    assert result.exit_code == EXIT_USAGE
    assert "no .json or .csv files found" in result.output


def test_exit_two_on_undetectable_schema(run, tmp_path) -> None:
    target = tmp_path / "mystery.json"
    target.write_text(json.dumps([{"colour": "blue"}]), encoding="utf-8")
    result = run("validate", str(target))
    assert result.exit_code == EXIT_USAGE
    assert "cannot detect schema" in result.output


def test_partial_failure_still_exits_two(run, tmp_path, data_dir, performance_record) -> None:
    """One unreadable file among readable ones must not be reported as success."""
    good = tmp_path / "good.json"
    good.write_text(json.dumps([performance_record]), encoding="utf-8")

    result = run("validate", str(good), str(data_dir / "malformed.json"))
    assert result.exit_code == EXIT_USAGE
    assert "invalid JSON" in result.output


# ----------------------------------------------------------------------- misc


def test_help_and_version(run) -> None:
    assert run("--help").exit_code == EXIT_OK
    version = run("--version")
    assert version.exit_code == EXIT_OK
    assert "0.1.0" in version.output


def test_bad_schema_choice_is_rejected(run, data_dir) -> None:
    result = run("validate", str(data_dir / "performance_valid.json"), "--schema", "nonsense")
    assert result.exit_code != EXIT_OK
