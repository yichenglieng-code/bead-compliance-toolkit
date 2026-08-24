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

from bead_data.convert import FORMATS, ConversionError, render, to_parquet
from bead_data.metrics import metrics_for
from bead_data.report import ReportError, build_report
from bead_data.schemas import FACT_KINDS
from bead_data.validate import (
    InputError,
    ValidationReport,
    load_records,
    validate_file,
    validate_records,
)

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2

SCHEMA_CHOICE = click.Choice(sorted(FACT_KINDS), case_sensitive=False)
FORMAT_CHOICE = click.Choice(FORMATS, case_sensitive=False)

DATA_SUFFIXES = {".json", ".csv", ".parquet"}


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

    Validate, convert, and summarize the performance, location, and Build America
    Buy America evidence that BEAD reporting depends on.
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
    .json, .csv, and .parquet files.
    """
    targets = _expand(paths)
    if not targets:
        click.echo("no .json, .csv, or .parquet files found in the given paths", err=True)
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


@main.command("convert")
@click.argument("path", type=click.Path())
@click.option(
    "--to",
    "fmt",
    type=FORMAT_CHOICE,
    required=True,
    help="Output format.",
)
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(),
    default=None,
    help="Output file. Writes to stdout when omitted (json and csv only).",
)
@click.option(
    "--schema",
    "kind",
    type=SCHEMA_CHOICE,
    default=None,
    help="Fact family. Autodetected from the records when omitted.",
)
def convert_cmd(path: str, fmt: str, output: str | None, kind: str | None) -> None:
    """Convert evidence between JSON, CSV, and Parquet.

    Validates before writing. If any record is invalid nothing is written, because
    emitting evidence that would be rejected downstream just moves the rejection
    to someone else's desk.
    """
    fmt = fmt.lower()
    source = Path(path)

    try:
        records, resolved = load_records(source, kind)
    except (InputError, KeyError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(EXIT_USAGE)

    report = validate_records(records, resolved, source)
    if not report.ok:
        for err in report.errors:
            click.echo(err.format(), err=True)
        click.echo(
            f"error: {report.invalid_count} invalid record(s); nothing written",
            err=True,
        )
        sys.exit(EXIT_INVALID)

    if fmt == "parquet":
        if not output:
            click.echo(
                "error: parquet is binary; pass -o/--output to write it to a file",
                err=True,
            )
            sys.exit(EXIT_USAGE)
        try:
            to_parquet(records, resolved, Path(output))
        except OSError as exc:
            click.echo(f"error: could not write {output}: {exc}", err=True)
            sys.exit(EXIT_USAGE)
        click.echo(f"wrote {len(records)} record(s) to {output}", err=True)
        sys.exit(EXIT_OK)

    try:
        text = render(records, resolved, fmt)
    except ConversionError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(EXIT_USAGE)

    if output:
        try:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        except OSError as exc:
            click.echo(f"error: could not write {output}: {exc}", err=True)
            sys.exit(EXIT_USAGE)
        click.echo(f"wrote {len(records)} record(s) to {output}", err=True)
    else:
        click.echo(text, nl=False)

    sys.exit(EXIT_OK)


@main.command("metrics")
@click.argument("path", type=click.Path())
@click.option(
    "--period",
    default=None,
    help="Reporting period as YYYY-MM or YYYY-QN. All periods when omitted.",
)
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(),
    default=None,
    help="Write the exposition to a file instead of stdout.",
)
def metrics_cmd(path: str, period: str | None, output: str | None) -> None:
    """Emit compliance metrics in Prometheus exposition format.

    Same numbers as `report`, shaped for a dashboard or an alert rule. Pair with
    the Grafana dashboard in dashboards/, which consumes these metric names.

    Alerting on bead_sample_set_compliant == 0 surfaces a failing sample set while
    there is still time to fix it.
    """
    try:
        text = metrics_for(Path(path), period)
    except (InputError, ReportError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(EXIT_USAGE)

    if output:
        try:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        except OSError as exc:
            click.echo(f"error: could not write {output}: {exc}", err=True)
            sys.exit(EXIT_USAGE)
        click.echo(f"wrote metrics to {output}", err=True)
    else:
        click.echo(text, nl=False)

    sys.exit(EXIT_OK)


@main.command("report")
@click.argument("path", type=click.Path())
@click.option(
    "--period",
    default=None,
    help="Reporting period as YYYY-MM or YYYY-QN. All periods when omitted.",
)
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(),
    default=None,
    help="Write the Markdown summary to a file instead of stdout.",
)
def report_cmd(path: str, period: str | None, output: str | None) -> None:
    """Summarize an evidence directory against the four NTIA thresholds.

    Produces a Markdown summary: an indicative compliance verdict per sample set,
    location counts by build status, and BABA coverage by compliance path.
    """
    try:
        text = build_report(Path(path), period)
    except (InputError, ReportError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(EXIT_USAGE)

    if output:
        try:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        except OSError as exc:
            click.echo(f"error: could not write {output}: {exc}", err=True)
            sys.exit(EXIT_USAGE)
        click.echo(f"wrote report to {output}", err=True)
    else:
        click.echo(text, nl=False)

    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
