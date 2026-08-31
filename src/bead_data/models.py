"""Pydantic v2 models bound to the normative JSON Schemas.

The JSON Schemas under ``schemas/`` are normative. These models are the reference
binding: they restate the same field constraints and, more importantly, carry the
cross-field rules that JSON Schema expresses awkwardly, with error messages aimed
at whoever has to fix the data.

Design note on timestamps. Date and date-time fields are kept as strings rather
than coerced into ``datetime`` objects. Coercing would silently rewrite the
caller's formatting, so a JSON to CSV to JSON round trip would no longer return
what went in. Instead the strings are parsed for validation and comparison, and
emitted unchanged.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bead_data.thresholds import MIN_SPEED_TEST_SECONDS

SCHEMA_VERSION = "0.1.0"

UUID4_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"

# FCC fixed technology codes. See docs/schema_reference.md for the full table.
TechnologyCode = Literal[0, 10, 40, 50, 60, 61, 70, 71, 72]

MeasurementMethod = Literal[
    "cwmp_tr069",
    "tr369_usp",
    "gateway_software",
    "ont_cpe_builtin",
    "dedicated_measurement_device",
    "other",
]

DeviceClass = Literal["base_node", "remote_node", "cpe", "other"]

ServiceStatus = Literal["planned", "under_construction", "installed", "active", "suspended"]

CompliancePath = Literal["domestic_certification", "waiver"]

ComponentType = Literal["device", "subassembly", "iron_steel", "construction_material", "other"]

ProductCategory = Literal[
    "router",
    "switch",
    "radio",
    "antenna",
    "power_system",
    "optical_transport",
    "cable",
    "enclosure",
    "other",
]

WaiverType = Literal[
    "public_interest",
    "nonavailability",
    "unreasonable_cost",
    "general_applicability",
    "de_minimis",
]

# Statuses at which a location is being reported as built, and therefore needs a
# build date to substantiate it.
BUILT_STATUSES: frozenset[str] = frozenset({"installed", "active"})


def _parse_datetime(value: str, field_name: str) -> datetime:
    """Parse an ISO 8601 date-time, accepting a trailing ``Z``."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid ISO 8601 date-time: {value!r}") from exc


