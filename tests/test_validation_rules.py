"""Per-schema validation behavior: golden files pass, and each rule bites.

The test matrix per schema is one valid golden file, plus a missing required
field, a bad enum value, and a cross-field rule violation.
"""

from __future__ import annotations

import pytest

from bead_data.validate import validate_file, validate_records


def only_error(records: list[dict], kind: str):
    """Validate one record and return its single error, asserting there is one."""
    report = validate_records(records, kind)
    assert report.invalid_count == 1, f"expected 1 invalid record, got {report.summary()}"
    assert report.errors, "expected at least one error"
    return report.errors[0]


# ---------------------------------------------------------------- golden files


@pytest.mark.parametrize(
    ("filename", "kind", "expected_records"),
    [
        ("performance_valid.json", "performance", 2),
        ("performance_valid.csv", "performance", 2),
        ("location_valid.json", "location", 2),
        ("baba_valid.json", "baba", 2),
    ],
)
def test_golden_file_passes(data_dir, filename, kind, expected_records) -> None:
    report = validate_file(data_dir / filename)
    assert report.kind == kind
    assert report.total == expected_records
    assert report.ok, [e.format() for e in report.errors]
    assert report.summary() == f"{expected_records} valid, 0 invalid"


# ------------------------------------------------------------- performance


def test_performance_missing_required_field(performance_record, without) -> None:
    err = only_error([without(performance_record, "uptime_pct")], "performance")
    assert err.field_path == "uptime_pct"
    assert "required" in err.message


def test_performance_bad_enum_value(performance_record) -> None:
    """'speedtest' is intuitive but not an NTIA-recognized active measurement."""
    err = only_error([{**performance_record, "measurement_method": "speedtest"}], "performance")
    assert err.field_path == "measurement_method"
    assert "is not one of" in err.message


def test_performance_bad_technology_code(performance_record) -> None:
    err = only_error([{**performance_record, "technology_code": 99}], "performance")
    assert err.field_path == "technology_code"


def test_performance_cross_field_period_order(performance_record) -> None:
    record = {
        **performance_record,
        "period_start": "2026-07-12T00:00:00Z",
        "period_end": "2026-07-06T00:00:00Z",
    }
    err = only_error([record], "performance")
    assert err.field_path == "period_end"
    assert "at or after" in err.message


@pytest.mark.parametrize(
    ("subset_field", "total_field"),
    [
        ("download_tests_meeting_threshold", "download_tests_total"),
        ("upload_tests_meeting_threshold", "upload_tests_total"),
        ("latency_tests_at_or_below_100ms", "latency_tests_total"),
    ],
)
def test_performance_cross_field_test_counts(performance_record, subset_field, total_field) -> None:
    """A passing count above the total means the denominator was filtered."""
    record = {**performance_record, subset_field: performance_record[total_field] + 1}
    err = only_error([record], "performance")
    assert err.field_path == subset_field
    assert "must not exceed" in err.message


def test_performance_committed_tier_floor(performance_record) -> None:
    """NTIA sets the committed speed tier floor at 100/20; below that is invalid."""
    err = only_error([{**performance_record, "committed_down_mbps": 50}], "performance")
    assert err.field_path == "committed_down_mbps"


def test_performance_rejects_unknown_field(performance_record) -> None:
    """additionalProperties=false keeps private extensions out of a shared format."""
    err = only_error([{**performance_record, "vendor_secret_sauce": 1}], "performance")
    assert "vendor_secret_sauce" in err.message


def test_performance_requires_provenance_completeness(performance_record) -> None:
    record = {**performance_record, "provenance": {"source_org": "Example Rural ISP"}}
    report = validate_records([record], "performance")
    paths = {e.field_path for e in report.errors}
    assert paths == {"provenance.collected_by", "provenance.collected_at"}


# ---------------------------------------------------------------- location


def test_location_missing_required_field(location_record, without) -> None:
    err = only_error([without(location_record, "latitude")], "location")
    assert err.field_path == "latitude"
    assert "required" in err.message


def test_location_bad_enum_value(location_record) -> None:
    err = only_error([{**location_record, "service_status": "in_progress"}], "location")
    assert err.field_path == "service_status"
    assert "is not one of" in err.message


