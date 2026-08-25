"""Emitting the USAC performance measurement CSV templates.

NTIA designates the USAC performance measurement CSV format for actual submission
of BEAD results, with two adjustments: because funded network locations have no
HUBB Location ID, the BSL identifier occupies the first column, and providers
submit a separate file for each technology and committed speed tier, so the tier
is not itself a column.

This module produces those files from raw `performance_test` records. It cannot
produce them from `performance_fact` records, and does not pretend to: a fact is an
aggregate over a period, the templates are per-test, and inventing individual test
rows from summary counts would be fabricating measurements.

Everything here is derived from published USAC template specifications and the NTIA
policy notice; see docs/sources.md, sources S1 and S5. Confirm against the current
USAC guide before a live submission, since USAC publishes updates.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime

from bead_data.models import PerformanceTest
from bead_data.schemas import technology_name

#: Speed Type column: download and upload are distinct submissions of the same template.
SPEED_TYPE = {"download": "1", "upload": "2"}

#: Test Status column, mirroring the USAC codes.
TEST_STATUS = {
    "success": "1",
    "not_run_crosstalk": "2",
    "not_run_other": "3",
}

SPEED_COLUMNS = [
    "HUBB Location ID",
    "Subscriber ID",
    "Speed Type",
    "IP Target",
    "Start Test",
    "End Test",
    "Bytes",
    "Test Status",
    "Comment",
]

LATENCY_COLUMNS = [
    "HUBB Location ID",
    "Subscriber ID",
    "IP Target",
    "Start Test",
    "Latency",
    "Packets Sent",
    "Packets Received",
    "Test Status",
    "Comment",
]


class SubmissionError(Exception):
    """Raised when a submission file cannot be produced."""


def usac_timestamp(value: str) -> str:
    """Render an ISO 8601 date-time in the USAC template's format.

    The template specifies ``yyyy-mm-dd hh:mm:ss:SSS±HH:MM`` — note the colon before
    the milliseconds rather than a decimal point, and a space rather than ``T``.
    That is unusual enough that it is worth a dedicated function and a test, because
    an ISO 8601 string will be silently accepted by nothing and rejected by
    everything.
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise SubmissionError(
            f"{value!r} has no UTC offset; the USAC template requires an explicit offset, "
            f"and local testing hours cannot be verified without one"
        )

    millis = parsed.microsecond // 1000
    offset = parsed.strftime("%z")
    offset = f"{offset[:3]}:{offset[3:]}"
    return f"{parsed.strftime('%Y-%m-%d %H:%M:%S')}:{millis:03d}{offset}"


def _row_speed(test: PerformanceTest) -> list[str]:
    return [
        test.location_ref,
        test.subscriber_ref or "",
        SPEED_TYPE[test.test_type],
        test.ip_target or "",
        usac_timestamp(test.started_at),
        usac_timestamp(test.ended_at) if test.ended_at else "",
        str(test.bytes_transferred) if test.bytes_transferred is not None else "",
        TEST_STATUS[test.test_status],
        test.comment or "",
    ]


def _row_latency(test: PerformanceTest) -> list[str]:
    # The template types Latency as an integer round-trip time in milliseconds.
    latency = "" if test.latency_ms_rtt is None else str(int(round(test.latency_ms_rtt)))
    return [
        test.location_ref,
        test.subscriber_ref or "",
        test.ip_target or "",
        usac_timestamp(test.started_at),
        latency,
        str(test.packets_sent) if test.packets_sent is not None else "",
        str(test.packets_received) if test.packets_received is not None else "",
        TEST_STATUS[test.test_status],
        test.comment or "",
    ]


