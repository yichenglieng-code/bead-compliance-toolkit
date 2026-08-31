"""Compliance arithmetic and report aggregation.

The threshold math is the part of this toolkit someone might actually rely on, so
it is tested against hand-computed cases rather than only against the example set.
"""

from __future__ import annotations

import pytest

from bead_data.report import (
    BSL_FLOOR_UP_MBPS,
    FAIL,
    LATENCY_FRACTION,
    NO_DATA,
    OUTAGE_HOURS_CEILING,
    PASS,
    SPEED_MEASUREMENT_FRACTION,
    SPEED_OF_REQUIRED_FRACTION,
    Corpus,
    ReportError,
    SampleSet,
    build_report,
    gather,
    group_sample_sets,
    in_period,
    parse_period,
    render_report,
    summarize,
)
from bead_data.validate import InputError

EXAMPLES = ["synthetic_field_telemetry.json", "synthetic_locations.json"]


@pytest.fixture
def examples_dir():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "examples"


def make_set(**overrides) -> SampleSet:
    """A sample set with one fact, tunable per test."""
    fact = {
        "location_ref": "BSL-1002003004",
        "is_cai": False,
        "download_tests_total": 100,
        "download_tests_meeting_threshold": 100,
        "upload_tests_total": 100,
        "upload_tests_meeting_threshold": 100,
        "latency_tests_total": 100,
        "latency_tests_at_or_below_100ms": 100,
        "uptime_pct": 99.9,
        "outage_hours_365d": 10.0,
        "sample_population_active_subscribers": 1,
    }
    fact.update(overrides)
    return SampleSet("NV", 71, 100.0, 20.0, [fact])


# ------------------------------------------------------------ period parsing


@pytest.mark.parametrize(
    ("period", "label", "start_month", "end_month"),
    [
        ("2026-Q1", "2026 Q1", 1, 4),
        ("2026-Q3", "2026 Q3", 7, 10),
        ("2026-Q4", "2026 Q4", 10, 1),
        ("2026-07", "2026-07", 7, 8),
        ("2026-12", "2026-12", 12, 1),
    ],
)
def test_parse_period(period, label, start_month, end_month) -> None:
    start, end, parsed_label = parse_period(period)
    assert parsed_label == label
    assert start.month == start_month
    assert end.month == end_month


@pytest.mark.parametrize("period", ["2026", "2026-Q5", "2026-13", "nonsense", "2026-QQ"])
def test_parse_period_rejects_bad_input(period) -> None:
    with pytest.raises(ReportError):
        parse_period(period)


def test_in_period_uses_overlap_not_containment() -> None:
    """A measurement week straddling a month boundary is evidence about both."""
    window = parse_period("2026-07")[:2]
    straddling = {"period_start": "2026-06-29T00:00:00Z", "period_end": "2026-07-05T00:00:00Z"}
    outside = {"period_start": "2026-09-01T00:00:00Z", "period_end": "2026-09-07T00:00:00Z"}

    assert in_period(straddling, window)
    assert not in_period(outside, window)
    assert in_period(outside, None)


# --------------------------------------------------------- threshold checks


def test_all_thresholds_pass_on_clean_data() -> None:
    sample_set = make_set()
    assert sample_set.verdict() == PASS
    assert all(c.verdict == PASS for c in sample_set.checks())


def test_sample_size_is_part_of_the_overall_verdict() -> None:
    sample_set = make_set(sample_population_active_subscribers=6)
    check = sample_set.sampling_check()

    assert check.verdict == FAIL
    assert "1 sampled location" in check.observed
    assert "at least 5" in check.required
    assert sample_set.verdict() == FAIL


def test_missing_sample_population_is_no_data_not_pass() -> None:
    sample_set = make_set()
    del sample_set.facts[0]["sample_population_active_subscribers"]

    assert sample_set.sampling_check().verdict == NO_DATA
    assert sample_set.verdict() == NO_DATA


def test_incomplete_sample_population_is_no_data() -> None:
    first = make_set().facts[0]
    second = {**first, "location_ref": "BSL-1002003005"}
    del second["sample_population_active_subscribers"]
    sample_set = SampleSet("NV", 71, 100.0, 20.0, [first, second])

    assert sample_set.sampling_check().verdict == NO_DATA


def test_conflicting_sample_population_fails() -> None:
    first = make_set(sample_population_active_subscribers=10).facts[0]
    second = {
        **first,
        "location_ref": "BSL-1002003005",
        "sample_population_active_subscribers": 11,
    }
    sample_set = SampleSet("NV", 71, 100.0, 20.0, [first, second])

    assert sample_set.sampling_check().verdict == FAIL
    assert "conflicting" in sample_set.sampling_check().observed


