"""Deriving performance facts from raw test observations.

This closes a loop that matters more than it first appears. `performance_fact`
carries the numerator and denominator for each NTIA threshold, which is what makes
compliance computable. But if a submitter simply asserts those counts, the schema
can only *prohibit* a filtered denominator; it cannot detect one.

Aggregating from raw `performance_test` records makes the counts derived. A
denominator that omits failures becomes arithmetically impossible rather than
merely against the rules, because the tests are all there to be counted.

Two interpretation decisions are documented rather than buried, because reasonable
implementers could differ and a consumer needs to know which reading produced a
number:

1. **Speed denominators count measurements actually taken.** NTIA's standard is
   phrased over measurements, and a test deferred because consumer cross-traffic
   exceeded the threshold is explicitly permitted to be reported as no test
   completed for that hour. It is not a failed measurement, so it is excluded from
   the denominator and counted separately in ``tests_not_run_total``.

2. **A fully lost latency test counts against the standard.** NTIA requires
   lost-packet tests to be recorded and forbids discarding them, stating they count
   as discrete tests that do not meet the standard. So a latency test that received
   no packets is in the denominator and not in the numerator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from bead_data.models import PerformanceTest
from bead_data.report import (
    BSL_FLOOR_DOWN_MBPS,
    BSL_FLOOR_UP_MBPS,
    CAI_FLOOR_DOWN_MBPS,
    CAI_FLOOR_UP_MBPS,
    SPEED_OF_REQUIRED_FRACTION,
)
from bead_data.schemas import SCHEMA_VERSION

LATENCY_MS_CEILING = 100


class AggregationError(Exception):
    """Raised when tests cannot be aggregated."""


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _iso(value: datetime) -> str:
    return value.astimezone(tz=None).isoformat(timespec="seconds")


@dataclass
class LocationRollup:
    """Accumulator for one location's observations."""

    location_ref: str
    state_or_territory: str
    technology_code: int
    committed_down_mbps: float
    committed_up_mbps: float
    is_cai: bool = False
    sample_set_id: str | None = None
    device_class: str | None = None
    measurement_method: str | None = None
    tests: list[PerformanceTest] = field(default_factory=list)

    def required_speeds(self) -> tuple[float, float]:
        floor_down = CAI_FLOOR_DOWN_MBPS if self.is_cai else BSL_FLOOR_DOWN_MBPS
        floor_up = CAI_FLOOR_UP_MBPS if self.is_cai else BSL_FLOOR_UP_MBPS
        return (
            max(floor_down, self.committed_down_mbps),
            max(floor_up, self.committed_up_mbps),
        )


def _speed_counts(
    tests: list[PerformanceTest], direction: str, bar_mbps: float
) -> tuple[int, int, list[float]]:
    """Return (total, meeting, observed throughputs) for one direction."""
    conducted = [t for t in tests if t.test_type == direction and t.test_status == "success"]
    throughputs = [t.throughput_mbps for t in conducted if t.throughput_mbps is not None]
    meeting = sum(1 for v in throughputs if v >= bar_mbps)
    return len(conducted), meeting, throughputs


def derived_fact_id(location_ref: str, period_start: str) -> str:
    """A stable UUID v4 for the fact derived from one location and period.

    Deliberately deterministic. Re-aggregating the same observations must produce
    the same ``fact_id``, or a downstream consumer that de-duplicates on it would
    accumulate a fresh copy of the same fact on every run.

    A v5 UUID would be the conventional way to express "derived from these inputs",
    but the schema requires v4, so the digest is truncated and the version and
    variant bits are set to v4. The value is not random; it is reproducible by
    construction, which is the property that matters here.
    """
    import hashlib
    import uuid

    digest = hashlib.sha256(f"bead-fact:{location_ref}:{period_start}".encode()).digest()
    return str(uuid.UUID(bytes=digest[:16], version=4))


