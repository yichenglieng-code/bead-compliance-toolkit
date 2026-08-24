"""Conversion must be lossless in both directions.

If a fact changes meaning when it changes container, the shared format is not
actually shared. These tests pin round-trip fidelity for CSV and Parquet.
"""

from __future__ import annotations

import json

import pytest

from bead_data.convert import (
    ConversionError,
    column_order,
    flatten_record,
    read_parquet,
    render,
    to_csv,
    to_json,
    to_parquet,
)
from bead_data.validate import load_records, validate_records


@pytest.fixture
def performance_records(data_dir):
    records, _ = load_records(data_dir / "performance_valid.json")
    return records


# ------------------------------------------------------------------ round trips


def test_json_to_csv_to_json_round_trip(tmp_path, performance_records) -> None:
    target = tmp_path / "out.csv"
    target.write_text(to_csv(performance_records, "performance"), encoding="utf-8")

    back, kind = load_records(target)
    assert kind == "performance"
    assert back == performance_records


def test_json_to_parquet_to_json_round_trip(tmp_path, performance_records) -> None:
    target = tmp_path / "out.parquet"
    to_parquet(performance_records, "performance", target)

    assert read_parquet(target) == performance_records


def test_parquet_is_loadable_and_valid(tmp_path, performance_records) -> None:
    target = tmp_path / "out.parquet"
    to_parquet(performance_records, "performance", target)

    records, kind = load_records(target)
    assert kind == "performance"
    assert validate_records(records, kind).ok


def test_parquet_preserves_integer_types(tmp_path, performance_records) -> None:
    """Inferred dtypes would turn a test count into a float; declared ones do not."""
    target = tmp_path / "out.parquet"
    to_parquet(performance_records, "performance", target)

    record = read_parquet(target)[0]
    assert isinstance(record["download_tests_total"], int)
    assert isinstance(record["technology_code"], int)
    assert isinstance(record["download_mbps"], float)
    assert record["is_cai"] is False


@pytest.mark.parametrize("kind_file", ["location_valid.json", "baba_valid.json"])
def test_round_trip_for_other_kinds(tmp_path, data_dir, kind_file) -> None:
    records, kind = load_records(data_dir / kind_file)

    csv_target = tmp_path / f"{kind}.csv"
    csv_target.write_text(to_csv(records, kind), encoding="utf-8")
    assert load_records(csv_target)[0] == records

    parquet_target = tmp_path / f"{kind}.parquet"
    to_parquet(records, kind, parquet_target)
    assert read_parquet(parquet_target) == records


def test_sparse_optional_fields_survive_round_trip(tmp_path, performance_record) -> None:
    """A record missing optional fields must not gain empty ones on the way back."""
    lean = {
        k: v
        for k, v in performance_record.items()
        if k not in {"latency_ms_loaded", "sample_set_id", "outage_hours_365d"}
    }
    lean["provenance"] = {k: v for k, v in lean["provenance"].items() if k != "tool"}

    target = tmp_path / "lean.csv"
    target.write_text(to_csv([lean], "performance"), encoding="utf-8")

    back, _ = load_records(target)
    assert back == [lean]
    assert "latency_ms_loaded" not in back[0]
    assert "tool" not in back[0]["provenance"]


# ---------------------------------------------------------------- CSV shape


def test_csv_columns_follow_schema_order(performance_records) -> None:
    header = to_csv(performance_records, "performance").splitlines()[0].split(",")
    expected = [c for c in column_order("performance") if c in header]
    assert header == expected


def test_csv_omits_columns_no_record_uses(performance_record) -> None:
    lean = {k: v for k, v in performance_record.items() if k != "latency_ms_loaded"}
    header = to_csv([lean], "performance").splitlines()[0]
    assert "latency_ms_loaded" not in header


def test_csv_renders_booleans_lowercase(performance_records) -> None:
    text = to_csv(performance_records, "performance")
    assert ",false," in text or text.rstrip().endswith("false")


def test_flatten_prefixes_provenance(performance_record) -> None:
    flat = flatten_record(performance_record)
    assert flat["provenance.source_org"] == "Example Rural ISP"
    assert "provenance" not in flat


def test_column_order_expands_provenance_in_place() -> None:
    columns = column_order("performance")
    assert columns[0] == "schema_version"
    assert "provenance.source_org" in columns
    assert "provenance" not in columns
    # Provenance sits where the schema declares it, at the end.
    assert columns.index("provenance.source_org") > columns.index("device_class")


# ---------------------------------------------------------------- JSON shape


def test_to_json_always_emits_an_array(performance_record) -> None:
    parsed = json.loads(to_json([performance_record]))
    assert isinstance(parsed, list)
    assert len(parsed) == 1


# -------------------------------------------------------------------- errors


def test_render_rejects_parquet_as_text(performance_records) -> None:
    with pytest.raises(ConversionError, match="binary"):
        render(performance_records, "performance", "parquet")


def test_render_rejects_unknown_format(performance_records) -> None:
    with pytest.raises(ConversionError, match="unknown format"):
        render(performance_records, "performance", "yaml")