def _parse_date(value: str, field_name: str) -> date:
    """Parse an ISO 8601 calendar date."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid ISO 8601 date: {value!r}") from exc


class Provenance(BaseModel):
    """Who produced a fact, with what, and when. Required on every fact."""

    model_config = ConfigDict(extra="forbid")

    source_org: Annotated[str, Field(min_length=1)]
    collected_by: Annotated[str, Field(min_length=1)]
    collected_at: str
    tool: Annotated[str | None, Field(min_length=1, default=None)] = None
    methodology_ref: Annotated[str | None, Field(min_length=1, default=None)] = None

    @field_validator("collected_at")
    @classmethod
    def _check_collected_at(cls, v: str) -> str:
        _parse_datetime(v, "collected_at")
        return v


class PerformanceFact(BaseModel):
    """One funded location's performance over one measurement period."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.0"]
    fact_id: Annotated[str, Field(pattern=UUID4_PATTERN)]
    location_ref: Annotated[str, Field(min_length=1)]
    state_or_territory: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    technology_code: TechnologyCode
    committed_down_mbps: Annotated[float, Field(ge=100)]
    committed_up_mbps: Annotated[float, Field(ge=20)]
    period_start: str
    period_end: str
    download_mbps: Annotated[float, Field(ge=0)]
    upload_mbps: Annotated[float, Field(ge=0)]
    latency_ms_mean: Annotated[float, Field(ge=0)]
    latency_ms_loaded: Annotated[float | None, Field(ge=0, default=None)] = None
    download_tests_total: Annotated[int | None, Field(ge=0, default=None)] = None
    download_tests_meeting_threshold: Annotated[int | None, Field(ge=0, default=None)] = None
    upload_tests_total: Annotated[int | None, Field(ge=0, default=None)] = None
    upload_tests_meeting_threshold: Annotated[int | None, Field(ge=0, default=None)] = None
    latency_tests_total: Annotated[int | None, Field(ge=0, default=None)] = None
    latency_tests_at_or_below_100ms: Annotated[int | None, Field(ge=0, default=None)] = None
    tests_not_run_total: Annotated[int | None, Field(ge=0, default=None)] = None
    uptime_pct: Annotated[float, Field(ge=0, le=100)]
    outage_hours_365d: Annotated[float | None, Field(ge=0, default=None)] = None
    measurement_method: MeasurementMethod
    device_class: DeviceClass
    sample_set_id: Annotated[str | None, Field(min_length=1, default=None)] = None
    sample_population_active_subscribers: Annotated[int | None, Field(ge=0, default=None)] = None
    is_cai: bool = False
    provenance: Provenance

    @field_validator("period_start", "period_end")
    @classmethod
    def _check_period_format(cls, v: str, info) -> str:
        _parse_datetime(v, info.field_name)
        return v

    @model_validator(mode="after")
    def _check_period_order(self) -> PerformanceFact:
        """Cross-field rule 1: the period must not end before it starts."""
        start = _parse_datetime(self.period_start, "period_start")
        end = _parse_datetime(self.period_end, "period_end")
        if end < start:
            raise ValueError(
                f"period_end ({self.period_end}) must be at or after "
                f"period_start ({self.period_start})"
            )
        return self

    @model_validator(mode="after")
    def _check_test_counts(self) -> PerformanceFact:
        """Cross-field rule 2: a subset count cannot exceed its population.

        NTIA forbids deleting, trimming, or excluding test measurements, so a
        record claiming more passing tests than total tests is not a rounding
        quirk. It means the denominator was filtered.
        """
        pairs = (
            ("download_tests_meeting_threshold", "download_tests_total"),
            ("upload_tests_meeting_threshold", "upload_tests_total"),
            ("latency_tests_at_or_below_100ms", "latency_tests_total"),
        )
        for subset_name, total_name in pairs:
            subset = getattr(self, subset_name)
            total = getattr(self, total_name)
            if subset is None or total is None:
                continue
            if subset > total:
                raise ValueError(f"{subset_name} ({subset}) must not exceed {total_name} ({total})")
        return self


