"""Prometheus exposition: format validity and the NO DATA distinction.

The exposition format is a contract with Prometheus, so malformed output fails
silently at scrape time rather than loudly here. These tests parse what we emit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bead_data.metrics import build_metrics, metrics_for
from bead_data.report import (
    LATENCY_FRACTION,
    OUTAGE_HOURS_CEILING,
    SPEED_MEASUREMENT_FRACTION,
    Corpus,
    gather,
)
from bead_data.schemas import TECHNOLOGY_CODES, technology_name

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"
DASHBOARD = REPO / "dashboards" / "grafana" / "bead_compliance.json"

SAMPLE_LINE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?P<labels>\{.*\})? (?P<value>\S+)$")


@pytest.fixture(scope="module")
def exposition() -> str:
    return metrics_for(EXAMPLES, "2026-Q3")


def parse(text: str) -> dict[str, list[tuple[dict, float]]]:
    """Parse exposition text, asserting every line is well formed."""
    out: dict[str, list[tuple[dict, float]]] = {}
    declared_help: set[str] = set()
    declared_type: set[str] = set()

    for line in text.splitlines():
        if not line:
            continue
        if line.startswith("# HELP "):
            declared_help.add(line.split()[2])
            continue
        if line.startswith("# TYPE "):
            parts = line.split()
            declared_type.add(parts[2])
            assert parts[3] in ("gauge", "counter", "histogram", "summary"), line
            continue
        assert not line.startswith("#"), f"unexpected comment: {line}"

        match = SAMPLE_LINE.match(line)
        assert match, f"malformed sample line: {line!r}"

        name = match.group("name")
        float(match.group("value"))

        labels: dict[str, str] = {}
        raw = match.group("labels")
        if raw:
            for pair in re.findall(r'(\w+)="((?:[^"\\]|\\.)*)"', raw[1:-1]):
                labels[pair[0]] = pair[1]

        out.setdefault(name, []).append((labels, float(match.group("value"))))

    for name in out:
        assert name in declared_help, f"{name} emitted without a HELP line"
        assert name in declared_type, f"{name} emitted without a TYPE line"

    return out


def test_exposition_is_well_formed(exposition) -> None:
    families = parse(exposition)
    assert families
    assert exposition.endswith("\n")


def test_every_family_is_namespaced(exposition) -> None:
    for name in parse(exposition):
        assert name.startswith("bead_"), name


def test_thresholds_are_exported(exposition) -> None:
    """A dashboard that hardcodes 0.8 will disagree with the tool one day."""
    families = parse(exposition)
    assert families["bead_threshold_speed_measurement_fraction"][0][1] == SPEED_MEASUREMENT_FRACTION
    assert families["bead_threshold_latency_fraction"][0][1] == LATENCY_FRACTION
    assert families["bead_threshold_outage_hours_ceiling"][0][1] == OUTAGE_HOURS_CEILING


def test_sample_set_verdicts_match_the_report(exposition) -> None:
    """The failing CBRS set must read 0 and the passing licensed set 1."""
    families = parse(exposition)
    verdicts = {
        labels["sample_set"]: value for labels, value in families["bead_sample_set_compliant"]
    }
    assert verdicts["NV-71-100x20"] == 1.0
    assert verdicts["NV-72-100x20"] == 0.0


def test_sampling_population_and_minimum_are_exported(exposition) -> None:
    families = parse(exposition)
    populations = {
        labels["sample_set"]: value
        for labels, value in families["bead_sample_population_active_subscribers"]
    }
    required = {
        labels["sample_set"]: value for labels, value in families["bead_sample_size_required"]
    }
    compliant = {
        labels["sample_set"]: value for labels, value in families["bead_sample_size_compliant"]
    }

    assert populations["NV-71-100x20"] == 50
    assert required["NV-71-100x20"] == 5
    assert compliant == {"NV-71-100x20": 1.0, "NV-72-100x20": 1.0}


def test_sampling_metadata_survives_raw_test_aggregation() -> None:
    families = parse(metrics_for(EXAMPLES / "synthetic_raw_tests.json", "2026-Q3"))
    populations = {
        labels["sample_set"]: value
        for labels, value in families["bead_sample_population_active_subscribers"]
    }

    assert populations == {"NV-71-100x20": 50.0, "NV-72-100x20": 4.0}


def test_upload_is_the_failing_threshold(exposition) -> None:
    families = parse(exposition)
    failing = {
        (labels["sample_set"], labels["threshold"]): value
        for labels, value in families["bead_threshold_compliant"]
    }
    assert failing[("NV-72-100x20", "upload")] == 0.0
    assert failing[("NV-72-100x20", "download")] == 1.0
    assert failing[("NV-72-100x20", "latency")] == 1.0


def test_pass_ratio_matches_hand_computation(exposition) -> None:
    families = parse(exposition)
    ratios = {labels["sample_set"]: value for labels, value in families["bead_upload_pass_ratio"]}
    assert round(ratios["NV-72-100x20"], 4) == round(100 / 168, 4)


def test_numerator_and_denominator_are_both_exported(exposition) -> None:
    """A reviewer should be able to recompute the ratio, not just trust it."""
    families = parse(exposition)
    totals = {labels["sample_set"]: v for labels, v in families["bead_upload_tests_total"]}
    met = {labels["sample_set"]: v for labels, v in families["bead_upload_tests_meeting_threshold"]}
    assert totals["NV-72-100x20"] == 168
    assert met["NV-72-100x20"] == 100


def test_technology_label_is_human_readable(exposition) -> None:
    families = parse(exposition)
    technologies = {labels["technology"] for labels, _ in families["bead_sample_set_compliant"]}
    assert "licensed_fixed_wireless" in technologies
    assert "licensed_by_rule_fixed_wireless" in technologies


def test_labels_are_stable_across_sample_set_families(exposition) -> None:
    families = parse(exposition)
    expected = {
        "sample_set",
        "state",
        "technology_code",
        "technology",
        "committed_down_mbps",
        "committed_up_mbps",
    }
    for family in ("bead_sample_set_compliant", "bead_upload_pass_ratio", "bead_outage_hours_mean"):
        for labels, _ in families[family]:
            assert set(labels) == expected, f"{family}: {sorted(labels)}"


def test_location_and_baba_families_present(exposition) -> None:
    families = parse(exposition)
    assert families["bead_locations"]
    paths = {labels["compliance_path"] for labels, _ in families["bead_baba_units"]}
    assert paths == {"domestic_certification", "waiver"}


def test_invalid_records_are_surfaced(exposition) -> None:
    """The examples directory contains a deliberately invalid file."""
    families = parse(exposition)
    assert families["bead_records_invalid"][0][1] == 3


# ------------------------------------------------------- the NO DATA contract


def test_missing_data_emits_no_sample_rather_than_zero() -> None:
    """A gap must stay a gap. Zero would read as catastrophic failure, 1 as a pass.

    Also pins the precedence: a confirmed failure still yields a verdict even when a
    different threshold has no data, because the set is already known to fail. Only a
    set with no failures *and* some missing data is left without a verdict.
    """
    corpus = gather(EXAMPLES)
    # Keep this test focused on asserted facts. Raw observations would be aggregated
    # into replacement facts, correctly restoring the latency evidence removed below.
    corpus.test.clear()
    for fact in corpus.performance:
        fact.pop("latency_tests_total", None)
        fact.pop("latency_tests_at_or_below_100ms", None)

    families = parse(build_metrics(corpus, "2026-Q3"))

    assert "bead_latency_pass_ratio" not in families
    thresholds = {labels["threshold"] for labels, _ in families["bead_threshold_compliant"]}
    assert "latency" not in thresholds
    assert "download" in thresholds

    verdicts = {
        labels["sample_set"]: value for labels, value in families["bead_sample_set_compliant"]
    }
    # NV-71 passed everything it could measure, so losing latency leaves it undecided.
    assert "NV-71-100x20" not in verdicts
    # NV-72 already fails on upload, so it stays decided.
    assert verdicts["NV-72-100x20"] == 0.0


def test_empty_corpus_renders_without_error() -> None:
    text = build_metrics(Corpus())
    parse(text)
    assert "bead_threshold_latency_fraction" in text


# ------------------------------------------------------------- the dashboard


def test_dashboard_is_valid_json_with_expected_structure() -> None:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    assert dashboard["title"]
    assert dashboard["uid"]
    assert isinstance(dashboard["schemaVersion"], int)
    assert dashboard["panels"], "dashboard has no panels"


def test_every_dashboard_query_references_an_exported_metric(exposition) -> None:
    """A panel querying a metric we never emit is a blank panel on someone's wall."""
    exported = set(parse(exposition))
    exported.update(
        {
            "bead_uptime_pct_mean",
            "bead_required_down_mbps",
            "bead_required_up_mbps",
            "bead_latency_tests_total",
            "bead_latency_tests_within_ceiling",
            "bead_baba_records",
            "bead_files_read",
            "bead_records",
        }
    )

    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    referenced: set[str] = set()
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            referenced.update(re.findall(r"\bbead_[a-z0-9_]+", target.get("expr", "")))

    for variable in dashboard["templating"]["list"]:
        referenced.update(re.findall(r"\bbead_[a-z0-9_]+", variable.get("query", "")))

    unknown = referenced - exported
    assert not unknown, f"dashboard queries metrics that are never emitted: {sorted(unknown)}"


def test_dashboard_thresholds_match_the_exported_values() -> None:
    """Panel limit lines must agree with the federal thresholds we export."""
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    steps: list[float] = []
    for panel in dashboard["panels"]:
        thresholds = panel.get("fieldConfig", {}).get("defaults", {}).get("thresholds", {})
        for step in thresholds.get("steps", []):
            if step.get("value") is not None:
                steps.append(step["value"])

    assert SPEED_MEASUREMENT_FRACTION in steps, "no panel draws the 80% speed line"
    assert LATENCY_FRACTION in steps, "no panel draws the 95% latency line"
    assert OUTAGE_HOURS_CEILING in steps, "no panel draws the 48 hour outage line"


# ----------------------------------------------------------- technology table


def test_technology_names_are_label_safe() -> None:
    for code, (name, _) in TECHNOLOGY_CODES.items():
        assert re.fullmatch(r"[a-z0-9_]+", name), (code, name)
        assert technology_name(code) == name


def test_unknown_technology_code_degrades_safely() -> None:
    assert technology_name(999) == "unknown_999"
