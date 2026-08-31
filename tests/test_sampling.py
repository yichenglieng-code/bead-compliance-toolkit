"""Boundary tests for the NTIA section 3.2 sample-size rule."""

from __future__ import annotations

import pytest

from bead_data.sampling import required_sample_size


@pytest.mark.parametrize(
    ("population", "required"),
    [
        (0, 0),
        (1, 1),
        (5, 5),
        (6, 5),
        (50, 5),
        (51, 6),
        (99, 10),
        (100, 10),
        (499, 50),
        (500, 50),
        (501, 50),
        (10_000, 50),
    ],
)
def test_required_sample_size_boundaries(population: int, required: int) -> None:
    assert required_sample_size(population) == required


@pytest.mark.parametrize("population", [-1, -100])
def test_required_sample_size_rejects_negative_population(population: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        required_sample_size(population)


@pytest.mark.parametrize("population", [True, 5.0, "5"])
def test_required_sample_size_requires_an_integer(population) -> None:
    with pytest.raises(TypeError, match="integer"):
        required_sample_size(population)