def aggregate_tests(records: list[dict]) -> list[dict]:
    """Roll raw test observations up into performance facts.

    One fact per location, covering the span of that location's observations.

    Raises:
        AggregationError: If records for one location disagree on the attributes
            that define which population it is judged against.
    """
    tests = [PerformanceTest.model_validate(r) for r in records]
    if not tests:
        return []

    groups: dict[str, LocationRollup] = {}
    for test in tests:
        existing = groups.get(test.location_ref)
        if existing is None:
            groups[test.location_ref] = LocationRollup(
                location_ref=test.location_ref,
                state_or_territory=test.state_or_territory,
                technology_code=test.technology_code,
                committed_down_mbps=test.committed_down_mbps,
                committed_up_mbps=test.committed_up_mbps,
                is_cai=test.is_cai,
                sample_set_id=test.sample_set_id,
                device_class=test.device_class,
                measurement_method=test.measurement_method,
                tests=[test],
            )
            continue

        for attr in (
            "state_or_territory",
            "technology_code",
            "committed_down_mbps",
            "committed_up_mbps",
        ):
            if getattr(existing, attr) != getattr(test, attr):
                raise AggregationError(
                    f"location {test.location_ref}: conflicting {attr} "
                    f"({getattr(existing, attr)!r} vs {getattr(test, attr)!r}). "
                    f"These decide which sample set the location is judged in, so they "
                    f"cannot differ between its own tests."
                )
        existing.tests.append(test)

    facts: list[dict] = []
    for rollup in sorted(groups.values(), key=lambda r: r.location_ref):
        required_down, required_up = rollup.required_speeds()
        down_bar = required_down * SPEED_OF_REQUIRED_FRACTION
        up_bar = required_up * SPEED_OF_REQUIRED_FRACTION

        down_total, down_meeting, down_values = _speed_counts(rollup.tests, "download", down_bar)
        up_total, up_meeting, up_values = _speed_counts(rollup.tests, "upload", up_bar)

        latency_conducted = [
            t for t in rollup.tests if t.test_type == "latency" and t.test_status == "success"
        ]
        latency_values = [
            t.latency_ms_rtt for t in latency_conducted if t.latency_ms_rtt is not None
        ]
        latency_meeting = sum(
            1
            for t in latency_conducted
            if (t.packets_received or 0) > 0
            and t.latency_ms_rtt is not None
            and t.latency_ms_rtt <= LATENCY_MS_CEILING
        )

        not_run = sum(1 for t in rollup.tests if t.test_status != "success")

        starts = [_parse(t.started_at) for t in rollup.tests]
        ends = [_parse(t.ended_at) for t in rollup.tests if t.ended_at] or starts

        first = rollup.tests[0]
        period_start = _iso(min(starts))
        fact = {
            "schema_version": SCHEMA_VERSION,
            "fact_id": derived_fact_id(rollup.location_ref, period_start),
            "location_ref": rollup.location_ref,
            "state_or_territory": rollup.state_or_territory,
            "technology_code": rollup.technology_code,
            "committed_down_mbps": rollup.committed_down_mbps,
            "committed_up_mbps": rollup.committed_up_mbps,
            "period_start": period_start,
            "period_end": _iso(max(ends)),
            "download_mbps": round(sum(down_values) / len(down_values), 2) if down_values else 0.0,
            "upload_mbps": round(sum(up_values) / len(up_values), 2) if up_values else 0.0,
            "latency_ms_mean": (
                round(sum(latency_values) / len(latency_values), 2) if latency_values else 0.0
            ),
            "download_tests_total": down_total,
            "download_tests_meeting_threshold": down_meeting,
            "upload_tests_total": up_total,
            "upload_tests_meeting_threshold": up_meeting,
            "latency_tests_total": len(latency_conducted),
            "latency_tests_at_or_below_100ms": latency_meeting,
            "uptime_pct": 100.0,
            "measurement_method": rollup.measurement_method or "other",
            "device_class": rollup.device_class or "other",
            "is_cai": rollup.is_cai,
            "provenance": {
                "source_org": first.provenance.source_org,
                "collected_by": first.provenance.collected_by,
                "collected_at": first.provenance.collected_at,
                "tool": f"bead-data {SCHEMA_VERSION} (aggregated from raw tests)",
            },
        }
        if rollup.sample_set_id:
            fact["sample_set_id"] = rollup.sample_set_id
        if not_run:
            fact["tests_not_run_total"] = not_run
        if first.provenance.methodology_ref:
            fact["provenance"]["methodology_ref"] = first.provenance.methodology_ref

        facts.append(fact)

    return facts


def aggregation_notes(records: list[dict], facts: list[dict]) -> list[str]:
    """Human-readable notes on what aggregation did, for the CLI to surface.

    Uptime is the one field aggregation cannot honestly derive: outage duration is
    not observable from a sample of speed and latency tests. It is emitted as 100
    and must be corrected from the provider's own outage records before the fact is
    used for an availability determination.
    """
    notes = [
        f"aggregated {len(records)} test observation(s) into {len(facts)} location fact(s)",
        "speed denominators count measurements actually taken; deferrals and failures are "
        "reported separately in tests_not_run_total",
        "a latency test that received no packets is counted in the denominator and not in "
        "the numerator, per the rule against discarding lost-packet tests",
    ]
    not_run = sum(f.get("tests_not_run_total", 0) for f in facts)
    if not_run:
        notes.append(f"{not_run} observation(s) did not run and were excluded from denominators")
    notes.append(
        "uptime_pct was set to 100 because outage duration is not observable from test "
        "samples; correct it from your outage records before relying on the availability "
        "determination"
    )
    return notes
