"""USAC submission template output.

The template format has details that fail loudly if wrong and are easy to get
wrong: a space rather than ``T``, a colon rather than a decimal point before the
milliseconds, numeric status codes, and one file per technology and speed tier.
Those are pinned here because a malformed submission is rejected by the recipient
rather than by us.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from tests.test_aggregate import latency, make_test, speed

from bead_data.submit import (
    LATENCY_COLUMNS,
    SPEED_COLUMNS,
    SubmissionError,
    build_submission,
    check_testing_hours,
    safe_filename,
    submission_manifest,
    usac_timestamp,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
OFFSET = timezone(timedelta(hours=-7))


def parse(content: str) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(content)))
    return rows[0], rows[1:]


# --------------------------------------------------------------- timestamps


def test_timestamp_uses_the_template_format() -> None:
    """yyyy-mm-dd hh:mm:ss:SSS±HH:MM — space, and a colon before milliseconds."""
    out = usac_timestamp("2026-07-06T19:03:01.123-07:00")
    assert out == "2026-07-06 19:03:01:123-07:00"


def test_timestamp_pads_milliseconds() -> None:
    assert usac_timestamp("2026-07-06T19:03:01.007-07:00").endswith("01:007-07:00")


def test_timestamp_handles_zero_milliseconds() -> None:
    assert usac_timestamp("2026-07-06T19:03:01-07:00") == "2026-07-06 19:03:01:000-07:00"


def test_timestamp_accepts_utc_z() -> None:
    assert usac_timestamp("2026-07-06T19:03:01Z") == "2026-07-06 19:03:01:000+00:00"


def test_timestamp_requires_an_offset() -> None:
    """Without an offset, local testing hours cannot be verified."""
    with pytest.raises(SubmissionError, match="no UTC offset"):
        usac_timestamp("2026-07-06T19:03:01")


# ------------------------------------------------------------ file splitting


def test_speed_and_latency_go_to_separate_templates() -> None:
    files = build_submission([speed(200), latency(20.0)])
    kinds = {f.kind for f in files}
    assert kinds == {"speed", "latency"}


def test_download_and_upload_share_the_speed_template() -> None:
    """They are distinguished by the Speed Type column, not by file."""
    files = build_submission([speed(200, "download"), speed(18, "upload")])
    speed_files = [f for f in files if f.kind == "speed"]
    assert len(speed_files) == 1
    _, rows = parse(speed_files[0].content)
    assert {r[SPEED_COLUMNS.index("Speed Type")] for r in rows} == {"1", "2"}


def test_separate_file_per_technology() -> None:
    files = build_submission([speed(200), speed(200, technology_code=72)])
    assert len({f.technology_code for f in files}) == 2


def test_separate_file_per_committed_tier() -> None:
    files = build_submission(
        [speed(200), speed(200, committed_down_mbps=500.0, committed_up_mbps=100.0)]
    )
    assert len({(f.committed_down_mbps, f.committed_up_mbps) for f in files}) == 2


def test_filenames_identify_the_population() -> None:
    files = build_submission([speed(200, technology_code=72)])
    name = files[0].filename
    assert "tech72" in name
    assert "licensed_by_rule_fixed_wireless" in name
    assert "100x20" in name
    assert name.endswith(".csv")


# ------------------------------------------------------------- column layout


def test_speed_columns_match_the_template() -> None:
    files = build_submission([speed(200)])
    header, _ = parse(files[0].content)
    assert header == SPEED_COLUMNS


def test_latency_columns_match_the_template() -> None:
    files = build_submission([latency(20.0)])
    header, _ = parse(files[0].content)
    assert header == LATENCY_COLUMNS


def test_bsl_identifier_occupies_the_first_column() -> None:
    """BEAD locations have no HUBB Location ID, so the BSL id goes there."""
    files = build_submission([speed(200)])
    header, rows = parse(files[0].content)
    assert header[0] == "HUBB Location ID"
    assert rows[0][0] == "BSL-1002003004"


def test_status_codes_are_numeric() -> None:
    records = [
        speed(200),
        make_test(
            test_status="not_run_crosstalk",
            ended_at=None,
            bytes_transferred=None,
            ip_target=None,
        ),
    ]
    files = build_submission(records)
    _, rows = parse(files[0].content)
    codes = {r[SPEED_COLUMNS.index("Test Status")] for r in rows}
    assert codes == {"1", "2"}


def test_bytes_are_emitted_not_throughput() -> None:
    """The template asks for bytes, so a consumer can reproduce the arithmetic."""
    files = build_submission([speed(200, seconds=16)])
    _, rows = parse(files[0].content)
    assert int(rows[0][SPEED_COLUMNS.index("Bytes")]) == int(200 * 1_000_000 / 8 * 16)


def test_latency_is_an_integer_millisecond_value() -> None:
    files = build_submission([latency(35.7)])
    _, rows = parse(files[0].content)
    assert rows[0][LATENCY_COLUMNS.index("Latency")] == "36"


def test_lost_packets_are_visible_in_the_submission() -> None:
    files = build_submission([latency(40.0, received=0)])
    _, rows = parse(files[0].content)
    assert rows[0][LATENCY_COLUMNS.index("Packets Sent")] == "3"
    assert rows[0][LATENCY_COLUMNS.index("Packets Received")] == "0"


def test_rows_use_crlf() -> None:
    """CSV templates for regulated submission conventionally use CRLF."""
    files = build_submission([speed(200)])
    assert "\r\n" in files[0].content


def test_empty_input_produces_no_files() -> None:
    assert build_submission([]) == []


# ----------------------------------------------------------------- manifest


def test_manifest_lists_every_file_and_the_human_gaps() -> None:
    files = build_submission([speed(200), latency(20.0)])
    text = submission_manifest(files)
    for f in files:
        assert f.filename in text
    for required in (
        "Methodology documentation",
        "Change log",
        "Random selection method",
        "Officer certification",
    ):
        assert required in text, f"manifest omits {required!r}"


def test_manifest_does_not_invent_the_certification() -> None:
    """The parts needing a person must be blanks, not plausible filler."""
    text = submission_manifest(build_submission([speed(200)]))
    assert "- [ ]" in text
    assert "certified by" not in text.lower().replace("certification", "")


# ------------------------------------------------------------ testing hours


def test_testing_hours_warning_flags_daytime_tests() -> None:
    day = make_test(
        started_at=datetime(2026, 7, 6, 11, 0, tzinfo=OFFSET).isoformat(timespec="milliseconds"),
        ended_at=datetime(2026, 7, 6, 11, 0, 16, tzinfo=OFFSET).isoformat(timespec="milliseconds"),
    )
    warnings = check_testing_hours([day])
    assert warnings and "outside the 18:00-24:00 testing window" in warnings[0]


def test_testing_hours_accepts_the_permitted_window() -> None:
    assert check_testing_hours([speed(200)]) == []


def test_example_raw_tests_are_all_within_testing_hours() -> None:
    records = json.loads((EXAMPLES / "synthetic_raw_tests.json").read_text(encoding="utf-8"))
    assert check_testing_hours(records) == []


# -------------------------------------------------------------------- safety


def test_safe_filename_rejects_traversal() -> None:
    for bad in ("../escape.csv", "a/b.csv", "x;rm -rf.csv", ""):
        with pytest.raises(SubmissionError, match="unsafe filename"):
            safe_filename(bad)


def test_safe_filename_accepts_generated_names() -> None:
    for f in build_submission([speed(200), latency(20.0)]):
        assert safe_filename(f.filename) == f.filename


# ------------------------------------------------------------ against examples


def test_examples_produce_four_submission_files() -> None:
    """Two technologies times two templates."""
    records = json.loads((EXAMPLES / "synthetic_raw_tests.json").read_text(encoding="utf-8"))
    files = build_submission(records)
    assert len(files) == 4
    assert {(f.technology_code, f.kind) for f in files} == {
        (71, "speed"),
        (71, "latency"),
        (72, "speed"),
        (72, "latency"),
    }
    for f in files:
        header, rows = parse(f.content)
        assert header in (SPEED_COLUMNS, LATENCY_COLUMNS)
        assert len(rows) == f.row_count
