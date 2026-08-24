"""The ``bead-data`` command line interface.

Exit codes are stable and meant to be used in CI:

* 0 - every record validated
* 1 - the input was readable but at least one record is invalid
* 2 - usage, I/O, or parse error; nothing could be validated

Keeping "invalid data" and "could not read the data" on separate codes lets a
state broadband office script tell a rejected submission apart from a broken one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from bead_data.schemas import FACT_KINDS
from bead_data.validate import InputError, ValidationReport, validate_file

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2

SCHEMA_CHOICE = click.Choice(sorted(FACT_KINDS), case_sensitive=False)

DATA_SUFFIXES = {".json", ".csv"}


def _expand(paths: tuple[str, ...]) -> list[Path]:
    """Expand the given paths, walking directories for .json and .csv files."""
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found.extend(
                sorted(c for c in p.rglob("*") if c.is_file() and c.suffix.lower() in DATA_SUFFIXES)
            )
        else:
            found.append(p)
    return found


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="bead-data", prog_name="bead-data")
def main() -> None:
    """Open, NTIA-aligned tooling for BEAD broadband compliance evidence.

    Validate the performance, location, and Build America Buy America evidence that
    BEAD reporting depends on.
    """


@main.command("validate")
@click.argument("paths", nargs=-1, required=True, type=click.Path())
@click.option(
    "--schema",
    "kind",
    type=SCHEMA_CHOICE,
    default=None,
    help="Fact family to validate against. Autodetected from the records when omitted.",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Print only the summary line, not each failure.",
)
def validate_cmd(paths: tuple[str, ...], kind: str | None, quiet: bool) -> None:
    """Validate evidence files against the normative schemas.

    PATHS may be files or directories. Directories are searched recursively for
    .json and .csv files.
    """
    targets = _expand(paths)
    if not targets:
        click.echo("no .json or .csv files found in the given paths", err=True)
        sys.exit(EXIT_USAGE)

    reports: list[ValidationReport] = []
    had_input_error = False

    for target in targets:
        try:
            report = validate_file(target, kind)
        except InputError as exc:
            click.echo(f"error: {exc}", err=True)
            had_input_error = True
            continue
        except KeyError as exc:
            click.echo(f"error: {exc}", err=True)
            had_input_error = True
            continue

        reports.append(report)

        if len(targets) > 1:
            click.echo(f"{target} [{report.kind}]")
        if not quiet:
            for err in report.errors:
                click.echo(err.format())

    if had_input_error and not reports:
        sys.exit(EXIT_USAGE)

    total_valid = sum(r.valid_count for r in reports)
    total_invalid = sum(r.invalid_count for r in reports)
    click.echo(f"{total_valid} valid, {total_invalid} invalid")

    if had_input_error:
        sys.exit(EXIT_USAGE)
    sys.exit(EXIT_INVALID if total_invalid else EXIT_OK)


if __name__ == "__main__":
    main()