@pytest.mark.parametrize("status", ["installed", "active"])
def test_location_cross_field_install_date_required(location_record, without, status) -> None:
    """A location reported as built needs a date to substantiate the milestone."""
    record = {**without(location_record, "install_date"), "service_status": status}
    err = only_error([record], "location")
    assert err.field_path == "install_date"
    assert "required" in err.message


@pytest.mark.parametrize("status", ["planned", "under_construction"])
def test_location_install_date_optional_before_build(location_record, without, status) -> None:
    record = {**without(location_record, "install_date"), "service_status": status}
    assert validate_records([record], "location").ok


def test_location_coordinate_bounds(location_record) -> None:
    err = only_error([{**location_record, "latitude": 91.0}], "location")
    assert err.field_path == "latitude"


# -------------------------------------------------------------------- baba


def test_baba_missing_required_field(baba_cert_record, without) -> None:
    err = only_error([without(baba_cert_record, "manufacturer_name")], "baba")
    assert err.field_path == "manufacturer_name"
    assert "required" in err.message


def test_baba_bad_enum_value(baba_cert_record) -> None:
    err = only_error([{**baba_cert_record, "component_type": "widget"}], "baba")
    assert err.field_path == "component_type"
    assert "is not one of" in err.message


def test_baba_certification_path_requires_letter_fields(baba_cert_record, without) -> None:
    record = without(without(baba_cert_record, "certification_ref"), "manufacturing_location")
    report = validate_records([record], "baba")
    paths = {e.field_path for e in report.errors}
    assert paths == {"certification_ref", "manufacturing_location"}


def test_baba_waiver_path_requires_tracker_fields(baba_waiver_record, without) -> None:
    """The waiver reporting tracker needs HS code, SKU, and product category."""
    record = without(without(baba_waiver_record, "hs_code_10"), "product_identifier")
    report = validate_records([record], "baba")
    paths = {e.field_path for e in report.errors}
    assert paths == {"hs_code_10", "product_identifier"}


def test_baba_cross_field_paths_are_exclusive(baba_cert_record) -> None:
    """A certification letter is not needed for waived equipment, so not both."""
    err = only_error([{**baba_cert_record, "waiver_ref": "W-1"}], "baba")
    assert err.field_path == "waiver_ref"
    assert "exactly one path" in err.message


def test_baba_waiver_path_rejects_certification_ref(baba_waiver_record) -> None:
    err = only_error([{**baba_waiver_record, "certification_ref": "CERT-1"}], "baba")
    assert err.field_path == "certification_ref"
    assert "exactly one path" in err.message


def test_baba_hs_code_must_be_ten_digits(baba_waiver_record) -> None:
    err = only_error([{**baba_waiver_record, "hs_code_10": "85176200"}], "baba")
    assert err.field_path == "hs_code_10"


def test_baba_origin_country_must_be_alpha2(baba_waiver_record) -> None:
    err = only_error([{**baba_waiver_record, "origin_country": "USA"}], "baba")
    assert err.field_path == "origin_country"


def test_baba_quantity_must_be_positive(baba_cert_record) -> None:
    err = only_error([{**baba_cert_record, "quantity": 0}], "baba")
    assert err.field_path == "quantity"


# --------------------------------------------------------- shared behavior


@pytest.mark.parametrize(
    ("kind", "fixture_name"),
    [
        ("performance", "performance_record"),
        ("location", "location_record"),
        ("baba", "baba_cert_record"),
    ],
)
def test_wrong_schema_version_is_rejected(request, kind, fixture_name) -> None:
    record = {**request.getfixturevalue(fixture_name), "schema_version": "0.2.0"}
    err = only_error([record], kind)
    assert err.field_path == "schema_version"


def test_multiple_records_report_their_own_index(performance_record) -> None:
    """Errors must be attributable to a record, not just to the file."""
    records = [
        performance_record,
        {**performance_record, "uptime_pct": 101},
        performance_record,
        {**performance_record, "device_class": "satellite_dish"},
    ]
    report = validate_records(records, "performance")
    assert report.total == 4
    assert report.valid_count == 2
    assert report.invalid_indices == {2, 4}
