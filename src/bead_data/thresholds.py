"""The federal thresholds, in one place, with nothing else in here.

Every number in this module is a published NTIA, FCC, or USAC requirement rather
than a choice this project made. Each is cited in ``docs/sources.md``. If a federal
threshold changes, this file and that document are the only places to edit.

This module deliberately has **no imports from the rest of the package**. It used to
live in ``report.py``, which meant ``aggregate.py`` imported ``report.py`` for the
constants while ``report.py`` imported ``aggregate.py`` to roll up raw
observations — a circular dependency held together by a late import inside a
function. Both now depend on this instead, and neither depends on the other.

Keeping it dependency-free is the point. Anything that needs to know a threshold can
import this without pulling in file loading, aggregation, or rendering.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Speed
# --------------------------------------------------------------------------

#: Fraction of speed measurements that must clear the bar.
#:
#: NTIA: 80 percent of download measurements must be at or above 80 percent of the
#: required download speed, and separately the same for upload. The two directions
#: are counted independently and each must satisfy the standard on its own.
SPEED_MEASUREMENT_FRACTION = 0.80

#: Fraction of the required speed each individual measurement must reach.
#:
#: Combined with the above this is the "80/80" rule. For a 100/20 Mbps commitment
#: the working bars are 80 Mbps down and 16 Mbps up.
SPEED_OF_REQUIRED_FRACTION = 0.80

# --------------------------------------------------------------------------
# Latency
# --------------------------------------------------------------------------

#: Fraction of latency measurements that must be at or below the ceiling.
#:
#: NTIA: 95 percent or more of round-trip latency tests. Lost-packet tests count as
#: discrete tests that do not meet the standard and may not be discarded, so they
#: belong in the denominator.
LATENCY_FRACTION = 0.95

#: Round-trip latency ceiling, in milliseconds, measured to a server at or reached
#: through an FCC-designated internet exchange point.
LATENCY_MS_CEILING = 100

# --------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------

#: Average outage ceiling, in hours per 365 days.
#:
#: NTIA: outages should not exceed, on average, 48 hours over any 365-day period,
#: excluding published maintenance windows, announced scheduled maintenance,
#: subscriber power failures, subscriber equipment disconnection, and periods covered
#: by an FCC DIRS activation or a FEMA declared disaster.
OUTAGE_HOURS_CEILING = 48

#: Annual uptime corresponding to the outage ceiling, as stated by NTIA.
#:
#: Used only as a fallback when a submitter reports uptime but not outage hours.
#: Outage hours is the quantity actually evaluated.
UPTIME_PCT_FLOOR = 99.45

# --------------------------------------------------------------------------
# Service standards
# --------------------------------------------------------------------------

#: Minimum committed speeds for a broadband serviceable location, in Mbps.
#:
#: NTIA defines the committed speed tier as not less than 100 Mbps down and 20 Mbps
#: up. Required speed is the greater of this floor and the subgrantee's commitment.
BSL_FLOOR_DOWN_MBPS = 100
BSL_FLOOR_UP_MBPS = 20

#: Service standard for a community anchor institution, in Mbps.
#:
#: NTIA: 1 Gbps symmetric, an order of magnitude above the BSL standard. A CAI in a
#: sample set raises the bar the whole set is judged against.
CAI_FLOOR_DOWN_MBPS = 1000
CAI_FLOOR_UP_MBPS = 1000

# --------------------------------------------------------------------------
# Test conduct
# --------------------------------------------------------------------------

#: Minimum duration of a single speed test, in seconds.
MIN_SPEED_TEST_SECONDS = 15

#: Local-time window during which testing must be conducted, as [start, end) hours.
#:
#: NTIA: between 6:00 pm and midnight local time, including weekends. Advisory in
#: this codebase rather than a schema rule, because a record carries a UTC offset
#: rather than a timezone, so the offset is a good proxy for local time and not a
#: guarantee of it.
TESTING_HOUR_START = 18
TESTING_HOUR_END = 24

#: Consumer cross-traffic threshold, as a fraction of the committed speed in the
#: direction under test, above which a speed test may be deferred.
CROSSTALK_FRACTION = 0.10

# --------------------------------------------------------------------------
# Sample size
# --------------------------------------------------------------------------

#: Populations at or below this size test every active subscriber.
SAMPLE_ALL_SUBSCRIBERS_MAX = 5

#: Populations from 6 through this size test five locations.
SAMPLE_FIXED_FIVE_POPULATION_MAX = 50

#: Populations from 51 through this size test at least ten percent.
SAMPLE_PERCENT_POPULATION_MAX = 500

#: Minimum fraction tested in the 51-through-500 population band.
SAMPLE_PERCENT_FRACTION = 0.10

#: Fixed sample size when the population exceeds 500 active subscribers.
SAMPLE_LARGE_REQUIRED_LOCATIONS = 50

# --------------------------------------------------------------------------
# Verdict vocabulary
# --------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"

#: Distinct from FAIL on purpose. Absent evidence is not failing evidence, and
#: reporting it as a pass would make this tooling worse than useless to anyone
#: relying on it.
NO_DATA = "NO DATA"
