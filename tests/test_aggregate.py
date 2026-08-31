"""Aggregation arithmetic and the interpretation decisions behind it.

The value of deriving counts rather than accepting them is that a filtered
denominator stops being possible. These tests pin that, plus the two readings of
NTIA guidance that a reasonable implementer might get wrong in the other direction.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from bead_data.aggregate import AggregationError, aggregate_tests, derived_fact_id
from bead_data.validate import validate_records
from helpers import BASE_TIME, latency, make_test, speed

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def only_fact(records: list[dict]) -> dict:
    facts = aggregate_tests(records)
    assert len(facts) == 1, f"expected one fact, got {len(facts)}"
    return facts[0]


# ------------------------------------------------------------- basic arithmetic


def test_download_counts_are_derived_from_observations() -> None:
    """Three of four clear the 80 Mbps bar for a 100/20 commitment."""
    fact = only_fact([speed(200), speed(150), speed(90), speed(40)])
    assert fact["download_tests_total"] == 4
    assert fact["download_tests_meeting_threshold"] == 3


def test_upload_counted_separately_from_download() -> None:
    fact = only_fact([speed(200, "download"), speed(4, "upload")])
    assert fact["download_tests_total"] == 1
    assert fact["download_tests_meeting_threshold"] == 1
    assert fact["upload_tests_total"] == 1
    assert fact["upload_tests_meeting_threshold"] == 0


def test_upload_bar_is_80_percent_of_the_upload_requirement() -> None:
    """For a 100/20 commitment the upload bar is 16 Mbps."""
    fact = only_fact([speed(16.5, "upload"), speed(15.5, "upload")])
    assert fact["upload_tests_total"] == 2
    assert fact["upload_tests_meeting_threshold"] == 1


def test_throughput_is_derived_from_bytes_and_duration() -> None:
    """A 20-second test moving 250 Mbps worth of bytes is a 250 Mbps measurement."""
    fact = only_fact([speed(250, seconds=20)])
    assert fact["download_mbps"] == pytest.approx(250, rel=0.01)


def test_cai_raises_the_bar() -> None:
    """A CAI is judged against 1 Gbps symmetric, so 200 Mbps no longer clears it."""
    fact = only_fact([speed(200, is_cai=True)])
    assert fact["is_cai"] is True
    assert fact["download_tests_total"] == 1
    assert fact["download_tests_meeting_threshold"] == 0


# ----------------------------------------------------- interpretation decisions


def test_deferred_tests_are_excluded_from_denominators_but_recorded() -> None:
    """A deferral is not a failed measurement, and must not silently vanish either."""
    records = [
        speed(200),
        make_test(
            test_status="not_run_crosstalk",
            ended_at=None,
            bytes_transferred=None,
            ip_target=None,
        ),
    ]
    fact = only_fact(records)
    assert fact["download_tests_total"] == 1, "a deferral is not a measurement"
    assert fact["download_tests_meeting_threshold"] == 1
    assert fact["tests_not_run_total"] == 1, "the exclusion must stay visible"


def test_fully_lost_latency_test_counts_against_the_standard() -> None:
    """NTIA forbids discarding lost-packet tests; they count as not meeting it."""
    fact = only_fact([latency(20.0, received=3), latency(20.0, received=0)])
    assert fact["latency_tests_total"] == 2, "the lost test stays in the denominator"
    assert fact["latency_tests_at_or_below_100ms"] == 1, "and out of the numerator"


def test_latency_above_ceiling_is_not_counted() -> None:
    fact = only_fact([latency(99.0), latency(101.0)])
    assert fact["latency_tests_total"] == 2
    assert fact["latency_tests_at_or_below_100ms"] == 1


def test_latency_at_exactly_the_ceiling_counts() -> None:
    """The standard is at or below 100 ms."""
    fact = only_fact([latency(100.0)])
    assert fact["latency_tests_at_or_below_100ms"] == 1


# ------------------------------------------------------------------- integrity


def test_a_filtered_denominator_is_impossible_by_construction() -> None:
    """The central property: counts cannot be understated by omitting failures.

    A submitter aggregating from raw observations cannot produce a passing count
    above the total, because both sides are counted from the same list.
    """
    records = [speed(200)] * 3 + [speed(10)] * 7
    fact = only_fact(records)
    assert fact["download_tests_total"] == 10
    assert fact["download_tests_meeting_threshold"] == 3
    assert fact["download_tests_meeting_threshold"] <= fact["download_tests_total"]


def test_derived_facts_validate_against_the_performance_schema() -> None:
    facts = aggregate_tests([speed(200), speed(4, "upload"), latency(20.0)])
    report = validate_records(facts, "performance")
    assert report.ok, [e.format() for e in report.errors]


def test_fact_id_is_stable_across_runs() -> None:
    """Re-aggregating must not create a second copy of the same fact."""
    records = [speed(200), latency(20.0)]
    assert aggregate_tests(records)[0]["fact_id"] == aggregate_tests(records)[0]["fact_id"]


def test_fact_id_differs_by_location_and_period() -> None:
    a = derived_fact_id("BSL-1", "2026-07-06T19:00:00-07:00")
    b = derived_fact_id("BSL-2", "2026-07-06T19:00:00-07:00")
    c = derived_fact_id("BSL-1", "2026-08-06T19:00:00-07:00")
    assert len({a, b, c}) == 3


def test_conflicting_sample_set_attributes_are_rejected() -> None:
    """Tests for one location cannot disagree on which population it belongs to."""
    with pytest.raises(AggregationError, match="conflicting technology_code"):
        aggregate_tests([speed(200), speed(200, technology_code=72)])


def test_sample_population_is_carried_into_derived_fact() -> None:
    facts = aggregate_tests([speed(200, sample_population_active_subscribers=10)])
    assert facts[0]["sample_population_active_subscribers"] == 10


def test_conflicting_sample_population_is_rejected_during_aggregation() -> None:
    with pytest.raises(AggregationError, match="sample_population_active_subscribers"):
        aggregate_tests(
            [
                speed(200, sample_population_active_subscribers=10),
                speed(200, sample_population_active_subscribers=11),
            ]
        )


def test_conflicting_committed_tier_is_rejected() -> None:
    with pytest.raises(AggregationError, match="conflicting committed_down_mbps"):
        aggregate_tests([speed(200), speed(200, committed_down_mbps=500.0)])


def test_one_fact_per_location() -> None:
    facts = aggregate_tests([speed(200), speed(200, location_ref="BSL-OTHER"), latency(20.0)])
    assert {f["location_ref"] for f in facts} == {"BSL-1002003004", "BSL-OTHER"}


def test_empty_input_produces_no_facts() -> None:
    assert aggregate_tests([]) == []


def test_period_spans_the_observations() -> None:
    late = speed(200, seconds=16)
    late["started_at"] = (BASE_TIME + timedelta(days=3)).isoformat(timespec="milliseconds")
    late["ended_at"] = (BASE_TIME + timedelta(days=3, seconds=16)).isoformat(
        timespec="milliseconds"
    )
    fact = only_fact([speed(200), late])
    assert fact["period_start"] < fact["period_end"]


# ------------------------------------------------------------ against examples


def test_example_raw_tests_aggregate_to_the_documented_outcome() -> None:
    """The committed example must produce the failure the walkthrough describes."""
    records = json.loads((EXAMPLES / "synthetic_raw_tests.json").read_text(encoding="utf-8"))
    facts = aggregate_tests(records)
    assert validate_records(facts, "performance").ok

    cbrs = [f for f in facts if f["technology_code"] == 72]
    assert cbrs, "expected CBRS locations in the example set"
    for fact in cbrs:
        rate = fact["upload_tests_meeting_threshold"] / fact["upload_tests_total"]
        assert rate < 0.80, f"{fact['location_ref']} upload should fall short, got {rate:.3f}"
        down = fact["download_tests_meeting_threshold"] / fact["download_tests_total"]
        assert down >= 0.80, f"{fact['location_ref']} download should pass, got {down:.3f}"

    licensed = [f for f in facts if f["technology_code"] == 71]
    for fact in licensed:
        for subset, total in (
            ("download_tests_meeting_threshold", "download_tests_total"),
            ("upload_tests_meeting_threshold", "upload_tests_total"),
        ):
            assert fact[subset] / fact[total] >= 0.80


def test_example_raw_tests_record_a_lost_latency_observation() -> None:
    """The example exercises the lost-packet rule rather than only describing it."""
    records = json.loads((EXAMPLES / "synthetic_raw_tests.json").read_text(encoding="utf-8"))
    lost = [r for r in records if r["test_type"] == "latency" and r.get("packets_received") == 0]
    assert lost, "no fully lost latency observation in the example set"
    for r in lost:
        assert r["test_status"] == "success", "a lost test still ran; it is not 'not run'"
