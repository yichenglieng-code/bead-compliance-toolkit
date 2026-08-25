"""Record builders shared between test modules.

Kept in its own module rather than imported across test files. ``pytest`` inserts
the test directory onto ``sys.path``, so ``from helpers import ...`` resolves under
both the ``pytest`` console script and ``python -m pytest``.

Importing one test module from another does not: ``python -m pytest`` puts the
working directory on ``sys.path`` and the console script does not, so
``from tests.test_aggregate import ...`` passes locally and fails in CI. That
happened, and this module is the fix.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

#: Pacific offset, matching the Nevada framing used throughout the examples.
OFFSET = timezone(timedelta(hours=-7))

#: Inside NTIA's 6pm-to-midnight testing window.
BASE_TIME = datetime(2026, 7, 6, 19, 0, tzinfo=OFFSET)

#: Bytes per second for 1 Mbps.
MBPS_BYTES = 1_000_000 / 8


def make_test(**overrides) -> dict:
    """A valid ``performance_test`` download observation, tunable per test."""
    record = {
        "schema_version": "0.1.0",
        "test_id": "7d9d2e1a-2b4f-4e88-9a1d-3f5b8e7c0a12",
        "location_ref": "BSL-1002003004",
        "state_or_territory": "NV",
        "technology_code": 71,
        "committed_down_mbps": 100.0,
        "committed_up_mbps": 20.0,
        "test_type": "download",
        "test_status": "success",
        "started_at": BASE_TIME.isoformat(timespec="milliseconds"),
        "ended_at": (BASE_TIME + timedelta(seconds=16)).isoformat(timespec="milliseconds"),
        "ip_target": "ixp.example",
        "bytes_transferred": int(200 * MBPS_BYTES * 16),
        "provenance": {
            "source_org": "Example Rural ISP",
            "collected_by": "collector",
            "collected_at": "2026-08-01T04:00:00Z",
        },
    }
    record.update(overrides)
    return record


def speed(mbps: float, direction: str = "download", seconds: float = 16.0, **kw) -> dict:
    """A successful speed observation at a given throughput.

    Duration defaults to 16 seconds, above the 15 second NTIA minimum. Bytes are
    computed from throughput and duration so the record is internally consistent.
    """
    return make_test(
        test_type=direction,
        ended_at=(BASE_TIME + timedelta(seconds=seconds)).isoformat(timespec="milliseconds"),
        bytes_transferred=int(mbps * MBPS_BYTES * seconds),
        **kw,
    )


def latency(rtt: float, received: int = 3, **kw) -> dict:
    """A successful latency observation. ``received=0`` is a fully lost test."""
    return make_test(
        test_type="latency",
        latency_ms_rtt=rtt,
        packets_sent=3,
        packets_received=received,
        ended_at=None,
        bytes_transferred=None,
        **kw,
    )