def test_sample_cannot_exceed_population() -> None:
    first = make_set(sample_population_active_subscribers=1).facts[0]
    second = {**first, "location_ref": "BSL-1002003005"}
    sample_set = SampleSet("NV", 71, 100.0, 20.0, [first, second])

    assert sample_set.sampling_check().verdict == FAIL
    assert "cannot exceed" in sample_set.sampling_check().required


def test_download_threshold_boundary_is_inclusive() -> None:
    """Exactly 80 percent passes; NTIA says at or above."""
    at_bar = make_set(download_tests_meeting_threshold=80)
    assert at_bar.download_check().verdict == PASS

    below = make_set(download_tests_meeting_threshold=79)
    assert below.download_check().verdict == FAIL


def test_latency_threshold_boundary_is_inclusive() -> None:
    at_bar = make_set(latency_tests_at_or_below_100ms=95)
    assert at_bar.latency_check().verdict == PASS

    below = make_set(latency_tests_at_or_below_100ms=94)
    assert below.latency_check().verdict == FAIL


def test_upload_is_judged_separately_from_download() -> None:
    """NTIA counts the two directions separately; download passing cannot rescue upload."""
    sample_set = make_set(upload_tests_meeting_threshold=10)
    assert sample_set.download_check().verdict == PASS
    assert sample_set.upload_check().verdict == FAIL
    assert sample_set.verdict() == FAIL


def test_availability_boundary_at_48_hours() -> None:
    """Under 48 hours passes; at 48 does not."""
    assert make_set(outage_hours_365d=47.9).availability_check().verdict == PASS
    assert make_set(outage_hours_365d=48.0).availability_check().verdict == FAIL


def test_availability_falls_back_to_uptime_pct() -> None:
    fact_without_hours = make_set()
    del fact_without_hours.facts[0]["outage_hours_365d"]

    check = fact_without_hours.availability_check()
    assert check.verdict == PASS
    assert "uptime_pct" in check.name


def test_availability_reports_no_data_when_neither_present() -> None:
    sample_set = make_set()
    del sample_set.facts[0]["outage_hours_365d"]
    del sample_set.facts[0]["uptime_pct"]

    assert sample_set.availability_check().verdict == NO_DATA
    assert sample_set.verdict() == NO_DATA


def test_missing_test_counts_report_no_data_not_pass() -> None:
    """Absent evidence is not passing evidence."""
    sample_set = make_set()
    for key in ("download_tests_total", "download_tests_meeting_threshold"):
        del sample_set.facts[0][key]

    assert sample_set.download_check().verdict == NO_DATA
    assert sample_set.verdict() == NO_DATA


def test_failure_outranks_no_data_in_overall_verdict() -> None:
    sample_set = make_set(upload_tests_meeting_threshold=1)
    del sample_set.facts[0]["latency_tests_total"]
    assert sample_set.verdict() == FAIL


def test_cai_raises_the_required_speed_bar() -> None:
    """A community anchor institution is judged against 1 Gbps symmetric."""
    ordinary = make_set()
    assert "80 Mbps" in ordinary.download_check().name

    cai = make_set(is_cai=True)
    assert "800 Mbps" in cai.download_check().name
    assert "800 Mbps" in cai.upload_check().name


def test_committed_tier_above_floor_raises_the_bar() -> None:
    sample_set = SampleSet("NV", 50, 500.0, 100.0, [make_set().facts[0]])
    assert "400 Mbps" in sample_set.download_check().name
    assert "80 Mbps" in sample_set.upload_check().name


def test_thresholds_match_documented_constants() -> None:
    """Guard against the constants drifting away from docs/sources.md."""
    assert SPEED_MEASUREMENT_FRACTION == 0.80
    assert LATENCY_FRACTION == 0.95
    assert OUTAGE_HOURS_CEILING == 48


# ------------------------------------------------------------- sample sets


def test_grouping_separates_by_technology_code() -> None:
    base = make_set().facts[0]
    facts = [
        {
            **base,
            "state_or_territory": "NV",
            "technology_code": 71,
            "committed_down_mbps": 100.0,
            "committed_up_mbps": 20.0,
        },
        {
            **base,
            "state_or_territory": "NV",
            "technology_code": 72,
            "committed_down_mbps": 100.0,
            "committed_up_mbps": 20.0,
        },
    ]
    assert len(group_sample_sets(facts)) == 2


def test_grouping_separates_by_state() -> None:
    base = make_set().facts[0]
    facts = [
        {
            **base,
            "state_or_territory": "NV",
            "technology_code": 71,
            "committed_down_mbps": 100.0,
            "committed_up_mbps": 20.0,
        },
        {
            **base,
            "state_or_territory": "MO",
            "technology_code": 71,
            "committed_down_mbps": 100.0,
            "committed_up_mbps": 20.0,
        },
    ]
    assert len(group_sample_sets(facts)) == 2