def _write_csv(columns: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return buffer.getvalue()


@dataclass(frozen=True)
class SubmissionFile:
    """One submission file, named for the population it covers."""

    filename: str
    content: str
    technology_code: int
    committed_down_mbps: float
    committed_up_mbps: float
    kind: str
    row_count: int


def _slug(value: float) -> str:
    return f"{value:g}".replace(".", "p")


def build_submission(records: list[dict]) -> list[SubmissionFile]:
    """Build the USAC submission files for a set of raw test observations.

    Splits by technology and committed speed tier, because NTIA requires a separate
    file per combination, and by template, because speed and latency use different
    templates. Download and upload share the speed template and are distinguished
    by the Speed Type column.
    """
    tests = [PerformanceTest.model_validate(r) for r in records]
    if not tests:
        return []

    grouped: dict[tuple[int, float, float, str], list[PerformanceTest]] = {}
    for test in tests:
        kind = "latency" if test.test_type == "latency" else "speed"
        key = (test.technology_code, test.committed_down_mbps, test.committed_up_mbps, kind)
        grouped.setdefault(key, []).append(test)

    files: list[SubmissionFile] = []
    for (code, down, up, kind), subset in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        subset.sort(key=lambda t: (t.location_ref, t.started_at, t.test_type))
        if kind == "speed":
            content = _write_csv(SPEED_COLUMNS, [_row_speed(t) for t in subset])
        else:
            content = _write_csv(LATENCY_COLUMNS, [_row_latency(t) for t in subset])

        name = f"usac_{kind}_tech{code}_{technology_name(code)}" f"_{_slug(down)}x{_slug(up)}.csv"
        files.append(
            SubmissionFile(
                filename=name,
                content=content,
                technology_code=code,
                committed_down_mbps=down,
                committed_up_mbps=up,
                kind=kind,
                row_count=len(subset),
            )
        )

    return files


def submission_manifest(files: list[SubmissionFile]) -> str:
    """A Markdown manifest describing the submission set.

    NTIA requires each submission to be accompanied by documentation of the
    methodology, standards, and parameters used, plus a change log of material
    changes from the previous submission, and to be certified by a corporate officer
    with supervisory and budgetary authority over network operations in the relevant
    service area. This manifest is a starting point for that packet, not a
    substitute for it: the parts that require a human are left as explicit blanks
    rather than filled in with plausible text.
    """
    lines = [
        "# USAC performance measurement submission",
        "",
        f"Generated by bead-data. Files: {len(files)}.",
        "",
        "| File | Template | Tech code | Technology | Committed | Rows |",
        "|---|---|---|---|---|---|",
    ]
    for f in files:
        lines.append(
            f"| `{f.filename}` | {f.kind} | {f.technology_code} | "
            f"{technology_name(f.technology_code)} | "
            f"{f.committed_down_mbps:g}/{f.committed_up_mbps:g} | {f.row_count} |"
        )

    lines += [
        "",
        "One file per technology and committed speed tier, per NTIA. The first column "
        "carries the BSL identifier rather than a HUBB Location ID, because funded "
        "network locations do not have one.",
        "",
        "## Still required before submitting",
        "",
        "These cannot be generated and are deliberately left blank:",
        "",
        "- [ ] **Methodology documentation** — the software, systems, protocols, and "
        "standards used in testing, in enough detail to validate the process.",
        "- [ ] **Change log** — material changes since the previous submission.",
        "- [ ] **Random selection method** — how test subjects were randomly selected "
        "from active subscribers in each tier and technology.",
        "- [ ] **Sample size justification** — the active subscriber count each sample "
        "size was derived from.",
        "- [ ] **Officer certification** — signed by a corporate officer with supervisory "
        "and budgetary authority over network operations in the service area.",
        "- [ ] **Published methodology** — the same methodology posted on your network "
        "management practices page, with aggregate results per sample set.",
        "",
        "## Verify before relying on this",
        "",
        "Column layouts follow published USAC template specifications, which USAC "
        "updates. Confirm against the current guide before a live submission. Sources "
        "are cited in `docs/sources.md`.",
        "",
    ]
    return "\n".join(lines)


def check_testing_hours(records: list[dict]) -> list[str]:
    """Flag observations outside NTIA's permitted testing window.

    NTIA requires testing between 6:00 pm and midnight local time, including
    weekends. This is advisory rather than a schema rule: the record carries a UTC
    offset, not a timezone, so the offset is a good proxy for local time but not a
    guarantee of it. Reporting it as a warning respects that limit instead of
    failing valid data.
    """
    warnings: list[str] = []
    for record in records:
        started = record.get("started_at")
        if not isinstance(started, str):
            continue
        try:
            parsed = datetime.fromisoformat(started.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            warnings.append(
                f"{record.get('test_id', '<unknown>')}: started_at has no UTC offset, "
                f"so local testing hours cannot be checked"
            )
            continue
        if not (18 <= parsed.hour <= 23):
            warnings.append(
                f"{record.get('test_id', '<unknown>')}: started_at local hour "
                f"{parsed.hour:02d} is outside the 18:00-24:00 testing window"
            )
    return warnings


def safe_filename(name: str) -> str:
    """Reject anything that could escape the output directory."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise SubmissionError(f"refusing to write unsafe filename {name!r}")
    return name
