"""Prometheus exposition of compliance evidence.

Turns an evidence directory into metrics, so the same numbers `bead-data report`
prints as Markdown can drive a dashboard or an alert rule. The Grafana dashboard
in `dashboards/` consumes exactly these metric names.

The design goal is that a subgrantee can alert on
``bead_sample_set_compliant == 0`` and find out mid-construction-season that a
sample set is failing, rather than at a state office review months later.

Two decisions worth stating:

* **Thresholds are exported as metrics too.** A dashboard that hardcodes 0.8 will
  silently disagree with the tool the day a threshold changes. Exporting
  ``bead_threshold_*`` lets a panel draw its own limit line from the same source.
* **NO DATA is not 0.** A sample set with no latency tests reported gets no
  ``bead_latency_pass_ratio`` sample at all, rather than a 0 that would look like
  catastrophic failure, or a 1 that would look like a pass. Absent evidence is
  absent, and a graph should show a gap.
"""

from __future__ import annotations

from pathlib import Path

from bead_data.report import (
    FAIL,
    LATENCY_FRACTION,
    LATENCY_MS_CEILING,
    NO_DATA,
    OUTAGE_HOURS_CEILING,
    PASS,
    SPEED_MEASUREMENT_FRACTION,
    SPEED_OF_REQUIRED_FRACTION,
    UPTIME_PCT_FLOOR,
    Corpus,
    SampleSet,
    gather,
    group_sample_sets,
    in_period,
    parse_period,
)
from bead_data.schemas import technology_name

NAMESPACE = "bead"


