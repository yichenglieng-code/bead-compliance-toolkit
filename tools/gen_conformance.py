#!/usr/bin/env python3
"""Author the language-agnostic conformance suite.

A schema anyone can implement is only useful if they can check their
implementation against the same expectations the reference one holds itself to.
This script writes those expectations out as plain JSON test vectors under
`conformance/`, so an implementation in any language can consume them without
running any Python.

Each case is a self-contained JSON file stating the instance, whether it should
validate, which fields should be blamed if not, and why the rule exists. The
rationale is part of the artifact, not a comment: an implementer who disagrees
with a case needs to know what it is asserting and on whose authority.

Usage:
    python tools/gen_conformance.py           # write the suite
    python tools/gen_conformance.py --check   # fail if it would change
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bead_data.schemas import SCHEMA_VERSION  # noqa: E402

OUT = REPO / "conformance"
CASES = OUT / "cases"

SUITE_VERSION = "0.1.0"

PROVENANCE = {
    "source_org": "Example Rural ISP",
    "collected_by": "field-telemetry-collector",
    "collected_at": "2026-08-01T04:00:00Z",
    "tool": "bead-data 0.1.0",
}

PERFORMANCE = {
    "schema_version": SCHEMA_VERSION,
    "fact_id": "7d9d2e1a-2b4f-4e88-9a1d-3f5b8e7c0a12",
    "location_ref": "BSL-1002003004",
    "state_or_territory": "NV",
    "technology_code": 71,
    "committed_down_mbps": 100.0,
    "committed_up_mbps": 20.0,
    "period_start": "2026-07-06T00:00:00Z",
    "period_end": "2026-07-12T23:59:59Z",
    "download_mbps": 312.5,
    "upload_mbps": 41.2,
    "latency_ms_mean": 18.6,
    "download_tests_total": 42,
    "download_tests_meeting_threshold": 41,
    "upload_tests_total": 42,
    "upload_tests_meeting_threshold": 40,
    "latency_tests_total": 2520,
    "latency_tests_at_or_below_100ms": 2498,
    "uptime_pct": 99.82,
    "outage_hours_365d": 12.5,
    "measurement_method": "ont_cpe_builtin",
    "device_class": "remote_node",
    "provenance": dict(PROVENANCE),
}

LOCATION = {
    "schema_version": SCHEMA_VERSION,
    "location_id": "BSL-1002003004",
    "state_or_territory": "NV",
    "latitude": 39.1638,
    "longitude": -119.7674,
    "service_status": "active",
    "install_date": "2026-05-14",
    "technology_code": 71,
    "provenance": dict(PROVENANCE),
}

BABA_CERT = {
    "schema_version": SCHEMA_VERSION,
    "evidence_id": "1d9d2e1a-2b4f-4e88-9a1d-3f5b8e7c0a12",
    "compliance_path": "domestic_certification",
    "component": "Example FWA Base Node B200",
    "component_type": "device",
    "component_description": "Sector base node terminating fixed wireless subscriber links.",
    "manufacturer_name": "Example Broadband Equipment Co.",
    "origin_country": "US",
    "quantity": 24,
    "manufacturing_location": "Austin, Texas, United States",
    "certification_ref": "CERT-2026-0417-A",
    "provenance": dict(PROVENANCE),
}

BABA_WAIVER = {
    "schema_version": SCHEMA_VERSION,
    "evidence_id": "2e8c3f66-4c2d-4b09-9e11-5a9c0d8b6e34",
    "compliance_path": "waiver",
    "component": "Example Aggregation Switch S48",
    "component_type": "device",
    "component_description": "48-port aggregation switch backhauling tower sites.",
    "product_category": "switch",
    "manufacturer_name": "Example Networking Systems Inc.",
    "origin_country": "VN",
    "quantity": 6,
    "waiver_ref": "BEAD-BABA-WAIVER-2024-02-23",
    "waiver_type": "general_applicability",
    "hs_code_10": "8517620090",
    "product_identifier": "EX-S48-AGG",
    "provenance": dict(PROVENANCE),
}

TEST_SPEED = {
    "schema_version": SCHEMA_VERSION,
    "test_id": "3f1c9a2b-6d4e-4f81-9c27-8a5b0e3d7f60",
    "location_ref": "BSL-1002003004",
    "subscriber_ref": "SUB-8f21a4",
    "state_or_territory": "NV",
    "technology_code": 71,
    "committed_down_mbps": 100.0,
    "committed_up_mbps": 20.0,
    "test_type": "download",
    "test_status": "success",
    "started_at": "2026-07-06T19:03:01.123-07:00",
    "ended_at": "2026-07-06T19:03:17.456-07:00",
    "ip_target": "ixp-lasvegas-1.example-isp.example",
    "bytes_transferred": 640000000,
    "measurement_method": "ont_cpe_builtin",
    "device_class": "remote_node",
    "provenance": dict(PROVENANCE),
}

TEST_LATENCY = {
    "schema_version": SCHEMA_VERSION,
    "test_id": "4a2d8b13-7e5f-4c92-8d31-9b6c1f4e8a72",
    "location_ref": "BSL-1002003004",
    "subscriber_ref": "SUB-8f21a4",
    "state_or_territory": "NV",
    "technology_code": 71,
    "committed_down_mbps": 100.0,
    "committed_up_mbps": 20.0,
    "test_type": "latency",
    "test_status": "success",
    "started_at": "2026-07-06T19:30:00.000-07:00",
    "ip_target": "ixp-lasvegas-1.example-isp.example",
    "latency_ms_rtt": 21.4,
    "packets_sent": 3,
    "packets_received": 3,
    "measurement_method": "ont_cpe_builtin",
    "device_class": "remote_node",
    "provenance": dict(PROVENANCE),
}

BASE = {
    "performance": PERFORMANCE,
    "location": LOCATION,
    "baba_cert": BABA_CERT,
    "baba_waiver": BABA_WAIVER,
    "test_speed": TEST_SPEED,
    "test_latency": TEST_LATENCY,
}

SCHEMA_OF = {
    "performance": "performance",
    "location": "location",
    "baba_cert": "baba",
    "baba_waiver": "baba",
    "test_speed": "test",
    "test_latency": "test",
}


@dataclass
class Case:
    """One conformance vector."""

    name: str
    base: str
    description: str
    rationale: str
    valid: bool
    remove: list[str] = field(default_factory=list)
    patch: dict = field(default_factory=dict)
    expect_fields: list[str] = field(default_factory=list)
    remove_provenance: list[str] = field(default_factory=list)

    def instance(self) -> dict:
        record = json.loads(json.dumps(BASE[self.base]))
        for key in self.remove:
            record.pop(key, None)
        for key in self.remove_provenance:
            record["provenance"].pop(key, None)
        record.update(json.loads(json.dumps(self.patch)))
        return record

    def to_json(self) -> dict:
        payload = {
            "conformance_suite_version": SUITE_VERSION,
            "name": self.name,
            "schema": SCHEMA_OF[self.base],
            "description": self.description,
            "rationale": self.rationale,
            "valid": self.valid,
            "instance": self.instance(),
        }
        if not self.valid:
            payload["expect_fields"] = sorted(self.expect_fields)
        return payload


def cases() -> list[Case]:
    out: list[Case] = []

    # ---------------------------------------------------------------- valid
    out += [
        Case(
            "performance/valid_minimal",
            "performance",
            "A performance fact with only the required fields.",
            "Establishes the required-field floor. An implementation that rejects this "
            "is over-constraining.",
            True,
            remove=[
                "latency_ms_loaded",
                "download_tests_total",
                "download_tests_meeting_threshold",
                "upload_tests_total",
                "upload_tests_meeting_threshold",
                "latency_tests_total",
                "latency_tests_at_or_below_100ms",
                "outage_hours_365d",
            ],
            remove_provenance=["tool"],
        ),
        Case(
            "performance/valid_full",
            "performance",
            "A performance fact with every field populated.",
            "Establishes that optional fields are accepted, not merely tolerated.",
            True,
            patch={
                "latency_ms_loaded": 42.3,
                "sample_set_id": "NV-71-100x20-2026",
                "is_cai": False,
                "provenance": dict(PROVENANCE, methodology_ref="https://example-isp.example/nmp"),
            },
        ),
        Case(
            "performance/valid_cai",
            "performance",
            "A community anchor institution fact.",
            "CAIs are judged against the 1 Gbps symmetric standard rather than 100/20, so "
            "is_cai must be representable and must not itself invalidate a record.",
            True,
            patch={"is_cai": True, "committed_down_mbps": 1000.0, "committed_up_mbps": 1000.0},
        ),
        Case(
            "location/valid_active",
            "location",
            "An active funded location.",
            "Baseline for the location family.",
            True,
        ),
        Case(
            "location/valid_planned_without_install_date",
            "location",
            "A planned location with no install_date.",
            "install_date is conditionally required. A location not yet built must be "
            "representable without inventing a build date.",
            True,
            remove=["install_date"],
            patch={"service_status": "planned"},
        ),
        Case(
            "baba/valid_domestic_certification",
            "baba_cert",
            "BABA evidence on the domestic certification path.",
            "Baseline for the path backed by a manufacturer's certification letter.",
            True,
        ),
        Case(
            "baba/valid_waiver",
            "baba_waiver",
            "BABA evidence on the waiver path.",
            "Baseline for the path reported through the NTIA waiver tracker.",
            True,
        ),
    ]

    # --------------------------------------------- missing required fields
    for f in (
        "fact_id",
        "location_ref",
        "state_or_territory",
        "technology_code",
        "committed_down_mbps",
        "period_start",
        "period_end",
        "download_mbps",
        "uptime_pct",
        "measurement_method",
        "device_class",
        "provenance",
    ):
        out.append(
            Case(
                f"performance/missing_{f}",
                "performance",
                f"Required field {f} is absent.",
                "Required fields are required. Accepting the record would let an "
                "unanswerable submission travel downstream.",
                False,
                remove=[f],
                expect_fields=[f],
            )
        )

    for f in ("location_id", "latitude", "longitude", "service_status", "technology_code"):
        out.append(
            Case(
                f"location/missing_{f}",
                "location",
                f"Required field {f} is absent.",
                "Required fields are required.",
                False,
                remove=[f],
                expect_fields=[f],
            )
        )

    for f in (
        "component",
        "component_type",
        "component_description",
        "manufacturer_name",
        "origin_country",
        "quantity",
        "compliance_path",
    ):
        out.append(
            Case(
                f"baba/missing_{f}",
                "baba_cert",
                f"Required field {f} is absent.",
                "Required fields are required.",
                False,
                remove=[f],
                expect_fields=[f],
            )
        )

    # ------------------------------------------------------ provenance rules
    for f in ("source_org", "collected_by", "collected_at"):
        out.append(
            Case(
                f"provenance/missing_{f}",
                "performance",
                f"Provenance is missing {f}.",
                "Evidence that passes between three organizations is only auditable if it "
                "carries its own origin, so provenance is required in full.",
                False,
                remove_provenance=[f],
                expect_fields=[f"provenance.{f}"],
            )
        )

    out.append(
        Case(
            "provenance/collected_at_not_iso8601",
            "performance",
            "collected_at is not an ISO 8601 date-time.",
            "A timestamp that cannot be parsed cannot be reconciled against a testing window.",
            False,
            patch={"provenance": dict(PROVENANCE, collected_at="August 1st 2026")},
            expect_fields=["provenance.collected_at"],
        )
    )

    # ------------------------------------------------------------- enums
    out += [
        Case(
            "performance/enum_measurement_method_speedtest",
            "performance",
            "measurement_method is 'speedtest'.",
            "NTIA requires active measurement and names the acceptable mechanisms. A "
            "third-party web speed test is not among them. This is the most likely "
            "wrong answer, so it is pinned explicitly.",
            False,
            patch={"measurement_method": "speedtest"},
            expect_fields=["measurement_method"],
        ),
        Case(
            "performance/enum_device_class_unknown",
            "performance",
            "device_class is a vendor product name.",
            "Equipment is described by generic class so no vendor vocabulary enters a "
            "sector-wide interchange format.",
            False,
            patch={"device_class": "acme_radio_9000"},
            expect_fields=["device_class"],
        ),
        Case(
            "performance/enum_technology_code_invalid",
            "performance",
            "technology_code is not an FCC fixed technology code.",
            "NTIA separates sample sets by FCC technology code, so an unrecognised code "
            "would place a location in no comparable population.",
            False,
            patch={"technology_code": 99},
            expect_fields=["technology_code"],
        ),
        Case(
            "location/enum_service_status_invalid",
            "location",
            "service_status is outside the lifecycle enum.",
            "The lifecycle vocabulary is fixed so that build progress rolls up "
            "consistently between parties.",
            False,
            patch={"service_status": "in_progress"},
            expect_fields=["service_status"],
        ),
        Case(
            "baba/enum_component_type_invalid",
            "baba_cert",
            "component_type is outside the BABA category enum.",
            "BABA reaches iron, steel, manufactured products, and construction "
            "materials; the categories map onto that treatment.",
            False,
            patch={"component_type": "widget"},
            expect_fields=["component_type"],
        ),
        Case(
            "baba/enum_compliance_path_invalid",
            "baba_cert",
            "compliance_path is neither of the two NTIA paths.",
            "NTIA operates exactly two compliance paths.",
            False,
            patch={"compliance_path": "self_certified"},
            expect_fields=["compliance_path"],
        ),
    ]

    # ------------------------------------------------------------ patterns
    out += [
        Case(
            "performance/pattern_fact_id_not_uuid4",
            "performance",
            "fact_id is not a UUID v4.",
            "A stable unique id lets the same fact be de-duplicated after passing "
            "through several organizations.",
            False,
            patch={"fact_id": "fact-1"},
            expect_fields=["fact_id"],
        ),
        Case(
            "performance/pattern_state_not_two_letters",
            "performance",
            "state_or_territory is a full state name.",
            "NTIA evaluates per state or territory; a fixed two-letter code keeps that "
            "grouping unambiguous.",
            False,
            patch={"state_or_territory": "Nevada"},
            expect_fields=["state_or_territory"],
        ),
        Case(
            "baba/pattern_origin_country_alpha3",
            "baba_waiver",
            "origin_country uses ISO alpha-3 instead of alpha-2.",
            "Country of origin is the field giving NTIA visibility into waived "
            "electronics, so one fixed representation is required.",
            False,
            patch={"origin_country": "USA"},
            expect_fields=["origin_country"],
        ),
        Case(
            "baba/pattern_hs_code_too_short",
            "baba_waiver",
            "hs_code_10 has eight digits.",
            "The NTIA waiver reporting tracker specifies a 10-digit HS code.",
            False,
            patch={"hs_code_10": "85176200"},
            expect_fields=["hs_code_10"],
        ),
        Case(
            "baba/pattern_sha256_not_hex",
            "baba_cert",
            "attestation_doc_sha256 is not 64 lowercase hex characters.",
            "The digest lets a reviewer confirm the retained document matches this "
            "record without the document travelling alongside it.",
            False,
            patch={"attestation_doc_sha256": "not-a-digest"},
            expect_fields=["attestation_doc_sha256"],
        ),
    ]

    # -------------------------------------------------------------- ranges
    out += [
        Case(
            "performance/range_uptime_above_100",
            "performance",
            "uptime_pct is greater than 100.",
            "A percentage above 100 is not a measurement.",
            False,
            patch={"uptime_pct": 104.5},
            expect_fields=["uptime_pct"],
        ),
        Case(
            "performance/range_negative_download",
            "performance",
            "download_mbps is negative.",
            "Throughput cannot be negative.",
            False,
            patch={"download_mbps": -1.0},
            expect_fields=["download_mbps"],
        ),
        Case(
            "performance/range_committed_below_floor",
            "performance",
            "committed_down_mbps is below the 100 Mbps floor.",
            "NTIA defines the committed speed tier as not less than 100 Mbps down and "
            "20 Mbps up, so a lower tier cannot be a BEAD commitment.",
            False,
            patch={"committed_down_mbps": 50.0},
            expect_fields=["committed_down_mbps"],
        ),
        Case(
            "performance/range_committed_up_below_floor",
            "performance",
            "committed_up_mbps is below the 20 Mbps floor.",
            "Same floor, upload side.",
            False,
            patch={"committed_up_mbps": 10.0},
            expect_fields=["committed_up_mbps"],
        ),
        Case(
            "location/range_latitude_out_of_bounds",
            "location",
            "latitude exceeds 90 degrees.",
            "Coordinates should match the Fabric point for the location id.",
            False,
            patch={"latitude": 91.0},
            expect_fields=["latitude"],
        ),
        Case(
            "location/range_longitude_out_of_bounds",
            "location",
            "longitude is below -180 degrees.",
            "Coordinates should match the Fabric point for the location id.",
            False,
            patch={"longitude": -181.0},
            expect_fields=["longitude"],
        ),
        Case(
            "baba/range_quantity_zero",
            "baba_cert",
            "quantity is zero.",
            "Both NTIA artifacts call for a quantity, and zero units is not evidence.",
            False,
            patch={"quantity": 0},
            expect_fields=["quantity"],
        ),
    ]

    # -------------------------------------------------------- cross-field
    out += [
        Case(
            "crossfield/period_end_before_start",
            "performance",
            "period_end precedes period_start.",
            "A measurement period that ends before it begins cannot be reconciled "
            "against a testing window.",
            False,
            patch={"period_start": "2026-07-12T00:00:00Z", "period_end": "2026-07-06T00:00:00Z"},
            expect_fields=["period_end"],
        ),
        Case(
            "crossfield/download_passing_exceeds_total",
            "performance",
            "More passing download tests than total download tests.",
            "NTIA forbids deleting, trimming, or excluding measurements. A passing count "
            "above the total is not a rounding artifact; it is the signature of a "
            "filtered denominator.",
            False,
            patch={"download_tests_meeting_threshold": 43},
            expect_fields=["download_tests_meeting_threshold"],
        ),
        Case(
            "crossfield/upload_passing_exceeds_total",
            "performance",
            "More passing upload tests than total upload tests.",
            "Same rule, upload side. Download and upload are counted separately.",
            False,
            patch={"upload_tests_meeting_threshold": 43},
            expect_fields=["upload_tests_meeting_threshold"],
        ),
        Case(
            "crossfield/latency_passing_exceeds_total",
            "performance",
            "More within-ceiling latency tests than total latency tests.",
            "Lost-packet tests must be recorded and counted as tests that did not meet "
            "the standard, so the total cannot be smaller than the passing subset.",
            False,
            patch={"latency_tests_at_or_below_100ms": 2521},
            expect_fields=["latency_tests_at_or_below_100ms"],
        ),
        Case(
            "crossfield/installed_without_install_date",
            "location",
            "service_status is installed but install_date is absent.",
            "A location reported as built counts toward a buildout milestone, and a "
            "milestone claim with no date cannot be substantiated on review.",
            False,
            remove=["install_date"],
            patch={"service_status": "installed"},
            expect_fields=["install_date"],
        ),
        Case(
            "crossfield/active_without_install_date",
            "location",
            "service_status is active but install_date is absent.",
            "Same rule; active implies built.",
            False,
            remove=["install_date"],
            patch={"service_status": "active"},
            expect_fields=["install_date"],
        ),
        Case(
            "crossfield/certification_path_missing_letter_fields",
            "baba_cert",
            "Domestic certification path without certification_ref or " "manufacturing_location.",
            "These are key elements of the manufacturer's BABA certification letter. "
            "Without them the component is unsubstantiated.",
            False,
            remove=["certification_ref", "manufacturing_location"],
            expect_fields=["certification_ref", "manufacturing_location"],
        ),
        Case(
            "crossfield/waiver_path_missing_tracker_fields",
            "baba_waiver",
            "Waiver path without hs_code_10 or product_identifier.",
            "These are key elements of the NTIA waiver reporting tracker.",
            False,
            remove=["hs_code_10", "product_identifier"],
            expect_fields=["hs_code_10", "product_identifier"],
        ),
        Case(
            "crossfield/both_compliance_paths_present",
            "baba_cert",
            "Domestic certification path also carrying a waiver_ref.",
            "NTIA states a certification letter is not needed for waived equipment, so a "
            "component travels exactly one path. Both set at once misstates which path a "
            "reviewer should follow.",
            False,
            patch={"waiver_ref": "BEAD-BABA-WAIVER-2024-02-23"},
            expect_fields=["waiver_ref"],
        ),
        Case(
            "crossfield/waiver_path_with_certification_ref",
            "baba_waiver",
            "Waiver path also carrying a certification_ref.",
            "Same exclusivity rule, from the other side.",
            False,
            patch={"certification_ref": "CERT-2026-0417-A"},
            expect_fields=["certification_ref"],
        ),
    ]

    # ------------------------------------------------- raw test observations
    out += [
        Case(
            "test/valid_speed",
            "test_speed",
            "A successful download observation.",
            "Baseline for a speed observation. Bytes and duration are carried rather than "
            "a precomputed throughput, so the figure is reproducible by whoever reads it.",
            True,
        ),
        Case(
            "test/valid_latency",
            "test_latency",
            "A successful latency observation.",
            "Baseline for a latency observation.",
            True,
        ),
        Case(
            "test/valid_lost_packets",
            "test_latency",
            "A latency observation where every packet was lost.",
            "NTIA requires lost-packet tests to be recorded and forbids discarding them; "
            "they count as discrete tests that do not meet the standard. So this must "
            "validate. Rejecting it would push implementers toward dropping exactly the "
            "measurements the rule exists to protect.",
            True,
            patch={"packets_received": 0},
        ),
        Case(
            "test/valid_deferred_for_crosstalk",
            "test_speed",
            "A speed test deferred because consumer load exceeded the threshold.",
            "NTIA permits deferring a test when consumer traffic exceeds 10 percent of the "
            "committed speed in the relevant direction, and permits reporting that no test "
            "completed for that hour. The attempt is still recorded; a test that did not "
            "run is not the same as a test that never existed.",
            True,
            remove=["ended_at", "bytes_transferred", "ip_target"],
            patch={"test_status": "not_run_crosstalk"},
        ),
        Case(
            "test/success_speed_without_bytes",
            "test_speed",
            "A successful speed test with no bytes_transferred.",
            "Without bytes there is no measurement, only an assertion that one happened.",
            False,
            remove=["bytes_transferred"],
            expect_fields=["bytes_transferred"],
        ),
        Case(
            "test/success_speed_without_end",
            "test_speed",
            "A successful speed test with no ended_at.",
            "Duration is what converts transferred bytes into a throughput figure.",
            False,
            remove=["ended_at"],
            expect_fields=["ended_at"],
        ),
        Case(
            "test/success_latency_without_rtt",
            "test_latency",
            "A successful latency test with no round-trip time.",
            "The measurement the test exists to take.",
            False,
            remove=["latency_ms_rtt"],
            expect_fields=["latency_ms_rtt"],
        ),
        Case(
            "test/success_latency_without_packet_counts",
            "test_latency",
            "A successful latency test with no packet counts.",
            "Packet counts are what make loss visible; without them a fully lost test is "
            "indistinguishable from a clean one.",
            False,
            remove=["packets_sent", "packets_received"],
            expect_fields=["packets_sent", "packets_received"],
        ),
        Case(
            "test/not_run_but_carries_a_result",
            "test_speed",
            "A test marked not run that still reports bytes transferred.",
            "A test that did not run cannot have produced a measurement. This is the shape "
            "a fabricated or mis-stitched record takes.",
            False,
            patch={"test_status": "not_run_other"},
            expect_fields=["bytes_transferred"],
        ),
        Case(
            "test/packets_received_exceeds_sent",
            "test_latency",
            "More packets received than were sent.",
            "Arithmetically impossible.",
            False,
            patch={"packets_received": 4},
            expect_fields=["packets_received"],
        ),
        Case(
            "test/speed_test_shorter_than_15_seconds",
            "test_speed",
            "A successful speed test spanning 5 seconds.",
            "NTIA sets a minimum speed-test duration of 15 seconds. A shorter measurement "
            "is not a compliant test, and accepting it silently would let a non-compliant "
            "methodology produce results that look valid.",
            False,
            patch={"ended_at": "2026-07-06T19:03:06.123-07:00"},
            expect_fields=["ended_at"],
        ),
        Case(
            "test/end_before_start",
            "test_speed",
            "ended_at precedes started_at.",
            "A negative duration is not a measurement.",
            False,
            patch={"ended_at": "2026-07-06T19:02:00.000-07:00"},
            expect_fields=["ended_at"],
        ),
        Case(
            "test/enum_test_type_invalid",
            "test_speed",
            "test_type is not one of download, upload, or latency.",
            "Download and upload are separate types because NTIA counts the two directions "
            "separately and each must independently satisfy the standard.",
            False,
            patch={"test_type": "throughput"},
            expect_fields=["test_type"],
        ),
        Case(
            "test/enum_test_status_invalid",
            "test_speed",
            "test_status is outside the status vocabulary.",
            "Status values map onto the USAC template's numeric status codes.",
            False,
            patch={"test_status": "failed"},
            expect_fields=["test_status"],
        ),
        Case(
            "test/missing_started_at",
            "test_speed",
            "started_at is absent.",
            "Without a start time the observation cannot be placed in a testing window.",
            False,
            remove=["started_at"],
            expect_fields=["started_at"],
        ),
        Case(
            "test/pattern_test_id_not_uuid4",
            "test_speed",
            "test_id is not a UUID v4.",
            "The id is assigned where the test runs, so that a retry after a network "
            "failure stays distinguishable from a genuinely duplicated test.",
            False,
            patch={"test_id": "test-1"},
            expect_fields=["test_id"],
        ),
    ]

    # ------------------------------------------------------------- strictness
    for base, label in (
        ("performance", "performance"),
        ("location", "location"),
        ("baba_cert", "baba"),
        ("test_speed", "test"),
    ):
        out.append(
            Case(
                f"strict/{label}_unknown_field",
                base,
                "An unknown field is present.",
                "additionalProperties is false. A shared format cannot quietly carry private "
                "extensions, or two parties will disagree about what a record means.",
                False,
                patch={"vendor_extension": "anything"},
                expect_fields=["vendor_extension"],
            )
        )
        out.append(
            Case(
                f"strict/{label}_wrong_schema_version",
                base,
                "schema_version does not match this schema version.",
                "Records declare the version they conform to so a consumer can refuse data "
                "it does not understand rather than misread it.",
                False,
                patch={"schema_version": "0.2.0"},
                expect_fields=["schema_version"],
            )
        )

    return out


def build() -> dict[str, str]:
    """Render every case file plus the manifest, as path -> text."""
    all_cases = cases()

    names = [c.name for c in all_cases]
    assert len(names) == len(set(names)), "duplicate conformance case names"

    files: dict[str, str] = {}
    for case in all_cases:
        files[f"cases/{case.name}.json"] = (
            json.dumps(case.to_json(), indent=2, ensure_ascii=False) + "\n"
        )

    manifest = {
        "conformance_suite_version": SUITE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "description": (
            "Language-agnostic conformance vectors for the BEAD compliance data schemas. "
            "Each case states an instance, whether it must validate, and which fields a "
            "conforming implementation should blame when it does not."
        ),
        "case_count": len(all_cases),
        "valid_count": sum(1 for c in all_cases if c.valid),
        "invalid_count": sum(1 for c in all_cases if not c.valid),
        "cases": [
            {
                "name": c.name,
                "path": f"cases/{c.name}.json",
                "schema": SCHEMA_OF[c.base],
                "valid": c.valid,
                "description": c.description,
            }
            for c in all_cases
        ],
    }
    files["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    return files


def write(files: dict[str, str]) -> None:
    if CASES.exists():
        shutil.rmtree(CASES)
    OUT.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Exit non-zero if the suite is out of date."
    )
    args = parser.parse_args()

    files = build()

    if args.check:
        stale = []
        for rel, text in files.items():
            path = OUT / rel
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(rel)
        existing = {str(p.relative_to(OUT)) for p in OUT.rglob("*.json")}
        orphans = sorted(existing - set(files))
        if stale or orphans:
            print(
                f"conformance suite is out of date: {len(stale)} changed, "
                f"{len(orphans)} orphaned; run python tools/gen_conformance.py"
            )
            return 1
        print(f"conformance suite is up to date ({len(files) - 1} cases)")
        return 0

    write(files)
    manifest = json.loads(files["manifest.json"])
    print(
        f"wrote {manifest['case_count']} cases "
        f"({manifest['valid_count']} valid, {manifest['invalid_count']} invalid) "
        f"+ manifest.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
