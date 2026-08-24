"""Loading, validating, and reporting on compliance evidence files.

Validation runs in two passes, because they catch different classes of problem
and both messages are worth having:

1. JSON Schema, which is the normative contract. Catches wrong types, unknown
   fields, bad enum values, failed patterns, out-of-range numbers.
2. The pydantic models, which carry the cross-field rules that decide whether a
   record is internally coherent.

Errors are reported per record with a field path, so a submitter can fix data
without reading the schema.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bead_data.models import MODELS
from bead_data.schemas import FACT_KINDS, load_schema, validator_for


class InputError(Exception):
    """Raised for unreadable input: bad path, unsupported suffix, malformed file.

    Distinct from a validation failure. A validation failure means the data is
    wrong; an InputError means the data could not be examined at all.
    """


@dataclass(frozen=True)
class RecordError:
    """One validation failure against one record."""

    record_index: int
    field_path: str
    message: str

    def format(self) -> str:
        """Render as ``record <n>: <field>: <message>``."""
        return f"record {self.record_index}: {self.field_path}: {self.message}"


@dataclass
class ValidationReport:
    """Outcome of validating one file."""

    kind: str
    path: Path
    total: int = 0
    errors: list[RecordError] = field(default_factory=list)

    @property
    def invalid_indices(self) -> set[int]:
        """Record indices with at least one error."""
        return {e.record_index for e in self.errors}

    @property
    def invalid_count(self) -> int:
        """Number of records with at least one error."""
        return len(self.invalid_indices)

    @property
    def valid_count(self) -> int:
        """Number of records that passed both passes."""
        return self.total - self.invalid_count

    @property
    def ok(self) -> bool:
        """True when every record passed."""
        return not self.errors

    def summary(self) -> str:
        """Render the summary line."""
        return f"{self.valid_count} valid, {self.invalid_count} invalid"


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

_TRUE = {"true", "t", "yes", "y", "1"}
_FALSE = {"false", "f", "no", "n", "0"}


def _schema_type_index(schema: dict) -> dict[str, str]:
    """Map dotted field path to declared JSON Schema type.

    Used to coerce CSV cells, which arrive as strings, into the types the schema
    declares. Without this, a CSV and a JSON file holding the same records would
    not validate the same way, which would defeat the point of a shared format.
    """
    index: dict[str, str] = {}

    def declared_type(subschema: dict) -> str | None:
        t = subschema.get("type")
        if isinstance(t, str):
            return t
        if isinstance(t, list):
            # e.g. ["number", "null"] -> take the first concrete type
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

    for name, sub in schema.get("properties", {}).items():
        if name == "provenance":
            from bead_data.schemas import load_provenance_schema

            for pname, psub in load_provenance_schema().get("properties", {}).items():
                t = declared_type(psub)
                if t:
                    index[f"provenance.{pname}"] = t
            continue
        t = declared_type(sub)
        if t:
            index[name] = t

    return index


def _coerce(value: str, declared: str | None, path: str) -> Any:
    """Coerce one CSV cell into its declared JSON Schema type."""
    if declared in (None, "string"):
        return value
    if declared == "number":
        try:
            return float(value)
        except ValueError as exc:
            raise InputError(f"{path}: expected a number, got {value!r}") from exc
    if declared == "integer":
        try:
            return int(value)
        except ValueError:
            # Accept "71.0" from spreadsheet exports, reject "71.5".
            try:
                as_float = float(value)
            except ValueError as exc:
                raise InputError(f"{path}: expected an integer, got {value!r}") from exc
            if as_float.is_integer():
                return int(as_float)
            raise InputError(f"{path}: expected an integer, got {value!r}") from None
    if declared == "boolean":
        low = value.strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise InputError(f"{path}: expected a boolean, got {value!r}")
    return value


def _nest_row(row: dict[str, str], types: dict[str, str]) -> dict[str, Any]:
    """Turn one flat CSV row into a nested record.

    Columns prefixed ``provenance.`` become the nested provenance object. Empty
    cells are dropped rather than sent through as empty strings, so that an
    unfilled optional column stays absent instead of failing a ``minLength``
    check it was never meant to face.
    """
    record: dict[str, Any] = {}
    provenance: dict[str, Any] = {}

    for raw_key, raw_value in row.items():
        if raw_key is None:
            continue
        key = raw_key.strip()
        if not key:
            continue
        value = (raw_value or "").strip()
        if value == "":
            continue
        if key.startswith("provenance."):
            leaf = key[len("provenance.") :]
            provenance[leaf] = _coerce(value, types.get(key), key)
        else:
            record[key] = _coerce(value, types.get(key), key)

    if provenance:
        record["provenance"] = provenance
    return record


def load_records(path: Path, kind: str | None = None) -> tuple[list[dict], str]:
    """Load records from a ``.json``, ``.csv``, or ``.parquet`` file.

    Args:
        path: File to read.
        kind: Fact kind, or None to autodetect from the records.

    Returns:
        The records and the resolved kind.

    Raises:
        InputError: Unreadable path, unsupported suffix, malformed content, or a
            kind that could not be determined.
    """
    if not path.is_file():
        raise InputError(f"not a file: {path}")

    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            with path.open(encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            raise InputError(f"{path}: invalid JSON: {exc}") from exc
        if isinstance(payload, dict):
            records = [payload]
        elif isinstance(payload, list):
            if not all(isinstance(r, dict) for r in payload):
                raise InputError(f"{path}: JSON array must contain only objects")
            records = payload
        else:
            raise InputError(f"{path}: expected a JSON object or array of objects")
        resolved = kind or detect_kind(records, path)
        return records, resolved

    if suffix == ".parquet":
        from bead_data.convert import read_parquet

        try:
            records = read_parquet(path)
        except Exception as exc:  # pyarrow raises a variety of types
            raise InputError(f"{path}: could not read Parquet: {exc}") from exc
        resolved = kind or detect_kind(records, path)
        return records, resolved

    if suffix == ".csv":
        try:
            with path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except (OSError, csv.Error) as exc:
            raise InputError(f"{path}: could not read CSV: {exc}") from exc
        if not rows:
            return [], kind or "performance"

        # Detection needs the raw header names, before any coercion.
        header_probe = [{k.strip(): v for k, v in rows[0].items() if k}]
        resolved = kind or detect_kind(header_probe, path)

        types = _schema_type_index(load_schema(resolved))
        records = [_nest_row(row, types) for row in rows]
        return records, resolved

    raise InputError(f"{path}: unsupported file type {suffix!r}; expected .json, .csv, or .parquet")


def detect_kind(records: list[dict], path: Path | None = None) -> str:
    """Infer the fact kind from the fields present on the records.

    Raises:
        InputError: If no kind matches, or more than one matches equally well.
    """
    where = f" in {path}" if path else ""
    if not records:
        raise InputError(f"cannot detect schema{where}: no records")

    present = set(records[0])
    scores = {name: len(spec.signature_fields & present) for name, spec in FACT_KINDS.items()}
    best = max(scores.values())

    if best == 0:
        known = ", ".join(sorted(FACT_KINDS))
        raise InputError(
            f"cannot detect schema{where}: no identifying fields found. "
            f"Pass --schema with one of: {known}"
        )

    winners = [name for name, score in scores.items() if score == best]
    if len(winners) > 1:
        raise InputError(
            f"ambiguous schema{where}: fields match {', '.join(sorted(winners))} equally. "
            f"Pass --schema to disambiguate."
        )
    return winners[0]


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


_REQUIRED_PROP = re.compile(r"^'([^']+)' is a required property$")
_LEADING_IDENT = re.compile(r"^([a-z_][a-z0-9_]*)\b")


def _json_path(error) -> str:
    """Render a jsonschema error location as a dotted field path.

    ``required`` and conditional ``allOf`` failures carry an empty path, because
    the fault is with the object rather than with a field inside it. Naming the
    missing property anyway is far more actionable than reporting ``<record>``.
    """
    prefix = ".".join(str(p) for p in error.absolute_path)

    if error.validator == "required":
        match = _REQUIRED_PROP.match(error.message)
        if match:
            name = match.group(1)
            return f"{prefix}.{name}" if prefix else name

    return prefix or "<record>"


def _model_path(loc: tuple, message: str, model: type) -> str:
    """Field path for a pydantic error, falling back to the message.

    Cross-field rules live in ``model_validator(mode="after")``, which reports an
    empty location because it validated the whole object. Every such rule in
    ``models.py`` opens its message with the offending field name, so recovering
    the name from the message keeps output consistent with schema errors.
    """
    if loc:
        return ".".join(str(p) for p in loc)

    match = _LEADING_IDENT.match(message)
    if match and match.group(1) in getattr(model, "model_fields", {}):
        return match.group(1)
    return "<record>"


def validate_records(records: list[dict], kind: str, path: Path | None = None) -> ValidationReport:
    """Validate records against the JSON Schema and then the model rules.

    A record that fails the schema pass is not put through the model pass, since
    the model would mostly restate the same problem in different words.
    """
    report = ValidationReport(kind=kind, path=path or Path("<records>"), total=len(records))
    validator = validator_for(kind)
    model = MODELS[kind]

    for index, record in enumerate(records, start=1):
        schema_errors = sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
        if schema_errors:
            for err in schema_errors:
                report.errors.append(
                    RecordError(
                        record_index=index,
                        field_path=_json_path(err),
                        message=err.message,
                    )
                )
            continue

        try:
            model.model_validate(record)
        except Exception as exc:  # pydantic ValidationError
            details = exc.errors() if hasattr(exc, "errors") else None
            if not details:
                report.errors.append(
                    RecordError(record_index=index, field_path="<record>", message=str(exc))
                )
                continue
            for detail in details:
                # Pydantic prefixes messages raised from validators.
                message = detail.get("msg", str(detail)).removeprefix("Value error, ")
                report.errors.append(
                    RecordError(
                        record_index=index,
                        field_path=_model_path(detail.get("loc", ()), message, model),
                        message=message,
                    )
                )

    return report


def validate_file(path: Path, kind: str | None = None) -> ValidationReport:
    """Load and validate one file end to end."""
    records, resolved = load_records(path, kind)
    return validate_records(records, resolved, path)
