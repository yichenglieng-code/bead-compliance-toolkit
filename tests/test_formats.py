"""Input format handling and schema autodetection.

The central promise of a shared format is that the same facts mean the same thing
however they arrive. If CSV and JSON disagree, that promise is broken.
"""

from __future__ import annotations

import json

import pytest

from bead_data.validate import InputError, detect_kind, load_records, validate_file


def test_csv_and_json_yield_identical_records(data_dir) -> None:
    """Same two facts, one file each way, must parse to identical structures."""
    json_records, json_kind = load_records(data_dir / "performance_valid.json")
    csv_records, csv_kind = load_records(data_dir / "performance_valid.csv")

    assert json_kind == csv_kind == "performance"
    assert csv_records == json_records


def test_csv_and_json_yield_identical_reports(data_dir) -> None:
    json_report = validate_file(data_dir / "performance_valid.json")
    csv_report = validate_file(data_dir / "performance_valid.csv")

    assert json_report.summary() == csv_report.summary()
    assert json_report.ok and csv_report.ok


def test_csv_coerces_declared_types(data_dir) -> None:
    """CSV cells arrive as text; declared types must be restored, not left as strings."""
    records, _ = load_records(data_dir / "performance_valid.csv")
    record = records[0]

    assert isinstance(record["technology_code"], int)
    assert isinstance(record["download_mbps"], float)
    assert isinstance(record["download_tests_total"], int)
    assert record["is_cai"] is False
    assert isinstance(record["location_ref"], str)


def test_csv_nests_provenance_columns(data_dir) -> None:
    records, _ = load_records(data_dir / "performance_valid.csv")
    provenance = records[0]["provenance"]

    assert provenance["source_org"] == "Example Rural ISP"
    assert provenance["tool"] == "bead-data 0.1.0"
    assert not any(key.startswith("provenance.") for key in records[0])


def test_csv_empty_cell_omits_optional_field(tmp_path, data_dir) -> None:
    """An unfilled optional column must stay absent, not become an empty string."""
    source = (data_dir / "performance_valid.csv").read_text(encoding="utf-8")
    header, first_row = source.splitlines()[0], source.splitlines()[1]
    columns = header.split(",")
    values = first_row.split(",")
    values[columns.index("provenance.tool")] = ""
    values[columns.index("sample_set_id")] = ""

    target = tmp_path / "sparse.csv"
    target.write_text(f"{header}\n{','.join(values)}\n", encoding="utf-8")

    records, _ = load_records(target)
    assert "sample_set_id" not in records[0]
    assert "tool" not in records[0]["provenance"]
    assert validate_file(target).ok


def test_csv_rejects_non_numeric_in_numeric_column(tmp_path, data_dir) -> None:
    source = (data_dir / "performance_valid.csv").read_text(encoding="utf-8").splitlines()
    columns = source[0].split(",")
    values = source[1].split(",")
    values[columns.index("download_mbps")] = "fast"

    target = tmp_path / "bad.csv"
    target.write_text(f"{source[0]}\n{','.join(values)}\n", encoding="utf-8")

    with pytest.raises(InputError, match="expected a number"):
        load_records(target)


def test_csv_accepts_integer_written_as_float(tmp_path, data_dir) -> None:
    """Spreadsheet exports often render 71 as 71.0; that is still code 71."""
    source = (data_dir / "performance_valid.csv").read_text(encoding="utf-8").splitlines()
    columns = source[0].split(",")
    values = source[1].split(",")
    values[columns.index("technology_code")] = "71.0"

    target = tmp_path / "floaty.csv"
    target.write_text(f"{source[0]}\n{','.join(values)}\n", encoding="utf-8")

    records, _ = load_records(target)
    assert records[0]["technology_code"] == 71


def test_json_accepts_single_object(tmp_path, performance_record) -> None:
    target = tmp_path / "single.json"
    target.write_text(json.dumps(performance_record), encoding="utf-8")

    records, kind = load_records(target)
    assert kind == "performance"
    assert records == [performance_record]


# ------------------------------------------------------------- autodetection


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("performance_valid.json", "performance"),
        ("performance_valid.csv", "performance"),
        ("location_valid.json", "location"),
        ("baba_valid.json", "baba"),
    ],
)
def test_autodetect_identifies_kind(data_dir, filename, expected) -> None:
    _, kind = load_records(data_dir / filename)
    assert kind == expected


def test_explicit_schema_overrides_detection(data_dir) -> None:
    """--schema must win, so a mismatch surfaces as validation errors, not silence."""
    records, kind = load_records(data_dir / "performance_valid.json", kind="baba")
    assert kind == "baba"
    assert records


def test_detect_rejects_unrecognizable_records() -> None:
    with pytest.raises(InputError, match="no identifying fields"):
        detect_kind([{"colour": "blue", "size": 3}])


def test_detect_rejects_empty_records() -> None:
    with pytest.raises(InputError, match="no records"):
        detect_kind([])


# --------------------------------------------------------------- input errors


def test_malformed_json_raises_input_error(data_dir) -> None:
    with pytest.raises(InputError, match="invalid JSON"):
        load_records(data_dir / "malformed.json")


def test_unsupported_suffix_raises_input_error(tmp_path) -> None:
    target = tmp_path / "evidence.xlsx"
    target.write_bytes(b"not really a spreadsheet")
    with pytest.raises(InputError, match="unsupported file type"):
        load_records(target)


def test_missing_file_raises_input_error(tmp_path) -> None:
    with pytest.raises(InputError, match="not a file"):
        load_records(tmp_path / "absent.json")


def test_json_scalar_payload_raises_input_error(tmp_path) -> None:
    target = tmp_path / "scalar.json"
    target.write_text("42", encoding="utf-8")
    with pytest.raises(InputError, match="object or array"):
        load_records(target)


def test_json_array_of_scalars_raises_input_error(tmp_path) -> None:
    target = tmp_path / "scalars.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(InputError, match="only objects"):
        load_records(target)
