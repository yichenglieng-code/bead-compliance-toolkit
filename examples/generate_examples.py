#!/usr/bin/env python3
"""Regenerate the synthetic example data.

The examples are committed, so this script is not needed to use the toolkit. It is
here so the numbers in ``examples/`` are reproducible and auditable rather than
hand-typed: the compliance outcomes in the walkthrough are supposed to be
deliberate, and a reader should be able to see how they were arrived at.

Every value is fabricated. There are no real locations, subscribers, providers, or
manufacturers anywhere in this file. Location ids use an obviously synthetic
``BSL-100200xxxx`` pattern and organizations are named "Example ...".

Usage:
    python examples/generate_examples.py
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent

SEED = 20260824  # fixed so regeneration is deterministic

SCHEMA_VERSION = "0.1.0"

COLLECTED_AT = "2026-08-01T04:00:00Z"
TOOL = "bead-data 0.1.0"

# One measurement week, inside 2026 Q3, per the NTIA one-week testing window.
PERIOD_START = "2026-07-06T00:00:00Z"
PERIOD_END = "2026-07-12T23:59:59Z"

# NTIA testing: one speed test per testing hour, 6pm to midnight, seven days = 42.
SPEED_TESTS_PER_LOCATION = 42
# One latency test per minute across those same 6 hours a day for 7 days = 2520.
LATENCY_TESTS_PER_LOCATION = 2520

ISP = "Example Rural ISP"
MANUFACTURER = "Example Broadband Equipment Co."


def uuid4(rng: random.Random) -> str:
    """Deterministic UUID v4 so regeneration produces identical files."""
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def provenance(source_org: str, collected_by: str, methodology: str | None = None) -> dict:
    block = {
        "source_org": source_org,
        "collected_by": collected_by,
        "collected_at": COLLECTED_AT,
        "tool": TOOL,
    }
    if methodology:
        block["methodology_ref"] = methodology
    return block


# --------------------------------------------------------------------------
# 1. Factory export: a manufacturer's end-of-line test results
# --------------------------------------------------------------------------


def factory_export(rng: random.Random) -> list[dict]:
    """20 performance facts in the manufacturer framing.

    A manufacturer runs end-of-line verification on each unit before it ships, so
    device_class varies and the measurement comes from the unit's own built-in
    capability rather than from a field gateway.
    """
    records = []
    for i in range(20):
        device_class = "base_node" if i % 5 == 0 else "remote_node"
        # Factory conditions are controlled, so results cluster high and tight.
        download = round(rng.uniform(295.0, 340.0), 1)
        upload = round(rng.uniform(38.0, 48.0), 1)
        latency = round(rng.uniform(9.0, 16.0), 1)

        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "fact_id": uuid4(rng),
                "location_ref": f"BSL-10020{4000 + i:04d}",
                "state_or_territory": "NV",
                "technology_code": 71,
                "committed_down_mbps": 100.0,
                "committed_up_mbps": 20.0,
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "download_mbps": download,
                "upload_mbps": upload,
                "latency_ms_mean": latency,
                "download_tests_total": SPEED_TESTS_PER_LOCATION,
                "download_tests_meeting_threshold": SPEED_TESTS_PER_LOCATION,
                "upload_tests_total": SPEED_TESTS_PER_LOCATION,
                "upload_tests_meeting_threshold": SPEED_TESTS_PER_LOCATION,
                "latency_tests_total": LATENCY_TESTS_PER_LOCATION,
                "latency_tests_at_or_below_100ms": LATENCY_TESTS_PER_LOCATION,
                "uptime_pct": 100.0,
                "outage_hours_365d": 0.0,
                "measurement_method": "ont_cpe_builtin",
                "device_class": device_class,
                "sample_set_id": "NV-71-100x20-2026",
                "sample_population_active_subscribers": 50,
                "is_cai": False,
                "provenance": provenance(
                    MANUFACTURER,
                    "mfg-exporter",
                    "https://example-equipment.example/test-methodology/v2",
                ),
            }
        )
    return records


# --------------------------------------------------------------------------
# 2. Field telemetry: an ISP's measurement week, engineered to be interesting
# --------------------------------------------------------------------------


def field_telemetry(rng: random.Random) -> list[dict]:
    """10 performance facts in the ISP framing, across two sample sets.

    Deliberately not all-passing. The licensed sample set (technology code 71)
    clears all four thresholds. The licensed-by-rule set (code 72, shared CBRS
    spectrum) fails on upload, which is the realistic failure mode for shared
    spectrum under contention, and demonstrates that the report catches a failure
    in one sample set without contaminating the other.
    """
    records: list[dict] = []

    # Sample set A: licensed spectrum, comfortably compliant.
    for i in range(6):
        download = round(rng.uniform(240.0, 330.0), 1)
        upload = round(rng.uniform(34.0, 46.0), 1)
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "fact_id": uuid4(rng),
                "location_ref": f"BSL-10020{3000 + i:04d}",
                "state_or_territory": "NV",
                "technology_code": 71,
                "committed_down_mbps": 100.0,
                "committed_up_mbps": 20.0,
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "download_mbps": download,
                "upload_mbps": upload,
                "latency_ms_mean": round(rng.uniform(16.0, 28.0), 1),
                "latency_ms_loaded": round(rng.uniform(35.0, 55.0), 1),
                "download_tests_total": SPEED_TESTS_PER_LOCATION,
                "download_tests_meeting_threshold": SPEED_TESTS_PER_LOCATION - rng.randint(0, 2),
                "upload_tests_total": SPEED_TESTS_PER_LOCATION,
                "upload_tests_meeting_threshold": SPEED_TESTS_PER_LOCATION - rng.randint(0, 3),
                "latency_tests_total": LATENCY_TESTS_PER_LOCATION,
                "latency_tests_at_or_below_100ms": LATENCY_TESTS_PER_LOCATION - rng.randint(10, 40),
                "uptime_pct": round(rng.uniform(99.6, 99.95), 2),
                "outage_hours_365d": round(rng.uniform(4.0, 30.0), 1),
                "measurement_method": "ont_cpe_builtin",
                "device_class": "remote_node",
                "sample_set_id": "NV-71-100x20-2026",
                "sample_population_active_subscribers": 50,
                "is_cai": False,
                "provenance": provenance(
                    ISP,
                    "field-telemetry-collector",
                    "https://example-isp.example/network-management-practices#bead-testing-v3",
                ),
            }
        )

    # Sample set B: licensed-by-rule (CBRS GAA) spectrum, fails upload.
    #
    # 59.5% of upload measurements clear the 16 Mbps bar (25 of 42), short of the
    # 80% NTIA requires. The per-location MEAN upload is deliberately set above
    # 16 Mbps even so, which is the whole teaching point of this example: on a
    # bursty contended link the successful tests run far enough above the bar to
    # pull the average over it, while most tests still fall short. A report built
    # on averages would show a passing number here for a failing network. That is
    # why performance_fact carries test counts and not just means.
    for i in range(4):
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "fact_id": uuid4(rng),
                "location_ref": f"BSL-10020{3100 + i:04d}",
                "state_or_territory": "NV",
                "technology_code": 72,
                "committed_down_mbps": 100.0,
                "committed_up_mbps": 20.0,
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "download_mbps": round(rng.uniform(120.0, 165.0), 1),
                "upload_mbps": round(rng.uniform(17.2, 19.4), 1),
                "latency_ms_mean": round(rng.uniform(30.0, 44.0), 1),
                "latency_ms_loaded": round(rng.uniform(60.0, 95.0), 1),
                "download_tests_total": SPEED_TESTS_PER_LOCATION,
                "download_tests_meeting_threshold": 38,
                "upload_tests_total": SPEED_TESTS_PER_LOCATION,
                "upload_tests_meeting_threshold": 25,
                "latency_tests_total": LATENCY_TESTS_PER_LOCATION,
                "latency_tests_at_or_below_100ms": LATENCY_TESTS_PER_LOCATION
                - rng.randint(60, 110),
                "uptime_pct": round(rng.uniform(99.2, 99.6), 2),
                "outage_hours_365d": round(rng.uniform(30.0, 46.0), 1),
                "measurement_method": "cwmp_tr069",
                "device_class": "cpe",
                "sample_set_id": "NV-72-100x20-2026",
                "sample_population_active_subscribers": 4,
                "is_cai": False,
                "provenance": provenance(
                    ISP,
                    "field-telemetry-collector",
                    "https://example-isp.example/network-management-practices#bead-testing-v3",
                ),
            }
        )

    return records


# --------------------------------------------------------------------------
# 3. Locations
# --------------------------------------------------------------------------


def locations(rng: random.Random) -> list[dict]:
    """14 funded locations spread across the build lifecycle."""
    plan = (
        [("active", 6)]
        + [("installed", 3)]
        + [("under_construction", 2)]
        + [("planned", 2)]
        + [("suspended", 1)]
    )

    records: list[dict] = []
    index = 0
    for status, count in plan:
        for _ in range(count):
            technology_code = 71 if index % 3 else 72
            record = {
                "schema_version": SCHEMA_VERSION,
                "location_id": f"BSL-10020{3000 + index:04d}",
                "state_or_territory": "NV",
                "latitude": round(39.10 + rng.uniform(0, 0.4), 4),
                "longitude": round(-119.90 + rng.uniform(0, 0.4), 4),
                "service_status": status,
                "technology_code": technology_code,
                "max_advertised_down_mbps": 300.0,
                "max_advertised_up_mbps": 50.0,
                "is_cai": False,
                "provenance": provenance(ISP, "deployment-tracker"),
            }
            if status in ("installed", "active"):
                record["install_date"] = f"2026-0{rng.randint(3, 6)}-{rng.randint(10, 28)}"
                record["active_subscriber_count"] = 1 if status == "active" else 0
            records.append(record)
            index += 1

    return records


# --------------------------------------------------------------------------
# 4. BABA bundle
# --------------------------------------------------------------------------


def baba_bundle(rng: random.Random) -> list[tuple[str, dict]]:
    """5 BABA evidence records: 4 domestic certifications, 1 waiver.

    The split mirrors the NTIA framework, where equipment requiring domestic
    production is covered by a manufacturer certification letter and waived
    finished electronics are covered by the waiver reporting tracker instead.
    """
    certified = [
        (
            "base_node_b200",
            "Example FWA Base Node B200",
            "radio",
            "Sector base node terminating fixed wireless subscriber links at a tower site.",
            24,
        ),
        (
            "remote_node_r100",
            "Example FWA Remote Node R100",
            "radio",
            "Outdoor subscriber radio unit terminating the fixed wireless link at the premises.",
            310,
        ),
        (
            "power_system_p12",
            "Example Tower Power System P12",
            "power_system",
            "DC power plant and battery backup for tower-mounted radio equipment.",
            8,
        ),
        (
            "enclosure_e30",
            "Example Outdoor Enclosure E30",
            "enclosure",
            "Weather-rated equipment cabinet housing tower-site electronics.",
            8,
        ),
    ]

    out: list[tuple[str, dict]] = []

    for slug, name, category, description, quantity in certified:
        out.append(
            (
                f"{slug}.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "evidence_id": uuid4(rng),
                    "compliance_path": "domestic_certification",
                    "component": name,
                    "component_type": "device",
                    "component_description": description,
                    "product_category": category,
                    "manufacturer_name": MANUFACTURER,
                    "origin_country": "US",
                    "quantity": quantity,
                    "manufacturing_location": "Austin, Texas, United States",
                    "certification_ref": f"CERT-2026-{rng.randint(1000, 9999)}",
                    "requirement_ref": "BEAD BABA waiver, Section III.A.2.a (Electronics)",
                    "certifying_representative": "VP of Operations",
                    "bead_project_ref": "NV-BEAD-2026-014",
                    "attestation_doc_sha256": f"{rng.getrandbits(256):064x}",
                    "attestation_doc_uri": (
                        f"https://example-equipment.example/baba/{slug}-cert.pdf"
                    ),
                    "provenance": provenance(MANUFACTURER, "compliance-exporter"),
                },
            )
        )

    out.append(
        (
            "aggregation_switch_s48.json",
            {
                "schema_version": SCHEMA_VERSION,
                "evidence_id": uuid4(rng),
                "compliance_path": "waiver",
                "component": "Example Aggregation Switch S48",
                "component_type": "device",
                "component_description": (
                    "48-port aggregation switch backhauling tower sites to the regional core."
                ),
                "product_category": "switch",
                "manufacturer_name": "Example Networking Systems Inc.",
                "origin_country": "VN",
                "quantity": 6,
                "waiver_ref": "BEAD-BABA-WAIVER-2024-02-23",
                "waiver_type": "general_applicability",
                "hs_code_10": "8517620090",
                "product_identifier": "EX-S48-AGG",
                "bead_project_ref": "NV-BEAD-2026-014",
                "provenance": provenance(ISP, "compliance-exporter"),
            },
        )
    )

    return out


# --------------------------------------------------------------------------
# 5. The deliberately invalid file
# --------------------------------------------------------------------------


def invalid_rows(valid: list[dict]) -> list[dict]:
    """Copy of the factory export with three rows broken on purpose.

    Each break is a different class of failure, so the companion file exercises
    schema validation, enum validation, and a cross-field rule. Documented in
    examples/walkthrough.md.
    """
    rows = [dict(r) for r in valid[:6]]

    # 1. Cross-field rule: more passing latency tests than tests conducted.
    rows[1]["latency_tests_at_or_below_100ms"] = rows[1]["latency_tests_total"] + 500

    # 2. Enum: an intuitive but NTIA-unrecognized measurement method.
    rows[3]["measurement_method"] = "speedtest"

    # 3. Range: uptime above 100 percent.
    rows[5]["uptime_pct"] = 104.5

    return rows


# --------------------------------------------------------------------------


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(HERE.parent)}")


def write_csv(path: Path, records: list[dict]) -> None:
    from bead_data.convert import to_csv

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_csv(records, "performance"), encoding="utf-8")
    print(f"wrote {path.relative_to(HERE.parent)}")


def main() -> None:
    rng = random.Random(SEED)

    factory = factory_export(rng)
    write_csv(HERE / "synthetic_factory_export.csv", factory)
    write_csv(HERE / "synthetic_factory_export.invalid.csv", invalid_rows(factory))

    write_json(HERE / "synthetic_field_telemetry.json", field_telemetry(rng))
    write_json(HERE / "synthetic_locations.json", locations(rng))

    bundle = HERE / "synthetic_baba_bundle"
    for filename, record in baba_bundle(rng):
        write_json(bundle / filename, record)


if __name__ == "__main__":
    main()
