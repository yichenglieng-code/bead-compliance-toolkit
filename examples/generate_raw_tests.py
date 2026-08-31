#!/usr/bin/env python3
"""Regenerate the synthetic raw test observations.

These exist so the full chain is demonstrable on committed data:

    raw tests  ->  aggregate  ->  report   (compliance verdicts)
                            \\->  submit   (USAC template files)

The interesting property of this dataset is that the aggregate counts are not
written down anywhere. They are computed from the individual observations, so the
sample set that fails on upload fails because 25 of its 42 upload measurements
actually fall short, not because a summary says so.

Every value is fabricated. No real locations, subscribers, providers, or
manufacturers. Subscriber references are opaque tokens, not derived from anything.

Usage:
    python examples/generate_raw_tests.py
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20260824

SCHEMA_VERSION = "0.1.0"
ISP = "Example Rural ISP"
METHODOLOGY = "https://example-isp.example/network-management-practices#bead-testing-v3"

# NTIA: testing between 6pm and midnight local time, one speed test per testing
# hour per direction, one latency test per minute. A full week would be 2,520
# latency observations per location, which is more than a readable example needs,
# so latency is sampled at one observation per testing hour and the file documents
# that reduction rather than pretending to be a complete week.
TESTING_HOURS = [18, 19, 20, 21, 22, 23]
DAYS = 7
OFFSET = timezone(timedelta(hours=-7))  # Pacific, matching the Nevada framing
WEEK_START = datetime(2026, 7, 6, tzinfo=OFFSET)

IXP = "ixp-lasvegas-1.example-isp.example"

MBPS = 1_000_000 / 8  # bytes per second for 1 Mbps
SAMPLE_POPULATION_BY_TECH = {71: 50, 72: 4}


def uuid4(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def provenance() -> dict:
    return {
        "source_org": ISP,
        "collected_by": "field-telemetry-collector",
        "collected_at": "2026-08-01T04:00:00Z",
        "tool": "bead-data 0.1.0",
        "methodology_ref": METHODOLOGY,
    }


def speed_test(
    rng: random.Random,
    *,
    location: str,
    subscriber: str,
    tech: int,
    direction: str,
    started: datetime,
    mbps: float,
    status: str = "success",
) -> dict:
    """One speed observation. Duration is 15-20s, above the NTIA 15s minimum."""
    record = {
        "schema_version": SCHEMA_VERSION,
        "test_id": uuid4(rng),
        "location_ref": location,
        "subscriber_ref": subscriber,
        "state_or_territory": "NV",
        "technology_code": tech,
        "committed_down_mbps": 100.0,
        "committed_up_mbps": 20.0,
        "test_type": direction,
        "test_status": status,
        "started_at": started.isoformat(timespec="milliseconds"),
        "measurement_method": "ont_cpe_builtin" if tech == 71 else "cwmp_tr069",
        "device_class": "remote_node" if tech == 71 else "cpe",
        "sample_set_id": f"NV-{tech}-100x20-2026",
        "sample_population_active_subscribers": SAMPLE_POPULATION_BY_TECH[tech],
        "is_cai": False,
        "provenance": provenance(),
    }
    if status != "success":
        record["comment"] = "deferred: consumer load above the cross-traffic threshold"
        return record

    seconds = round(rng.uniform(15.0, 20.0), 3)
    record["ended_at"] = (started + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")
    record["ip_target"] = IXP
    record["bytes_transferred"] = int(mbps * MBPS * seconds)
    return record


def latency_test(
    rng: random.Random,
    *,
    location: str,
    subscriber: str,
    tech: int,
    started: datetime,
    rtt_ms: float,
    lost_all: bool = False,
) -> dict:
    """One latency observation. A fully lost test is recorded, never discarded."""
    sent = 3
    received = 0 if lost_all else sent
    return {
        "schema_version": SCHEMA_VERSION,
        "test_id": uuid4(rng),
        "location_ref": location,
        "subscriber_ref": subscriber,
        "state_or_territory": "NV",
        "technology_code": tech,
        "committed_down_mbps": 100.0,
        "committed_up_mbps": 20.0,
        "test_type": "latency",
        "test_status": "success",
        "started_at": started.isoformat(timespec="milliseconds"),
        "ip_target": IXP,
        "latency_ms_rtt": rtt_ms,
        "packets_sent": sent,
        "packets_received": received,
        "measurement_method": "ont_cpe_builtin" if tech == 71 else "cwmp_tr069",
        "device_class": "remote_node" if tech == 71 else "cpe",
        "sample_set_id": f"NV-{tech}-100x20-2026",
        "sample_population_active_subscribers": SAMPLE_POPULATION_BY_TECH[tech],
        "is_cai": False,
        "provenance": provenance(),
        **(
            {"comment": "all packets lost; recorded as a test not meeting the standard"}
            if lost_all
            else {}
        ),
    }


def slots() -> list[datetime]:
    """The 42 testing-hour slots in one measurement week."""
    return [WEEK_START + timedelta(days=d, hours=h) for d in range(DAYS) for h in TESTING_HOURS]


def build(rng: random.Random) -> list[dict]:
    records: list[dict] = []
    all_slots = slots()
    assert len(all_slots) == 42, len(all_slots)

    # ---- Sample set A: licensed spectrum (71), comfortably compliant -----------
    for i in range(2):
        loc = f"BSL-10020{3000 + i:04d}"
        sub = f"SUB-{rng.getrandbits(24):06x}"
        for n, slot in enumerate(all_slots):
            # A couple of hours fall short, well inside the 80% allowance.
            down = rng.uniform(240, 330) if n % 21 else rng.uniform(60, 78)
            up = rng.uniform(34, 46) if n % 19 else rng.uniform(10, 15)
            records.append(
                speed_test(
                    rng,
                    location=loc,
                    subscriber=sub,
                    tech=71,
                    direction="download",
                    started=slot,
                    mbps=down,
                )
            )
            records.append(
                speed_test(
                    rng,
                    location=loc,
                    subscriber=sub,
                    tech=71,
                    direction="upload",
                    started=slot,
                    mbps=up,
                )
            )
            records.append(
                latency_test(
                    rng,
                    location=loc,
                    subscriber=sub,
                    tech=71,
                    started=slot + timedelta(minutes=30),
                    rtt_ms=round(rng.uniform(14, 29), 1),
                )
            )

    # ---- Sample set B: licensed-by-rule CBRS (72), fails on upload -------------
    #
    # 25 of 42 upload observations clear the 16 Mbps bar (59.5%, short of 80%),
    # while the ones that do clear it run high enough that the mean sits above the
    # bar. That is the whole point of the example: the average passes, the
    # population does not.
    for i in range(2):
        loc = f"BSL-10020{3100 + i:04d}"
        sub = f"SUB-{rng.getrandbits(24):06x}"
        clearing = set(rng.sample(range(42), 25))
        for n, slot in enumerate(all_slots):
            records.append(
                speed_test(
                    rng,
                    location=loc,
                    subscriber=sub,
                    tech=72,
                    direction="download",
                    started=slot,
                    mbps=rng.uniform(120, 165) if n % 11 else rng.uniform(55, 75),
                )
            )
            up_mbps = rng.uniform(24, 34) if n in clearing else rng.uniform(8, 15.4)
            records.append(
                speed_test(
                    rng,
                    location=loc,
                    subscriber=sub,
                    tech=72,
                    direction="upload",
                    started=slot,
                    mbps=up_mbps,
                )
            )
            # One fully lost latency observation per location, recorded not discarded.
            records.append(
                latency_test(
                    rng,
                    location=loc,
                    subscriber=sub,
                    tech=72,
                    started=slot + timedelta(minutes=30),
                    rtt_ms=round(rng.uniform(30, 44), 1),
                    lost_all=(n == 7),
                )
            )

        # One deferral, exercising the not-run path.
        records.append(
            speed_test(
                rng,
                location=loc,
                subscriber=sub,
                tech=72,
                direction="download",
                started=all_slots[3],
                mbps=0,
                status="not_run_crosstalk",
            )
        )

    return records


def main() -> None:
    rng = random.Random(SEED)
    records = build(rng)
    target = HERE / "synthetic_raw_tests.json"
    target.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    kinds: dict[str, int] = {}
    for r in records:
        key = f"{r['test_type']}/{r['test_status']}"
        kinds[key] = kinds.get(key, 0) + 1
    print(f"wrote {target.relative_to(HERE.parent)}  ({len(records)} observations)")
    for key, count in sorted(kinds.items()):
        print(f"  {key:28} {count}")


if __name__ == "__main__":
    main()
