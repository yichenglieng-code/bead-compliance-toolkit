"""NTIA sample-size arithmetic for BEAD performance measurement.

The population is the active subscribers in one state or territory, for one
subgrantee, technology, and committed speed tier, counted across all of that
subgrantee's BEAD-funded projects. See ``docs/sources.md``, S1 section 3.2.
"""

from __future__ import annotations

import math

from bead_data.thresholds import (
    SAMPLE_ALL_SUBSCRIBERS_MAX,
    SAMPLE_FIXED_FIVE_POPULATION_MAX,
    SAMPLE_LARGE_REQUIRED_LOCATIONS,
    SAMPLE_PERCENT_FRACTION,
    SAMPLE_PERCENT_POPULATION_MAX,
)


def required_sample_size(active_subscribers: int) -> int:
    """Return the minimum locations NTIA requires for a sample population.

    ``ceil`` matters in the percentage band: 51 subscribers requires 6 tested
    locations, because 5 would be less than 10 percent.
    """
    if isinstance(active_subscribers, bool) or not isinstance(active_subscribers, int):
        raise TypeError("active_subscribers must be an integer")
    if active_subscribers < 0:
        raise ValueError("active_subscribers must be non-negative")
    if active_subscribers <= SAMPLE_ALL_SUBSCRIBERS_MAX:
        return active_subscribers
    if active_subscribers <= SAMPLE_FIXED_FIVE_POPULATION_MAX:
        return SAMPLE_ALL_SUBSCRIBERS_MAX
    if active_subscribers <= SAMPLE_PERCENT_POPULATION_MAX:
        return math.ceil(active_subscribers * SAMPLE_PERCENT_FRACTION)
    return SAMPLE_LARGE_REQUIRED_LOCATIONS
