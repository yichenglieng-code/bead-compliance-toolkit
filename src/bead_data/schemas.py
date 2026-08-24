"""Locating and loading the normative JSON Schema files.

The JSON Schemas under ``schemas/`` are normative; the pydantic models in
``models.py`` are a reference binding to them. Anything that disagrees between
the two is a bug in the binding, not in the schema.

Schemas resolve from one of two places, checked in order:

1. ``bead_data/_schemas/`` inside an installed wheel, where the build copies them.
2. ``schemas/`` at the repository root, which is what a development checkout uses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SCHEMA_VERSION = "0.1.0"

_PROVENANCE_ID = (
    "https://raw.githubusercontent.com/yichenglieng-code/bead-compliance-toolkit"
    "/main/schemas/common/v0/provenance.schema.json"
)


@dataclass(frozen=True)
class FactKind:
    """One fact family: its CLI name, schema path, and identifying fields."""

    name: str
    """Short name used on the command line, e.g. ``performance``."""

    schema_relpath: str
    """Path to the normative schema, relative to the schemas root."""

    title: str
    """Human-readable title."""

    signature_fields: frozenset[str]
    """Fields that, taken together, identify this kind during autodetection.

    These are required fields unique to this kind among the three, so their
    presence is a reliable signal when ``--schema`` was not supplied.
    """


FACT_KINDS: dict[str, FactKind] = {
    "performance": FactKind(
        name="performance",
        schema_relpath="performance/v0/performance_fact.schema.json",
        title="Performance Fact",
        signature_fields=frozenset({"download_mbps", "upload_mbps", "uptime_pct"}),
    ),
    "location": FactKind(
        name="location",
        schema_relpath="location/v0/deployment_location.schema.json",
        title="Deployment Location",
        signature_fields=frozenset({"location_id", "service_status", "latitude"}),
    ),
    "baba": FactKind(
        name="baba",
        schema_relpath="baba/v0/baba_evidence.schema.json",
        title="BABA Evidence",
        signature_fields=frozenset({"evidence_id", "compliance_path", "component"}),
    ),
}


class SchemaNotFoundError(RuntimeError):
    """Raised when the schemas directory cannot be located on disk."""


@lru_cache(maxsize=1)
def schemas_root() -> Path:
    """Return the directory holding the normative schema tree."""
    packaged = Path(__file__).resolve().parent / "_schemas"
    if (packaged / "performance/v0/performance_fact.schema.json").is_file():
        return packaged

    # Development checkout: src/bead_data/schemas.py -> repo root -> schemas/
    repo = Path(__file__).resolve().parents[2] / "schemas"
    if (repo / "performance/v0/performance_fact.schema.json").is_file():
        return repo

    raise SchemaNotFoundError(
        "Could not locate the schemas directory. Expected either "
        f"{packaged} (installed) or {repo} (development checkout)."
    )


@lru_cache(maxsize=8)
def load_schema(kind: str) -> dict:
    """Load the normative JSON Schema for ``kind``.

    Args:
        kind: One of the keys of :data:`FACT_KINDS`.

    Raises:
        KeyError: If ``kind`` is not a known fact family.
    """
    if kind not in FACT_KINDS:
        known = ", ".join(sorted(FACT_KINDS))
        raise KeyError(f"Unknown schema kind {kind!r}. Known kinds: {known}")
    path = schemas_root() / FACT_KINDS[kind].schema_relpath
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_provenance_schema() -> dict:
    """Load the shared provenance sub-schema."""
    with (schemas_root() / "common/v0/provenance.schema.json").open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=8)
def validator_for(kind: str):
    """Build a JSON Schema validator for ``kind``.

    The provenance schema is registered locally so that validation never reaches
    out to the network to resolve its ``$ref``. Format checking is enabled, which
    is what makes ``date-time``, ``date``, and ``uri`` constraints actually bite.
    """
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    provenance = Resource.from_contents(load_provenance_schema())
    registry = Registry().with_resource(uri=_PROVENANCE_ID, resource=provenance)

    schema = load_schema(kind)
    return Draft202012Validator(
        schema,
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