class DeploymentLocation(BaseModel):
    """One BEAD-funded location and where it sits in the build lifecycle."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.0"]
    location_id: Annotated[str, Field(min_length=1)]
    state_or_territory: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    service_status: ServiceStatus
    install_date: str | None = None
    technology_code: TechnologyCode
    max_advertised_down_mbps: Annotated[float | None, Field(ge=0, default=None)] = None
    max_advertised_up_mbps: Annotated[float | None, Field(ge=0, default=None)] = None
    is_cai: bool = False
    active_subscriber_count: Annotated[int | None, Field(ge=0, default=None)] = None
    provenance: Provenance

    @field_validator("install_date")
    @classmethod
    def _check_install_date_format(cls, v: str | None) -> str | None:
        if v is not None:
            _parse_date(v, "install_date")
        return v

    @model_validator(mode="after")
    def _check_install_date_present(self) -> DeploymentLocation:
        """Cross-field rule 3: a built location needs a build date.

        A location reported as installed or active is being counted toward
        buildout milestones, and a milestone claim with no date behind it cannot
        be substantiated on review.
        """
        if self.service_status in BUILT_STATUSES and not self.install_date:
            raise ValueError(
                f"install_date is required when service_status is "
                f"{self.service_status!r} (one of {sorted(BUILT_STATUSES)})"
            )
        return self


class BabaEvidence(BaseModel):
    """BABA provenance for one component used in a BEAD-funded build."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.0"]
    evidence_id: Annotated[str, Field(pattern=UUID4_PATTERN)]
    compliance_path: CompliancePath
    component: Annotated[str, Field(min_length=1)]
    component_type: ComponentType
    component_description: Annotated[str, Field(min_length=1)]
    product_category: ProductCategory | None = None
    manufacturer_name: Annotated[str, Field(min_length=1)]
    origin_country: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    quantity: Annotated[int, Field(ge=1)]
    manufacturing_location: Annotated[str | None, Field(min_length=1, default=None)] = None
    certification_ref: Annotated[str | None, Field(min_length=1, default=None)] = None
    requirement_ref: Annotated[str | None, Field(min_length=1, default=None)] = None
    certifying_representative: Annotated[str | None, Field(min_length=1, default=None)] = None
    waiver_ref: Annotated[str | None, Field(min_length=1, default=None)] = None
    waiver_type: WaiverType | None = None
    hs_code_10: Annotated[str | None, Field(pattern=r"^[0-9]{10}$", default=None)] = None
    product_identifier: Annotated[str | None, Field(min_length=1, default=None)] = None
    bead_project_ref: Annotated[str | None, Field(min_length=1, default=None)] = None
    attestation_doc_sha256: Annotated[
        str | None, Field(pattern=r"^[0-9a-f]{64}$", default=None)
    ] = None
    attestation_doc_uri: str | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def _check_compliance_path(self) -> BabaEvidence:
        """Cross-field rule 4: each path requires the fields that path needs.

        NTIA runs two distinct compliance paths and states that a certification
        letter is not needed for waived equipment. Recording a component with
        neither a certification nor a waiver leaves it unsubstantiated; recording
        it with both misstates which path a reviewer should follow.
        """
        if self.compliance_path == "domestic_certification":
            missing = [
                name
                for name in ("certification_ref", "manufacturing_location")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    f"compliance_path 'domestic_certification' requires "
                    f"{', '.join(missing)} (from the manufacturer's BABA certification letter)"
                )
            if self.waiver_ref:
                raise ValueError(
                    "waiver_ref must not be set when compliance_path is "
                    "'domestic_certification'; a certification letter is not needed for "
                    "waived equipment, so a component follows exactly one path"
                )
        else:
            missing = [
                name
                for name in ("waiver_ref", "hs_code_10", "product_identifier", "product_category")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    f"compliance_path 'waiver' requires {', '.join(missing)} "
                    f"(from the NTIA waiver reporting tracker)"
                )
            if self.certification_ref:
                raise ValueError(
                    "certification_ref must not be set when compliance_path is 'waiver'; "
                    "a component follows exactly one path"
                )
        return self


TestType = Literal["download", "upload", "latency"]

TestStatus = Literal["success", "not_run_crosstalk", "not_run_other"]