def test_grouping_separates_by_committed_tier() -> None:
    base = make_set().facts[0]
    facts = [
        {
            **base,
            "state_or_territory": "NV",
            "technology_code": 71,
            "committed_down_mbps": 100.0,
            "committed_up_mbps": 20.0,
        },
        {
            **base,
            "state_or_territory": "NV",
            "technology_code": 71,
            "committed_down_mbps": 500.0,
            "committed_up_mbps": 100.0,
        },
    ]
    assert len(group_sample_sets(facts)) == 2


def test_location_count_deduplicates() -> None:
    fact = make_set().facts[0]
    sample_set = SampleSet("NV", 71, 100.0, 20.0, [fact, dict(fact)])
    assert sample_set.location_count == 1


# ---------------------------------------------------------- against examples


def test_gather_reads_the_example_bundle(examples_dir) -> None:
    corpus = gather(examples_dir)
    assert corpus.performance
    assert corpus.location
    assert corpus.baba
    # The deliberately invalid example lives here too, and must be counted.
    assert corpus.invalid_records == 3


def test_report_on_examples_finds_both_verdicts(examples_dir) -> None:
    """The example set is engineered so one sample set passes and one fails."""
    text = build_report(examples_dir, "2026-Q3")
    assert "# BEAD compliance summary" in text
    assert "**PASS**" in text
    assert "**FAIL**" in text
    assert "indicative" in text


def test_example_data_demonstrates_that_averages_hide_failures(examples_dir) -> None:
    """The walkthrough claims mean upload clears the bar while the set still fails.

    That claim is the main argument for carrying test counts, and it is only true
    if the example data actually exhibits it. Pinned here so regenerating the
    examples cannot quietly turn the walkthrough into a false statement.
    """
    import json
    import statistics

    records = json.loads(
        (examples_dir / "synthetic_field_telemetry.json").read_text(encoding="utf-8")
    )
    failing = [r for r in records if r["technology_code"] == 72]

    required_up = max(BSL_FLOOR_UP_MBPS, failing[0]["committed_up_mbps"])
    bar = required_up * SPEED_OF_REQUIRED_FRACTION

    mean_upload = statistics.fmean(r["upload_mbps"] for r in failing)
    total = sum(r["upload_tests_total"] for r in failing)
    met = sum(r["upload_tests_meeting_threshold"] for r in failing)
    pass_rate = met / total

    assert mean_upload > bar, (
        f"mean upload {mean_upload:.2f} must sit above the {bar:g} Mbps bar, "
        f"or the walkthrough's point about averages is false"
    )
    assert pass_rate < SPEED_MEASUREMENT_FRACTION, (
        f"upload pass rate {pass_rate:.2%} must fall short of "
        f"{SPEED_MEASUREMENT_FRACTION:.0%}, or the sample set would not fail"
    )


def test_report_shows_the_8080_bar(examples_dir) -> None:
    text = build_report(examples_dir, "2026-Q3")
    assert "at or above 80 Mbps" in text
    assert "at or above 16 Mbps" in text


def test_summarize_agrees_with_the_markdown(examples_dir) -> None:
    data = summarize(examples_dir, "2026-Q3")
    verdicts = {s["key"]: s["verdict"] for s in data["sample_sets"]}
    assert verdicts["NV-71-100x20"] == PASS
    assert verdicts["NV-72-100x20"] == FAIL

    failing = next(s for s in data["sample_sets"] if s["key"] == "NV-72-100x20")
    failed_checks = [c["name"] for c in failing["checks"] if c["verdict"] == FAIL]
    assert any("Upload" in name for name in failed_checks)


def test_period_filter_excludes_out_of_range_facts(examples_dir) -> None:
    in_q3 = summarize(examples_dir, "2026-Q3")
    in_q1 = summarize(examples_dir, "2026-Q1")
    assert in_q3["counts"]["performance"] > 0
    assert in_q1["counts"]["performance"] == 0


def test_report_survives_an_empty_period(examples_dir) -> None:
    text = build_report(examples_dir, "2026-Q1")
    assert "No performance facts in this period." in text


def test_baba_coverage_splits_by_path(examples_dir) -> None:
    text = build_report(examples_dir)
    assert "Domestic certification (manufacturer letter)" in text
    assert "Waiver (reporting tracker)" in text


def test_location_rollup_reports_built_share(examples_dir) -> None:
    text = build_report(examples_dir)
    assert "Built (installed or active)" in text


# -------------------------------------------------------------------- errors


def test_gather_rejects_missing_path(tmp_path) -> None:
    with pytest.raises(InputError, match="not found"):
        gather(tmp_path / "absent")


def test_gather_rejects_empty_directory(tmp_path) -> None:
    with pytest.raises(InputError, match="no .json, .csv, or .parquet files"):
        gather(tmp_path)


def test_render_handles_a_wholly_empty_corpus() -> None:
    text = render_report(Corpus())
    assert "No performance facts" in text
    assert "No location records found." in text
    assert "No BABA evidence records found." in text
