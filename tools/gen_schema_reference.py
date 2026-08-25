#!/usr/bin/env python3
"""Generate docs/schema_reference.md from the normative schemas.

The field reference is generated rather than hand-written for the same reason the
pydantic models are drift-tested against the schemas: a reference doc that is
maintained separately from the thing it documents goes stale, and a stale field
reference is worse than none, because someone will build against it.

The schemas are the single source of truth. This script renders them.

Usage:
    python tools/gen_schema_reference.py           # write the file
    python tools/gen_schema_reference.py --check   # fail if it would change
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from bead_data.models import MODELS  # noqa: E402
from bead_data.schemas import (  # noqa: E402
    FACT_KINDS,
    SCHEMA_VERSION,
    TECHNOLOGY_CODES,
    load_provenance_schema,
    load_schema,
)

TARGET = REPO / "docs" / "schema_reference.md"

# Rendered in this order: the interchange story runs performance, then the
# locations those facts attach to, then the BABA provenance for the hardware.
KIND_ORDER = ["test", "performance", "location", "baba"]


def technology_rows() -> list[tuple[str, str, str]]:
    """Render the FCC code table from its single source of truth in schemas.py."""
    return [
        (str(code), name.replace("_", " "), covers)
        for code, (name, covers) in sorted(TECHNOLOGY_CODES.items())
    ]


CROSS_FIELD_RULES = [
    (
        "test",
        "a successful test must carry the measurement it claims to have taken",
        "A successful speed test needs bytes and an end time; a successful latency test "
        "needs a round-trip time and packet counts. Without them there is no measurement, "
        "only an assertion that one happened.",
    ),
    (
        "test",
        "a test that did not run must not carry a result",
        "NTIA permits reporting that no test completed in a testing hour because consumer "
        "cross-traffic exceeded the threshold. Such an attempt has no measurement, and a "
        "record claiming one would be reporting a result that was never observed.",
    ),
    (
        "test",
        "`packets_received` must not exceed `packets_sent`",
        "Arithmetically impossible, and the shape a corrupted or synthesised latency "
        "record tends to take.",
    ),
    (
        "test",
        "a successful speed test must span at least 15 seconds",
        "NTIA sets a minimum speed-test duration of 15 seconds. A shorter measurement is "
        "not a compliant test, and accepting one silently would let a non-compliant "
        "methodology produce results that look valid.",
    ),
    (
        "performance",
        "`period_end` must be at or after `period_start`",
        "A measurement period that ends before it starts cannot be reconciled against a "
        "testing window.",
    ),
    (
        "performance",
        "each `*_tests_meeting_threshold` must not exceed its `*_tests_total`",
        "NTIA forbids deleting, trimming, or excluding test measurements. More passing "
        "tests than total tests is the signature of a filtered denominator, not a "
        "rounding quirk.",
    ),
    (
        "location",
        "`install_date` is required when `service_status` is `installed` or `active`",
        "A location reported as built is being counted toward a buildout milestone, and a "
        "milestone claim with no date cannot be substantiated on review.",
    ),
    (
        "baba",
        "`compliance_path` `domestic_certification` requires `certification_ref` and "
        "`manufacturing_location`",
        "These are key elements of the manufacturer's BABA certification letter.",
    ),
    (
        "baba",
        "`compliance_path` `waiver` requires `waiver_ref`, `hs_code_10`, "
        "`product_identifier`, and `product_category`",
        "These are key elements of the NTIA waiver reporting tracker.",
    ),
    (
        "baba",
        "the two paths are mutually exclusive",
        "NTIA states that a certification letter is not needed for waived equipment, so a "
        "component travels exactly one path. Both set at once misstates which path a "
        "reviewer should follow.",
    ),
]


def describe_type(sub: dict) -> str:
    """Human-readable type for one property."""
    if "const" in sub:
        return f"`{sub['const']!r}` (constant)".replace("'", '"')
    declared = sub.get("type")
    if isinstance(declared, list):
        declared = "/".join(x for x in declared if x != "null")
    return f"`{declared}`" if declared else "`any`"


def describe_constraints(sub: dict) -> list[str]:
    """Collect the constraints on one property, as short phrases."""
    out: list[str] = []

    if "enum" in sub:
        out.append("one of " + ", ".join(f"`{v}`" for v in sub["enum"]))
    if "const" in sub:
        out.append(f"must equal `{sub['const']}`")
    if "minimum" in sub:
        out.append(f"at least {sub['minimum']}")
    if "maximum" in sub:
        out.append(f"at most {sub['maximum']}")
    if "minLength" in sub and sub["minLength"] == 1:
        out.append("non-empty")
    elif "minLength" in sub:
        out.append(f"at least {sub['minLength']} characters")
    if "pattern" in sub:
        out.append(f"pattern `{sub['pattern']}`")
    if "format" in sub:
        out.append(f"format `{sub['format']}`")
    if "default" in sub:
        out.append(f"defaults to `{str(sub['default']).lower()}`")

    return out


def render_properties(schema: dict, required: set[str], conditional: dict[str, str]) -> list[str]:
    """Render every property of one schema as a definition block."""
    lines: list[str] = []

    for name, sub in schema["properties"].items():
        if name == "provenance":
            lines += [
                "#### `provenance`",
                "",
                "**Required.** Shared object; see [Provenance](#provenance-shared) below.",
                "",
            ]
            continue

        if name in required:
            requirement = "**Required.**"
        elif name in conditional:
            requirement = f"**Conditionally required** — {conditional[name]}"
        else:
            requirement = "Optional."

        facts = [f"Type {describe_type(sub)}."]
        constraints = describe_constraints(sub)
        if constraints:
            facts.append("Constraints: " + "; ".join(constraints) + ".")

        lines += [
            f"#### `{name}`",
            "",
            f"{requirement} {' '.join(facts)}",
            "",
            sub.get("description", "_No description._"),
            "",
        ]

        if "examples" in sub:
            examples = ", ".join(f"`{e}`" for e in sub["examples"])
            lines += [f"Examples: {examples}", ""]

    return lines


def conditional_map(kind: str) -> dict[str, str]:
    """Which fields are required only on some condition, and what that condition is."""
    if kind == "test":
        return {
            "bytes_transferred": "for a successful `download` or `upload` test.",
            "ended_at": "for a successful `download` or `upload` test.",
            "latency_ms_rtt": "for a successful `latency` test.",
            "packets_sent": "for a successful `latency` test.",
            "packets_received": "for a successful `latency` test.",
            "ip_target": "for any successful test.",
        }
    if kind == "location":
        return {"install_date": "when `service_status` is `installed` or `active`."}
    if kind == "baba":
        return {
            "certification_ref": "on the `domestic_certification` path.",
            "manufacturing_location": "on the `domestic_certification` path.",
            "waiver_ref": "on the `waiver` path.",
            "hs_code_10": "on the `waiver` path.",
            "product_identifier": "on the `waiver` path.",
            "product_category": "on the `waiver` path.",
        }
    return {}


def build() -> str:
    lines: list[str] = [
        "# Schema field reference",
        "",
        "<!-- GENERATED FILE - do not edit by hand.",
        "     Run: python tools/gen_schema_reference.py",
        "     The JSON Schemas under schemas/ are the source of truth. -->",
        "",
        f"Schema version **{SCHEMA_VERSION}**. JSON Schema draft 2020-12 is normative; the",
        "pydantic models in `src/bead_data/models.py` are a reference binding that adds the",
        "cross-field rules.",
        "",
        "Every field below carries the reporting rationale for why it exists. The federal",
        "requirement behind each one is cited to a primary NTIA, FCC, or USAC source in",
        "[sources.md](sources.md) — nothing here is asserted on this project's own authority.",
        "",
        "## Contents",
        "",
    ]

    for kind in KIND_ORDER:
        spec = FACT_KINDS[kind]
        anchor = spec.title.lower().replace(" ", "-")
        lines.append(f"- [{spec.title}](#{anchor}) — `--schema {kind}`")
    lines += [
        "- [Provenance (shared)](#provenance-shared)",
        "- [FCC fixed technology codes](#fcc-fixed-technology-codes)",
        "- [Cross-field rules](#cross-field-rules)",
        "- [The four compliance thresholds](#the-four-compliance-thresholds)",
        "",
        "---",
        "",
    ]

    # ------------------------------------------------------------- the families
    for kind in KIND_ORDER:
        spec = FACT_KINDS[kind]
        schema = load_schema(kind)
        required = set(schema["required"])
        conditional = conditional_map(kind)

        model_fields = MODELS[kind].model_fields
        optional_count = len(model_fields) - len(required)

        lines += [
            f"## {spec.title}",
            "",
            f"`schemas/{spec.schema_relpath}`",
            "",
            schema.get("description", ""),
            "",
            f"{len(required)} required fields, {optional_count} optional. "
            f"`additionalProperties` is `false`: unknown fields are rejected, which keeps "
            f"private extensions out of a format meant to be adopted sector-wide.",
            "",
        ]
        lines += render_properties(schema, required, conditional)
        lines += ["---", ""]

    # ----------------------------------------------------------------- provenance
    provenance = load_provenance_schema()
    lines += [
        "## Provenance (shared)",
        "",
        "`schemas/common/v0/provenance.schema.json`",
        "",
        provenance.get("description", ""),
        "",
        "Required on all three fact families.",
        "",
    ]
    lines += render_properties(provenance, set(provenance["required"]), {})
    lines += [
        "In CSV and Parquet, provenance flattens to `provenance.`-prefixed columns and "
        "nests again on read.",
        "",
        "---",
        "",
    ]

    # ------------------------------------------------------------ technology codes
    lines += [
        "## FCC fixed technology codes",
        "",
        "Used by `technology_code` on both `performance_fact` and `deployment_location`.",
        "These are the FCC's own codes, reproduced so the meaning of the field is",
        "unambiguous.",
        "",
        "NTIA treats technologies as different when their FCC technology codes differ, and",
        "sample sets are separated on that basis. The code therefore decides which",
        "population a location is judged against, which is why the field carries no default.",
        "",
        "| Code | Name | Covers |",
        "|---|---|---|",
    ]
    lines += [f"| `{code}` | {name} | {covers} |" for code, name, covers in technology_rows()]
    lines += [
        "",
        "Next-generation fixed wireless access deployments generally fall under `70`, `71`,",
        "or `72`, depending on spectrum.",
        "",
        "---",
        "",
    ]

    # -------------------------------------------------------------- cross-field
    lines += [
        "## Cross-field rules",
        "",
        "Rules spanning more than one field. Implemented in the pydantic models, and in the",
        "JSON Schema through conditional `allOf` blocks where it can express them. Each has",
        "a dedicated test.",
        "",
    ]
    for kind, rule, why in CROSS_FIELD_RULES:
        lines += [f"**{FACT_KINDS[kind].title}** — {rule}", "", f"> {why}", ""]
    lines += ["---", ""]

    # --------------------------------------------------------------- thresholds
    lines += [
        "## The four compliance thresholds",
        "",
        "What the performance fields are ultimately for. NTIA evaluates a BEAD last-mile",
        "network against four thresholds, each computed over a population of discrete",
        "tests, and a provider is non-compliant if it fails **any** one of them.",
        "",
        "| Threshold | Rule | Fields that answer it |",
        "|---|---|---|",
        "| Download | 80% of measurements at or above 80% of required download speed | "
        "`download_tests_meeting_threshold` / `download_tests_total` |",
        "| Upload | the same, counted separately from download | "
        "`upload_tests_meeting_threshold` / `upload_tests_total` |",
        "| Latency | 95% or more of round-trip measurements at or below 100 ms | "
        "`latency_tests_at_or_below_100ms` / `latency_tests_total` |",
        "| Availability | average outage under 48 hours per 365 days (about 99.45% uptime) | "
        "`outage_hours_365d`, falling back to `uptime_pct` |",
        "",
        "Required speed is the greater of the program floor (100/20 Mbps for a broadband",
        "serviceable location, 1 Gbps symmetric for a community anchor institution) and the",
        "committed speed tier in the subgrantee agreement. So for a 100/20 commitment the",
        "working bar is 80/16 Mbps.",
        "",
        "This is why `performance_fact` carries counts and not only means: a record holding",
        "mean download speed and mean latency cannot answer any of the four questions,",
        "because each needs a numerator and a denominator. `bead-data report` computes all",
        "four per sample set.",
        "",
        "The determination `report` produces is **indicative**. The binding determination is",
        "made by the Eligible Entity and NTIA, who also weigh testing methodology, sampling",
        "method, and transparency obligations that no data file can express.",
        "",
    ]

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the generated file is out of date.",
    )
    args = parser.parse_args()

    rendered = build()

    if args.check:
        if not TARGET.exists():
            print(f"{TARGET.relative_to(REPO)} does not exist; run tools/gen_schema_reference.py")
            return 1
        if TARGET.read_text(encoding="utf-8") != rendered:
            print(
                f"{TARGET.relative_to(REPO)} is out of date; "
                f"run python tools/gen_schema_reference.py"
            )
            return 1
        print(f"{TARGET.relative_to(REPO)} is up to date")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(rendered, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(REPO)} ({len(rendered.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