class PerformanceTest(BaseModel):
    """One discrete speed or latency observation, as actually conducted."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.0"]
    test_id: Annotated[str, Field(pattern=UUID4_PATTERN)]
    location_ref: Annotated[str, Field(min_length=1)]
    subscriber_ref: Annotated[str | None, Field(min_length=1, default=None)] = None
    state_or_territory: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    technology_code: TechnologyCode
    committed_down_mbps: Annotated[float, Field(ge=100)]
    committed_up_mbps: Annotated[float, Field(ge=20)]
    test_type: TestType
    test_status: TestStatus
    started_at: str
    ended_at: str | None = None
    ip_target: Annotated[str | None, Field(min_length=1, default=None)] = None
    bytes_transferred: Annotated[int | None, Field(ge=0, default=None)] = None
    latency_ms_rtt: Annotated[float | None, Field(ge=0, default=None)] = None
    packets_sent: Annotated[int | None, Field(ge=0, default=None)] = None
    packets_received: Annotated[int | None, Field(ge=0, default=None)] = None
    measurement_method: MeasurementMethod | None = None
    device_class: DeviceClass | None = None
    sample_set_id: Annotated[str | None, Field(min_length=1, default=None)] = None
    sample_population_active_subscribers: Annotated[int | None, Field(ge=0, default=None)] = None
    is_cai: bool = False
    comment: Annotated[str | None, Field(min_length=1, default=None)] = None
    provenance: Provenance

    @field_validator("started_at", "ended_at")
    @classmethod
    def _check_timestamps(cls, v: str | None, info) -> str | None:
        if v is not None:
            _parse_datetime(v, info.field_name)
        return v

    @property
    def duration_seconds(self) -> float | None:
        """Observation duration, when both endpoints are present."""
        if not self.ended_at:
            return None
        start = _parse_datetime(self.started_at, "started_at")
        end = _parse_datetime(self.ended_at, "ended_at")
        return (end - start).total_seconds()

    @property
    def throughput_mbps(self) -> float | None:
        """Throughput in Mbps, derived rather than stored.

        Storing bytes and duration instead of a precomputed figure means whoever
        consumes the record can reproduce the arithmetic rather than trust it.
        """
        if self.bytes_transferred is None:
            return None
        duration = self.duration_seconds
        if not duration or duration <= 0:
            return None
        return (self.bytes_transferred * 8) / duration / 1_000_000

    @model_validator(mode="after")
    def _check_time_order(self) -> PerformanceTest:
        duration = self.duration_seconds
        if duration is not None and duration < 0:
            raise ValueError(
                f"ended_at ({self.ended_at}) must be at or after started_at ({self.started_at})"
            )
        return self

    @model_validator(mode="after")
    def _check_measurement_present(self) -> PerformanceTest:
        """A successful test must carry the measurement it claims to have taken."""
        if self.test_status != "success":
            return self

        if self.test_type in ("download", "upload"):
            missing = [
                name
                for name in ("bytes_transferred", "ended_at", "ip_target")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    f"{', '.join(missing)} is required for a successful " f"{self.test_type} test"
                )
        else:
            missing = [
                name
                for name in ("latency_ms_rtt", "packets_sent", "packets_received", "ip_target")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"{', '.join(missing)} is required for a successful latency test")
        return self

    @model_validator(mode="after")
    def _check_no_result_when_not_run(self) -> PerformanceTest:
        """A test that did not run cannot have produced a measurement."""
        if self.test_status == "success":
            return self
        present = [
            name
            for name in ("bytes_transferred", "latency_ms_rtt")
            if getattr(self, name) is not None
        ]
        if present:
            raise ValueError(
                f"{', '.join(present)} must not be set when test_status is "
                f"{self.test_status!r}; a test that did not run has no result"
            )
        return self

    @model_validator(mode="after")
    def _check_packets(self) -> PerformanceTest:
        if (
            self.packets_sent is not None
            and self.packets_received is not None
            and self.packets_received > self.packets_sent
        ):
            raise ValueError(
                f"packets_received ({self.packets_received}) must not exceed "
                f"packets_sent ({self.packets_sent})"
            )
        return self

    @model_validator(mode="after")
    def _check_speed_test_duration(self) -> PerformanceTest:
        """NTIA sets a 15 second minimum duration for a speed test.

        A shorter measurement is not a compliant test, and silently accepting one
        would let a non-compliant methodology produce results that look valid.
        """
        if self.test_status != "success" or self.test_type == "latency":
            return self
        duration = self.duration_seconds
        if duration is not None and duration < MIN_SPEED_TEST_SECONDS:
            raise ValueError(
                f"ended_at implies a {duration:g}s speed test; NTIA requires a minimum "
                f"duration of {MIN_SPEED_TEST_SECONDS} seconds"
            )
        return self


MODELS: dict[str, type[BaseModel]] = {
    "performance": PerformanceFact,
    "location": DeploymentLocation,
    "baba": BabaEvidence,
    "test": PerformanceTest,
}
