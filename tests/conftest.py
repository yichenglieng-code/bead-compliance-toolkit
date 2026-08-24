"""Shared fixtures.

Invalid cases are built by mutating a known-good record rather than by keeping a
separate broken file for every rule. That keeps the valid record as the single
source of truth: when a schema field changes, the invalid cases follow it instead
of silently drifting into passing for the wrong reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """Directory holding the golden files."""
    return DATA


def _first(name: str) -> dict:
    payload = json.loads((DATA / name).read_text(encoding="utf-8"))
    return payload[0] if isinstance(payload, list) else payload


@pytest.fixture
def performance_record() -> dict:
    """A valid performance_fact."""
    return _first("performance_valid.json")


@pytest.fixture
def location_record() -> dict:
    """A valid deployment_location with service_status 'active'."""
    return _first("location_valid.json")


@pytest.fixture
def baba_cert_record() -> dict:
    """A valid baba_evidence on the domestic_certification path."""
    return _first("baba_valid.json")


@pytest.fixture
def baba_waiver_record() -> dict:
    """A valid baba_evidence on the waiver path."""
    return json.loads((DATA / "baba_valid.json").read_text(encoding="utf-8"))[1]


@pytest.fixture
def without():
    """Return a copy of a record with one key removed."""

    def _without(record: dict, key: str) -> dict:
        assert key in record, f"fixture bug: {key!r} not present, so removing it proves nothing"
        return {k: v for k, v in record.items() if k != key}

    return _without
