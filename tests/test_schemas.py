"""The normative schemas must stay well-formed and mutually consistent.

These guard the contract itself, independent of any data. If the JSON Schemas and
the pydantic models drift apart, the claim that the schemas are normative and the
models are a binding stops being true.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from bead_data.models import MODELS
from bead_data.schemas import (
    FACT_KINDS,
    SCHEMA_VERSION,
    load_provenance_schema,
    load_schema,
    schemas_root,
    validator_for,
)

DRAFT_URI = "https://json-schema.org/draft/2020-12/schema"

ALL_KINDS = sorted(FACT_KINDS)


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_schema_is_valid_draft_2020_12(kind: str) -> None:
    Draft202012Validator.check_schema(load_schema(kind))


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_schema_declares_draft_and_id(kind: str) -> None:
    schema = load_schema(kind)
    assert schema["$schema"] == DRAFT_URI
    assert schema["$id"].startswith("https://")
    assert schema["$id"].endswith(FACT_KINDS[kind].schema_relpath)


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_schema_pins_version_and_requires_provenance(kind: str) -> None:
    schema = load_schema(kind)
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert "schema_version" in schema["required"]
    assert "provenance" in schema["required"]
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_every_property_is_documented(kind: str) -> None:
    """A field with no description cannot be adopted by anyone else."""
    undocumented = [
        name
        for name, sub in load_schema(kind)["properties"].items()
        if name != "provenance" and not sub.get("description")
    ]
    assert undocumented == [], f"{kind}: undocumented fields {undocumented}"


def test_provenance_schema_is_valid_and_documented() -> None:
    provenance = load_provenance_schema()
    Draft202012Validator.check_schema(provenance)
    assert provenance["$schema"] == DRAFT_URI
    assert set(provenance["required"]) == {"source_org", "collected_by", "collected_at"}
    assert all(sub.get("description") for sub in provenance["properties"].values())


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_provenance_ref_resolves_offline(kind: str) -> None:
    """Validation must never need the network to resolve the provenance $ref."""
    validator = validator_for(kind)
    errors = list(validator.iter_errors({"provenance": {"source_org": "x"}}))
    messages = " ".join(e.message for e in errors)
    assert "collected_by" in messages, "provenance sub-schema did not take effect"


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_model_fields_match_schema_properties(kind: str) -> None:
    """The pydantic binding must cover exactly the normative fields."""
    schema_fields = set(load_schema(kind)["properties"])
    model_fields = set(MODELS[kind].model_fields)
    assert model_fields == schema_fields, (
        f"{kind}: binding drift. "
        f"only in schema={sorted(schema_fields - model_fields)}, "
        f"only in model={sorted(model_fields - schema_fields)}"
    )


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_model_required_matches_schema_required(kind: str) -> None:
    """Unconditionally required fields must agree between schema and model."""
    schema = load_schema(kind)
    schema_required = set(schema["required"])
    model_required = {name for name, f in MODELS[kind].model_fields.items() if f.is_required()}
    assert model_required == schema_required, (
        f"{kind}: required drift. "
        f"only in schema={sorted(schema_required - model_required)}, "
        f"only in model={sorted(model_required - schema_required)}"
    )


def test_schema_files_are_formatted_json() -> None:
    """Schemas are read by humans; keep them parseable and newline-terminated."""
    for path in sorted(schemas_root().rglob("*.schema.json")):
        raw = path.read_text(encoding="utf-8")
        assert raw.endswith("\n"), f"{path} must end with a newline"
        json.loads(raw)


def test_signature_fields_are_required_and_unique() -> None:
    """Autodetection depends on signature fields being required and distinctive."""
    for kind, spec in FACT_KINDS.items():
        required = set(load_schema(kind)["required"])
        assert spec.signature_fields <= required, (
            f"{kind}: signature fields must all be required, "
            f"else detection fails on valid records"
        )

    for kind, spec in FACT_KINDS.items():
        for other, other_spec in FACT_KINDS.items():
            if kind >= other:
                continue
            overlap = spec.signature_fields & other_spec.signature_fields
            assert not overlap, f"{kind} and {other} share signature fields {overlap}"


def test_schema_reference_doc_is_current() -> None:
    """docs/schema_reference.md is generated; a stale copy misleads adopters.

    Worse than no reference doc is one that disagrees with the schemas, because
    someone will build against it. Regenerate with:
        python tools/gen_schema_reference.py
    """
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo / "tools" / "gen_schema_reference.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=repo,
    )
    assert result.returncode == 0, result.stdout + result.stderr