def _escape(value: str) -> str:
    """Escape a Prometheus label value."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(pairs: dict[str, object]) -> str:
    """Render a label set, sorted for stable output."""
    if not pairs:
        return ""
    inner = ",".join(f'{k}="{_escape(str(v))}"' for k, v in sorted(pairs.items()))
    return "{" + inner + "}"


class MetricSet:
    """Accumulates metric families and renders the text exposition format."""

    def __init__(self) -> None:
        self._families: list[tuple[str, str, str, list[tuple[dict, float]]]] = []
        self._index: dict[str, list[tuple[dict, float]]] = {}

    def family(self, name: str, help_text: str, metric_type: str = "gauge") -> None:
        full = f"{NAMESPACE}_{name}"
        samples: list[tuple[dict, float]] = []
        self._families.append((full, help_text, metric_type, samples))
        self._index[full] = samples

    def add(self, name: str, value: float, **labels: object) -> None:
        """Record one sample. The family must already be declared."""
        full = f"{NAMESPACE}_{name}"
        if full not in self._index:
            raise KeyError(f"metric family {full!r} was not declared")
        self._index[full].append((labels, float(value)))

    def render(self) -> str:
        out: list[str] = []
        for full, help_text, metric_type, samples in self._families:
            if not samples:
                continue
            out.append(f"# HELP {full} {help_text}")
            out.append(f"# TYPE {full} {metric_type}")
            for labels, value in samples:
                rendered = f"{value:.6f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.0f}"
                out.append(f"{full}{_labels(labels)} {rendered}")
        return "\n".join(out) + "\n"


def _sample_set_labels(sample_set: SampleSet) -> dict[str, object]:
    return {
        "sample_set": sample_set.key,
        "state": sample_set.state_or_territory,
        "technology_code": sample_set.technology_code,
        "technology": technology_name(sample_set.technology_code),
        "committed_down_mbps": f"{sample_set.committed_down_mbps:g}",
        "committed_up_mbps": f"{sample_set.committed_up_mbps:g}",
    }


def _verdict_value(verdict: str) -> float | None:
    if verdict == PASS:
        return 1.0
    if verdict == FAIL:
        return 0.0
    return None


def build_metrics(corpus: Corpus, period: str | None = None) -> str:
    """Render Prometheus metrics for an evidence corpus."""
    window = None
    if period:
        start, end, _ = parse_period(period)
        window = (start, end)

    facts = [f for f in corpus.performance if in_period(f, window)]
    sample_sets = group_sample_sets(facts)

    m = MetricSet()

    m.family(
        "threshold_speed_measurement_fraction",
        "Fraction of speed measurements that must clear the bar.",
    )
    m.family(
        "threshold_speed_of_required_fraction",
        "Fraction of the required speed each measurement must reach.",
    )
    m.family(
        "threshold_latency_fraction",
        "Fraction of latency measurements that must be at or below the ceiling.",
    )
    m.family("threshold_latency_ms_ceiling", "Round-trip latency ceiling in milliseconds.")
    m.family("threshold_outage_hours_ceiling", "Average outage ceiling in hours per 365 days.")
    m.family("threshold_uptime_pct_floor", "Annual uptime corresponding to the outage ceiling.")

    m.add("threshold_speed_measurement_fraction", SPEED_MEASUREMENT_FRACTION)
    m.add("threshold_speed_of_required_fraction", SPEED_OF_REQUIRED_FRACTION)
    m.add("threshold_latency_fraction", LATENCY_FRACTION)
    m.add("threshold_latency_ms_ceiling", LATENCY_MS_CEILING)
    m.add("threshold_outage_hours_ceiling", OUTAGE_HOURS_CEILING)
    m.add("threshold_uptime_pct_floor", UPTIME_PCT_FLOOR)

    m.family("files_read", "Evidence files read.")
    m.family("records_invalid", "Records excluded because they failed validation.")
    m.family("records", "Valid records, by fact family.")
    m.add("files_read", corpus.files_read)
    m.add("records_invalid", corpus.invalid_records)
    m.add("records", len(facts), kind="performance")
    m.add("records", len(corpus.location), kind="location")
    m.add("records", len(corpus.baba), kind="baba")

    m.family("sample_set_locations", "Distinct funded locations in a sample set.")
    m.family(
        "sample_set_compliant",
        "1 when a sample set clears all four thresholds, 0 when any fails. "
        "Absent when a threshold has no data.",
    )
    m.family(
        "threshold_compliant",
        "1 when a threshold passes, 0 when it fails. Absent when it has no data.",
    )
    m.family("download_tests_total", "Download tests observed.")
    m.family(
        "download_tests_meeting_threshold",
        "Download tests at or above 80 percent of the required download speed.",
    )
    m.family("download_pass_ratio", "Share of download tests clearing the bar.")
    m.family("upload_tests_total", "Upload tests observed.")
    m.family(
        "upload_tests_meeting_threshold",
        "Upload tests at or above 80 percent of the required upload speed.",
    )
    m.family("upload_pass_ratio", "Share of upload tests clearing the bar.")
    m.family("latency_tests_total", "Latency tests observed, including lost-packet tests.")
    m.family(
        "latency_tests_within_ceiling",
        "Latency tests with round-trip time at or below the ceiling.",
    )
    m.family("latency_pass_ratio", "Share of latency tests within the ceiling.")
    m.family("outage_hours_mean", "Mean outage hours over the trailing 365 days.")
    m.family("uptime_pct_mean", "Mean reported uptime percentage.")
    m.family("download_mbps_mean", "Mean observed download speed. Context only, not a threshold.")
    m.family("upload_mbps_mean", "Mean observed upload speed. Context only, not a threshold.")
    m.family("latency_ms_mean", "Mean observed round-trip latency. Context only.")
    m.family("required_down_mbps", "Required download speed for a sample set.")
    m.family("required_up_mbps", "Required upload speed for a sample set.")

    for sample_set in sample_sets:
        labels = _sample_set_labels(sample_set)
        m.add("sample_set_locations", sample_set.location_count, **labels)

        required_down, required_up = sample_set.required_speeds()
        m.add("required_down_mbps", required_down, **labels)
        m.add("required_up_mbps", required_up, **labels)

        overall = _verdict_value(sample_set.verdict())
        if overall is not None:
            m.add("sample_set_compliant", overall, **labels)

        pairs = (
            (
                "download",
                sample_set.download_check(),
                "download_tests_total",
                "download_tests_meeting_threshold",
                "download_pass_ratio",
            ),
            (
                "upload",
                sample_set.upload_check(),
                "upload_tests_total",
                "upload_tests_meeting_threshold",
                "upload_pass_ratio",
            ),
            (
                "latency",
                sample_set.latency_check(),
                "latency_tests_total",
                "latency_tests_within_ceiling",
                "latency_pass_ratio",
            ),
        )

        for threshold, check, total_metric, met_metric, ratio_metric in pairs:
            value = _verdict_value(check.verdict)
            if value is not None:
                m.add("threshold_compliant", value, threshold=threshold, **labels)
            if check.verdict == NO_DATA:
                continue

            if threshold == "latency":
                total = sum(f.get("latency_tests_total") or 0 for f in sample_set.facts)
                met = sum(f.get("latency_tests_at_or_below_100ms") or 0 for f in sample_set.facts)
            else:
                total = sum(f.get(f"{threshold}_tests_total") or 0 for f in sample_set.facts)
                met = sum(
                    f.get(f"{threshold}_tests_meeting_threshold") or 0 for f in sample_set.facts
                )

            m.add(total_metric, total, **labels)
            m.add(met_metric, met, **labels)
            if total:
                m.add(ratio_metric, met / total, **labels)

        availability = sample_set.availability_check()
        value = _verdict_value(availability.verdict)
        if value is not None:
            m.add("threshold_compliant", value, threshold="availability", **labels)

        outages = [
            f["outage_hours_365d"]
            for f in sample_set.facts
            if f.get("outage_hours_365d") is not None
        ]
        if outages:
            m.add("outage_hours_mean", sum(outages) / len(outages), **labels)

        for metric, field in (
            ("uptime_pct_mean", "uptime_pct"),
            ("download_mbps_mean", "download_mbps"),
            ("upload_mbps_mean", "upload_mbps"),
            ("latency_ms_mean", "latency_ms_mean"),
        ):
            values = [f[field] for f in sample_set.facts if f.get(field) is not None]
            if values:
                m.add(metric, sum(values) / len(values), **labels)

    m.family("locations", "Funded locations by build status.")
    if corpus.location:
        counts: dict[tuple, int] = {}
        for record in corpus.location:
            key = (
                record.get("state_or_territory", "??"),
                record.get("service_status", "unknown"),
                record.get("technology_code", 0),
            )
            counts[key] = counts.get(key, 0) + 1
        for (state, status, code), count in sorted(counts.items()):
            m.add(
                "locations",
                count,
                state=state,
                service_status=status,
                technology_code=code,
                technology=technology_name(code),
            )

    m.family("baba_records", "BABA evidence records by compliance path.")
    m.family("baba_units", "Component units covered by BABA evidence.")
    if corpus.baba:
        rec_counts: dict[str, int] = {}
        unit_counts: dict[tuple, int] = {}
        for record in corpus.baba:
            path = record.get("compliance_path", "unknown")
            rec_counts[path] = rec_counts.get(path, 0) + 1
            key = (path, record.get("origin_country", "??"))
            unit_counts[key] = unit_counts.get(key, 0) + record.get("quantity", 0)
        for path, count in sorted(rec_counts.items()):
            m.add("baba_records", count, compliance_path=path)
        for (path, country), units in sorted(unit_counts.items()):
            m.add("baba_units", units, compliance_path=path, origin_country=country)

    return m.render()


def metrics_for(root: Path, period: str | None = None) -> str:
    """Gather evidence under ``root`` and render Prometheus metrics."""
    return build_metrics(gather(root), period)
