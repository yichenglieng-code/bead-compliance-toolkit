"""Milestone-report-ready summaries, including the four NTIA threshold checks.

This is where carrying test counts on ``performance_fact`` pays off. NTIA judges a
BEAD last-mile network on four thresholds, each computed over a population of
discrete tests, and a provider is non-compliant if it fails any one of them:

* download - 80% of measurements at or above 80% of the required download speed
* upload   - the same test, counted separately from download
* latency  - 95% or more of round-trip measurements at or below 100 ms
* uptime   - average outage under 48 hours per 365 days

Compliance is evaluated per sample set, where a sample set is the group of test
subjects in one state or territory, on one technology, under one committed speed
tier. That grouping is reproduced here.

A note on what this output is. The determination below is **indicative**: it is
what the submitted data implies. The binding determination is made by the Eligible
Entity and NTIA, who may also weigh testing methodology, sampling method, and
transparency obligations that no data file can express. This tool exists so a
submitter finds a problem before the state office does, not to replace the state
office.

See ``docs/sources.md`` for the citation behind every threshold used here.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bead_data.validate import InputError, load_records, validate_records

# --------------------------------------------------------------------------
# Verified NTIA thresholds. See docs/sources.md, source S1.
# --------------------------------------------------------------------------

#: Fraction of speed measurements that must clear the bar.
SPEED_MEASUREMENT_FRACTION = 0.80

#: Fraction of the required speed each measurement must reach.
SPEED_OF_REQUIRED_FRACTION = 0.80

#: Fraction of latency measurements that must be at or below the ceiling.
LATENCY_FRACTION = 0.95

#: Round-trip latency ceiling, in milliseconds.
LATENCY_MS_CEILING = 100

#: Average outage ceiling, in hours per 365 days.
OUTAGE_HOURS_CEILING = 48

#: Annual uptime corresponding to the outage ceiling.
UPTIME_PCT_FLOOR = 99.45

#: Minimum committed speeds for a broadband serviceable location, in Mbps.
BSL_FLOOR_DOWN_MBPS = 100
BSL_FLOOR_UP_MBPS = 20

#: Service standard for a community anchor institution, in Mbps.
CAI_FLOOR_DOWN_MBPS = 1000
CAI_FLOOR_UP_MBPS = 1000

PASS = "PASS"
FAIL = "FAIL"
NO_DATA = "NO DATA"


class ReportError(Exception):
    """Raised when a report cannot be produced."""


# --------------------------------------------------------------------------
# Period selection
# --------------------------------------------------------------------------


def parse_period(period: str) -> tuple[datetime, datetime, str]:
    """Parse ``YYYY-MM`` or ``YYYY-QN`` into a half-open UTC window.

    Returns the start, the exclusive end, and a human label.
    """

    text = period.strip().upper()
    parts = text.split("-")
    if len(parts) != 2:
        raise ReportError(f"could not parse period {period!r}; expected YYYY-MM or YYYY-QN")

    try:
        year = int(parts[0])
    except ValueError as exc:
        raise ReportError(f"could not parse year in period {period!r}") from exc

    tail = parts[1]

    if tail.startswith("Q"):
        try:
            quarter = int(tail[1:])
        except ValueError as exc:
            raise ReportError(f"could not parse quarter in period {period!r}") from exc
        if not 1 <= quarter <= 4:
            raise ReportError(f"quarter must be Q1 through Q4, got {tail!r}")
        start_month = 3 * (quarter - 1) + 1
        end_month = start_month + 3
        label = f"{year} Q{quarter}"
    else:
        try:
            start_month = int(tail)
        except ValueError as exc:
            raise ReportError(f"could not parse month in period {period!r}") from exc
        if not 1 <= start_month <= 12:
            raise ReportError(f"month must be 01 through 12, got {tail!r}")
        end_month = start_month + 1
        label = f"{year}-{start_month:02d}"

    start = datetime(year, start_month, 1, tzinfo=UTC)
    end_year, end_month_norm = (year + 1, 1) if end_month > 12 else (year, end_month)
    end = datetime(end_year, end_month_norm, 1, tzinfo=UTC)

    return start, end, label


def _as_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def in_period(record: dict, window: tuple[datetime, datetime] | None) -> bool:
    """Whether a performance fact's measurement period overlaps ``window``.

    Overlap rather than containment: a measurement week that straddles a month
    boundary is still evidence about both months, and dropping it would
    understate coverage.
    """
    if window is None:
        return True
    start, end = window
    try:
        record_start = _as_datetime(record["period_start"])
        record_end = _as_datetime(record["period_end"])
    except (KeyError, ValueError):
        return False
    return record_start < end and record_end >= start


# --------------------------------------------------------------------------
# Compliance evaluation
# --------------------------------------------------------------------------


@dataclass
class Check:
    """One threshold evaluation."""

    name: str
    verdict: str
    observed: str
    required: str

    @property
    def failed(self) -> bool:
        return self.verdict == FAIL


@dataclass
class SampleSet:
    """A group of performance facts judged together."""

    state_or_territory: str
    technology_code: int
    committed_down_mbps: float
    committed_up_mbps: float
    facts: list[dict] = field(default_factory=list)

    @property
    def key(self) -> str:
        return (
            f"{self.state_or_territory}-{self.technology_code}-"
            f"{self.committed_down_mbps:g}x{self.committed_up_mbps:g}"
        )

    @property
    def location_count(self) -> int:
        return len({f["location_ref"] for f in self.facts})

    def required_speeds(self) -> tuple[float, float]:
        """Required download and upload speeds for this sample set.

        The required speed is the greater of the program floor and what the
        subgrantee committed to. Community anchor institutions in the set raise
        the floor to the symmetric gigabit standard.
        """
        any_cai = any(f.get("is_cai") for f in self.facts)
        floor_down = CAI_FLOOR_DOWN_MBPS if any_cai else BSL_FLOOR_DOWN_MBPS
        floor_up = CAI_FLOOR_UP_MBPS if any_cai else BSL_FLOOR_UP_MBPS
        return (
            max(floor_down, self.committed_down_mbps),
            max(floor_up, self.committed_up_mbps),
        )

    def _rate_check(self, name: str, subset_key: str, total_key: str, floor: float) -> Check:
        total = sum(f.get(total_key) or 0 for f in self.facts)
        subset = sum(f.get(subset_key) or 0 for f in self.facts)
        if total == 0:
            return Check(name, NO_DATA, "no tests reported", f"{floor:.0%} of tests")
        rate = subset / total
        verdict = PASS if rate >= floor else FAIL
        return Check(
            name,
            verdict,
            f"{rate:.2%} ({subset:,} of {total:,} tests)",
            f"at least {floor:.0%}",
        )

    def download_check(self) -> Check:
        required_down, _ = self.required_speeds()
        bar = required_down * SPEED_OF_REQUIRED_FRACTION
        check = self._rate_check(
            f"Download (at or above {bar:g} Mbps)",
            "download_tests_meeting_threshold",
            "download_tests_total",
            SPEED_MEASUREMENT_FRACTION,
        )
        return check

    def upload_check(self) -> Check:
        _, required_up = self.required_speeds()
        bar = required_up * SPEED_OF_REQUIRED_FRACTION
        return self._rate_check(
            f"Upload (at or above {bar:g} Mbps)",
            "upload_tests_meeting_threshold",
            "upload_tests_total",
            SPEED_MEASUREMENT_FRACTION,
        )

    def latency_check(self) -> Check:
        return self._rate_check(
            f"Latency (at or below {LATENCY_MS_CEILING} ms)",
            "latency_tests_at_or_below_100ms",
            "latency_tests_total",
            LATENCY_FRACTION,
        )

    def availability_check(self) -> Check:
        """Availability, preferring reported outage hours over uptime percent.

        Outage hours over 365 days is the quantity NTIA actually evaluates. Uptime
        percent is the fallback when a submitter has not populated the hours, and
        the report says which one was used so the number can be traced.
        """
        outages = [
            f["outage_hours_365d"] for f in self.facts if f.get("outage_hours_365d") is not None
        ]
        if outages:
            mean_outage = statistics.fmean(outages)
            verdict = PASS if mean_outage < OUTAGE_HOURS_CEILING else FAIL
            return Check(
                "Availability (outage hours per 365 days)",
                verdict,
                f"{mean_outage:.1f} h mean across {len(outages)} location(s)",
                f"under {OUTAGE_HOURS_CEILING} h",
            )

        uptimes = [f["uptime_pct"] for f in self.facts if f.get("uptime_pct") is not None]
        if not uptimes:
            return Check(
                "Availability (outage hours per 365 days)",
                NO_DATA,
                "neither outage_hours_365d nor uptime_pct reported",
                f"under {OUTAGE_HOURS_CEILING} h",
            )
        mean_uptime = statistics.fmean(uptimes)
        verdict = PASS if mean_uptime >= UPTIME_PCT_FLOOR else FAIL
        return Check(
            "Availability (from uptime_pct, outage hours not reported)",
            verdict,
            f"{mean_uptime:.3f}% mean uptime across {len(uptimes)} location(s)",
            f"at least {UPTIME_PCT_FLOOR}%",
        )

    def checks(self) -> list[Check]:
        return [
            self.download_check(),
            self.upload_check(),
            self.latency_check(),
            self.availability_check(),
        ]

    def verdict(self) -> str:
        """Overall indicative verdict: any failed threshold means non-compliant."""
        checks = self.checks()
        if any(c.failed for c in checks):
            return FAIL
        if any(c.verdict == NO_DATA for c in checks):
            return NO_DATA
        return PASS


def group_sample_sets(facts: list[dict]) -> list[SampleSet]:
    """Group performance facts into NTIA sample sets."""
    grouped: dict[tuple, SampleSet] = {}
    for fact in facts:
        key = (
            fact.get("state_or_territory", "??"),
            fact.get("technology_code", 0),
            fact.get("committed_down_mbps", 0),
            fact.get("committed_up_mbps", 0),
        )
        if key not in grouped:
            grouped[key] = SampleSet(*key)
        grouped[key].facts.append(fact)
    return [grouped[k] for k in sorted(grouped)]


# --------------------------------------------------------------------------
# Gathering input
# --------------------------------------------------------------------------


@dataclass
class Corpus:
    """Validated records gathered from a directory, split by kind."""

    performance: list[dict] = field(default_factory=list)
    location: list[dict] = field(default_factory=list)
    baba: list[dict] = field(default_factory=list)
    test: list[dict] = field(default_factory=list)
    files_read: int = 0
    invalid_records: int = 0
    skipped_files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, kind: str, records: list[dict]) -> None:
        getattr(self, kind).extend(records)

    def resolve_performance(self) -> list[dict]:
        """Performance facts to evaluate, aggregating any raw observations.

        Raw test observations are rolled up automatically so that a directory of
        measurements yields verdicts without a separate step.

        Where a location has both raw observations and an asserted fact, the derived
        one wins. That is not arbitrary: derived counts cannot understate a
        denominator, because both sides are counted from the same observations, while
        an asserted count is only as good as whatever produced it. The substitution is
        recorded in ``notes`` rather than done silently.
        """
        if not self.test:
            return list(self.performance)

        from bead_data.aggregate import AggregationError, aggregate_tests

        try:
            derived = aggregate_tests(self.test)
        except AggregationError as exc:
            self.notes.append(f"raw observations could not be aggregated: {exc}")
            return list(self.performance)

        self.notes.append(
            f"aggregated {len(self.test)} raw observation(s) into {len(derived)} "
            f"location fact(s); threshold counts for these are derived, not asserted"
        )

        derived_locations = {f["location_ref"] for f in derived}
        overridden = [
            f["location_ref"]
            for f in self.performance
            if f.get("location_ref") in derived_locations
        ]
        if overridden:
            self.notes.append(
                f"{len(overridden)} asserted fact(s) superseded by facts derived from raw "
                f"observations for the same location(s): {', '.join(sorted(set(overridden)))}"
            )

        kept = [f for f in self.performance if f.get("location_ref") not in derived_locations]
        return kept + derived


DATA_SUFFIXES = {".json", ".csv", ".parquet"}


def gather(root: Path) -> Corpus:
    """Load and validate every evidence file under ``root``.

    Invalid records are counted and excluded rather than aborting the report. A
    submitter with one bad row still needs to see the other 199, and the count
    surfaces in the output so the gap is visible rather than silent.
    """
    if not root.exists():
        raise InputError(f"not found: {root}")

    if root.is_file():
        candidates = [root]
    else:
        candidates = sorted(
            p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in DATA_SUFFIXES
        )

    if not candidates:
        raise InputError(f"no .json, .csv, or .parquet files found under {root}")

    corpus = Corpus()
    for path in candidates:
        try:
            records, kind = load_records(path)
        except InputError as exc:
            corpus.skipped_files.append(str(exc))
            continue

        report = validate_records(records, kind, path)
        bad = report.invalid_indices
        corpus.invalid_records += len(bad)
        good = [r for i, r in enumerate(records, start=1) if i not in bad]
        corpus.add(kind, good)
        corpus.files_read += 1

    return corpus


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _stat_line(values: list[float], unit: str) -> str:
    if not values:
        return "not reported"
    return (
        f"mean {statistics.fmean(values):.1f} {unit}, "
        f"median {statistics.median(values):.1f} {unit}, "
        f"min {min(values):.1f}, max {max(values):.1f}"
    )


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out.extend("| " + " | ".join(row) + " |" for row in rows)
    return out


def render_report(corpus: Corpus, period: str | None = None) -> str:
    """Render the Markdown milestone summary."""
    window: tuple[datetime, datetime] | None = None
    label = "all periods"
    if period:
        start, end, label = parse_period(period)
        window = (start, end)

    facts = [f for f in corpus.resolve_performance() if in_period(f, window)]

    lines: list[str] = [
        "# BEAD compliance summary",
        "",
        f"- **Reporting period:** {label}",
        "- **Generated by:** bead-data (see docs/sources.md for every threshold's source)",
        f"- **Files read:** {corpus.files_read}",
        f"- **Records:** {len(facts)} performance, {len(corpus.location)} location, "
        f"{len(corpus.baba)} BABA",
    ]

    if corpus.invalid_records:
        lines.append(
            f"- **Invalid records excluded:** {corpus.invalid_records} "
            f"(run `bead-data validate` to see why)"
        )
    if corpus.skipped_files:
        lines.append(f"- **Unreadable files skipped:** {len(corpus.skipped_files)}")
    for note in corpus.notes:
        lines.append(f"- **Note:** {note}")

    lines += [
        "",
        "> This determination is **indicative**: it is what the submitted data implies.",
        "> The binding determination is made by the Eligible Entity and NTIA, who also",
        "> weigh testing methodology, sampling, and transparency obligations that a data",
        "> file cannot express.",
        "",
    ]

    # ---------------------------------------------------------- performance
    lines += ["## Performance thresholds by sample set", ""]

    if not facts:
        lines += ["No performance facts in this period.", ""]
    else:
        lines += [
            "A sample set is one state or territory, one technology, one committed speed",
            "tier. A sample set is non-compliant if it fails any of the four thresholds.",
            "",
        ]
        sample_sets = group_sample_sets(facts)
        rows = [
            [
                s.key,
                str(s.technology_code),
                f"{s.committed_down_mbps:g}/{s.committed_up_mbps:g}",
                str(s.location_count),
                f"**{s.verdict()}**",
            ]
            for s in sample_sets
        ]
        lines += _table(
            ["Sample set", "Tech code", "Committed", "Locations", "Indicative verdict"], rows
        )
        lines.append("")

        for sample_set in sample_sets:
            lines += [
                f"### Sample set `{sample_set.key}`",
                "",
                f"State/territory {sample_set.state_or_territory}, FCC technology code "
                f"{sample_set.technology_code}, committed "
                f"{sample_set.committed_down_mbps:g}/{sample_set.committed_up_mbps:g} Mbps, "
                f"{sample_set.location_count} location(s).",
                "",
            ]
            lines += _table(
                ["Threshold", "Observed", "Required", "Verdict"],
                [[c.name, c.observed, c.required, c.verdict] for c in sample_set.checks()],
            )
            lines.append("")

        downloads = [f["download_mbps"] for f in facts if f.get("download_mbps") is not None]
        uploads = [f["upload_mbps"] for f in facts if f.get("upload_mbps") is not None]
        latencies = [f["latency_ms_mean"] for f in facts if f.get("latency_ms_mean") is not None]

        lines += [
            "### Observed central values",
            "",
            "Context only. None of the four thresholds is decided on an average.",
            "",
            f"- Download: {_stat_line(downloads, 'Mbps')}",
            f"- Upload: {_stat_line(uploads, 'Mbps')}",
            f"- Mean latency: {_stat_line(latencies, 'ms')}",
            "",
        ]

        uptimes = [f["uptime_pct"] for f in facts if f.get("uptime_pct") is not None]
        if uptimes:
            buckets = {
                f"at or above {UPTIME_PCT_FLOOR}% (meets the outage standard)": 0,
                "99.00% to 99.45%": 0,
                "below 99.00%": 0,
            }
            for value in uptimes:
                if value >= UPTIME_PCT_FLOOR:
                    buckets[f"at or above {UPTIME_PCT_FLOOR}% (meets the outage standard)"] += 1
                elif value >= 99.0:
                    buckets["99.00% to 99.45%"] += 1
                else:
                    buckets["below 99.00%"] += 1

            lines += ["### Uptime distribution", ""]
            lines += _table(
                ["Band", "Locations", "Share"],
                [
                    [band, str(count), f"{count / len(uptimes):.1%}"]
                    for band, count in buckets.items()
                ],
            )
            lines.append("")

    # ------------------------------------------------------------- locations
    lines += ["## Deployment locations", ""]
    if not corpus.location:
        lines += ["No location records found.", ""]
    else:
        statuses: dict[str, int] = {}
        for record in corpus.location:
            statuses[record.get("service_status", "unknown")] = (
                statuses.get(record.get("service_status", "unknown"), 0) + 1
            )
        total = len(corpus.location)
        order = ["planned", "under_construction", "installed", "active", "suspended"]
        rows = [
            [status, str(statuses[status]), f"{statuses[status] / total:.1%}"]
            for status in order
            if status in statuses
        ]
        rows += [
            [status, str(count), f"{count / total:.1%}"]
            for status, count in sorted(statuses.items())
            if status not in order
        ]
        lines += _table(["Service status", "Locations", "Share"], rows)

        built = statuses.get("installed", 0) + statuses.get("active", 0)
        lines += [
            "",
            f"Built (installed or active): **{built} of {total}** ({built / total:.1%}).",
            "",
        ]

    # ------------------------------------------------------------------ BABA
    lines += ["## BABA evidence coverage", ""]
    if not corpus.baba:
        lines += ["No BABA evidence records found.", ""]
    else:
        total = len(corpus.baba)
        certified = [r for r in corpus.baba if r.get("compliance_path") == "domestic_certification"]
        waived = [r for r in corpus.baba if r.get("compliance_path") == "waiver"]
        units = sum(r.get("quantity", 0) for r in corpus.baba)

        lines += _table(
            ["Compliance path", "Records", "Share of records", "Units"],
            [
                [
                    "Domestic certification (manufacturer letter)",
                    str(len(certified)),
                    f"{len(certified) / total:.1%}",
                    f"{sum(r.get('quantity', 0) for r in certified):,}",
                ],
                [
                    "Waiver (reporting tracker)",
                    str(len(waived)),
                    f"{len(waived) / total:.1%}",
                    f"{sum(r.get('quantity', 0) for r in waived):,}",
                ],
                ["**Total**", f"**{total}**", "100.0%", f"**{units:,}**"],
            ],
        )
        lines.append("")

        origins: dict[str, int] = {}
        for record in corpus.baba:
            origins[record.get("origin_country", "??")] = origins.get(
                record.get("origin_country", "??"), 0
            ) + record.get("quantity", 0)
        lines += ["### Units by country of origin", ""]
        lines += _table(
            ["Country", "Units", "Share of units"],
            [
                [country, f"{count:,}", f"{count / units:.1%}" if units else "n/a"]
                for country, count in sorted(origins.items(), key=lambda kv: -kv[1])
            ],
        )
        lines.append("")

        missing_docs = [
            r
            for r in corpus.baba
            if not r.get("attestation_doc_sha256") and not r.get("attestation_doc_uri")
        ]
        if missing_docs:
            lines += [
                f"{len(missing_docs)} of {total} records carry neither an attestation digest",
                "nor a document URI. Valid, but a reviewer cannot tie them to a retained",
                "document without one.",
                "",
            ]

    # ------------------------------------------------------------ data quality
    if corpus.skipped_files:
        lines += ["## Unreadable files", ""]
        lines += [f"- {message}" for message in corpus.skipped_files]
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_report(root: Path, period: str | None = None) -> str:
    """Gather evidence under ``root`` and render the Markdown summary."""
    return render_report(gather(root), period)


def summarize(root: Path, period: str | None = None) -> dict[str, Any]:
    """Machine-readable counterpart to :func:`build_report`.

    Same numbers, no prose, for callers wiring this into a dashboard or a CI gate.
    """
    corpus = gather(root)
    window = None
    label = "all periods"
    if period:
        start, end, label = parse_period(period)
        window = (start, end)

    facts = [f for f in corpus.resolve_performance() if in_period(f, window)]
    sample_sets = group_sample_sets(facts)

    return {
        "period": label,
        "files_read": corpus.files_read,
        "invalid_records": corpus.invalid_records,
        "counts": {
            "performance": len(facts),
            "location": len(corpus.location),
            "baba": len(corpus.baba),
        },
        "sample_sets": [
            {
                "key": s.key,
                "state_or_territory": s.state_or_territory,
                "technology_code": s.technology_code,
                "committed_down_mbps": s.committed_down_mbps,
                "committed_up_mbps": s.committed_up_mbps,
                "locations": s.location_count,
                "verdict": s.verdict(),
                "checks": [
                    {
                        "name": c.name,
                        "verdict": c.verdict,
                        "observed": c.observed,
                        "required": c.required,
                    }
                    for c in s.checks()
                ],
            }
            for s in sample_sets
        ],
    }
