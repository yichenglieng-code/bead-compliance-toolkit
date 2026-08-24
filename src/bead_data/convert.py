"""Normalizing evidence between JSON, CSV, and Parquet.

The point of a shared format is that the same facts survive a change of container.
So conversion is deliberately lossless in both directions: the nested
``provenance`` object flattens to ``provenance.``-prefixed columns on the way out
and nests again on the way in, declared types are restored rather than left as
text, and fields that were absent stay absent instead of becoming empty strings.

Conversion always validates first. Emitting evidence that would be rejected
downstream is worse than refusing to emit it, because the rejection then surfaces
at a state broadband office instead of on the submitter's own machine.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from bead_data.schemas import load_provenance_schema, load_schema

PROVENANCE_PREFIX = "provenance."

FORMATS = ("json", "csv", "parquet")

# Formats that can be written to stdout. Parquet is binary and seek-dependent, so
# it needs a real file.
STDOUT_FORMATS = ("json", "csv")


class ConversionError(Exception):
    """Raised when output cannot be produced."""


def _declared_type(subschema: dict) -> str | None:
    """Return the JSON Schema type a property declares, if it declares one."""
    t = subschema.get("type")
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        concrete = [x for x in t if x != "null"]
        return concrete[0] if concrete else None
    if "const" in subschema:
        return "string" if isinstance(subschema["const"], str) else None
    if "enum" in subschema:
        vals = subschema["enum"]
        if vals and all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
            return "integer"
        return "string"
    return None


def column_order(kind: str) -> list[str]:
    """Full column order for ``kind``, with provenance expanded in place.

    Schema declaration order is used rather than alphabetical order, so a human
    reading a converted CSV sees identity, then location, then measurements, then
    provenance, which is the order the schema documents them in.
    """
    columns: list[str] = []
    for name in load_schema(kind)["properties"]:
        if name == "provenance":
            columns.extend(
                f"{PROVENANCE_PREFIX}{pname}" for pname in load_provenance_schema()["properties"]
            )
        else:
            columns.append(name)
    return columns


def flatten_record(record: dict) -> dict[str, Any]:
    """Flatten one record, prefixing provenance keys."""
    flat: dict[str, Any] = {}
    for key, value in record.items():
        if key == "provenance" and isinstance(value, dict):
            for pkey, pvalue in value.items():
                flat[f"{PROVENANCE_PREFIX}{pkey}"] = pvalue
        else:
            flat[key] = value
    return flat


def _present_columns(records: list[dict], kind: str) -> list[str]:
    """Columns actually used by these records, in schema order.

    Emitting every column the schema allows would bury real data under columns
    nobody filled in. Emitting only what is present keeps output readable and
    still round-trips, because an absent column and an empty cell both mean
    "not provided".
    """
    present: set[str] = set()
    for record in records:
        present.update(flatten_record(record))

    ordered = [c for c in column_order(kind) if c in present]
    # Anything unexpected is appended rather than dropped, so conversion never
    # silently loses a field. Schema validation is what rejects unknown fields.
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def _csv_cell(value: Any) -> str:
    """Render one value for a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def to_csv(records: list[dict], kind: str) -> str:
    """Render records as CSV text."""
    columns = _present_columns(records, kind)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for record in records:
        flat = flatten_record(record)
        writer.writerow([_csv_cell(flat.get(column)) for column in columns])
    return buffer.getvalue()


def to_json(records: list[dict]) -> str:
    """Render records as pretty-printed JSON text.

    Always an array, even for a single record, so consumers need one code path.
    """
    return json.dumps(records, indent=2, ensure_ascii=False) + "\n"


def _arrow_schema(records: list[dict], kind: str):
    """Build an explicit Arrow schema from the JSON Schema declarations.

    Letting pandas infer dtypes would turn an integer column into a float the
    moment one value is missing, so ``download_tests_total`` could come back out
    of Parquet as 42.0. Declaring the types keeps a count a count.
    """
    import pyarrow as pa

    arrow_by_json = {
        "string": pa.string(),
        "number": pa.float64(),
        "integer": pa.int64(),
        "boolean": pa.bool_(),
    }

    schema_props = load_schema(kind)["properties"]
    provenance_props = load_provenance_schema()["properties"]

    fields = []
    for column in _present_columns(records, kind):
        if column.startswith(PROVENANCE_PREFIX):
            sub = provenance_props.get(column[len(PROVENANCE_PREFIX) :], {})
        else:
            sub = schema_props.get(column, {})
        arrow_type = arrow_by_json.get(_declared_type(sub) or "string", pa.string())
        fields.append(pa.field(column, arrow_type, nullable=True))

    return pa.schema(fields)


def to_parquet(records: list[dict], kind: str, target: Path) -> None:
    """Write records to a Parquet file at ``target``."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = _arrow_schema(records, kind)
    flat = [flatten_record(r) for r in records]
    columns = {field.name: [row.get(field.name) for row in flat] for field in schema}

    table = pa.Table.from_pydict(columns, schema=schema)
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target)


def read_parquet(path: Path) -> list[dict]:
    """Read a Parquet file back into nested records.

    Mirrors :func:`to_parquet`: provenance columns re-nest and nulls are dropped,
    so a record that went in without an optional field comes back without it.
    """
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    records: list[dict] = []

    for row in table.to_pylist():
        record: dict[str, Any] = {}
        provenance: dict[str, Any] = {}
        for key, value in row.items():
            if value is None:
                continue
            if key.startswith(PROVENANCE_PREFIX):
                provenance[key[len(PROVENANCE_PREFIX) :]] = value
            else:
                record[key] = value
        if provenance:
            record["provenance"] = provenance
        records.append(record)

    return records


def render(records: list[dict], kind: str, fmt: str) -> str:
    """Render records to text in ``fmt``. Parquet is not a text format."""
    if fmt == "json":
        return to_json(records)
    if fmt == "csv":
        return to_csv(records, kind)
    if fmt == "parquet":
        raise ConversionError("parquet is binary; pass -o/--output to write it to a file")
    raise ConversionError(f"unknown format {fmt!r}; expected one of {', '.join(FORMATS)}")
