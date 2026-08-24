# BEAD Compliance Data Toolkit

**An open data format and reference tooling for the compliance evidence that U.S. broadband deployment runs on.**

The federal BEAD program directs $42.45 billion toward building broadband to unserved
and underserved American locations. To keep that money flowing, three parties have to
exchange evidence continuously: equipment **manufacturers** prove what they shipped and
where it was made, **internet service providers** receiving BEAD subgrants prove their
networks actually deliver the promised speed and reliability, and **state broadband
offices** check all of it before reporting up to NTIA.

Today that exchange happens largely through bespoke spreadsheets, one-off export
scripts, and manual review. Every new pairing of manufacturer and ISP, or ISP and state
office, tends to mean another custom parser. The cost of that plumbing falls hardest on
small rural providers, who can least afford to spend grant dollars on data wrangling
instead of towers and fiber.

This toolkit provides a common, vendor-neutral format for that evidence, plus reference
tools to validate and summarize it, so **compliance evidence can be produced once and
trusted everywhere**. Apache-2.0 licensed, no vendor lock-in, adoptable by any U.S.
organization.

> **Status: v0.1, early.** The schemas are versioned and the tooling works, but this is a
> new project. Field names may change before v1.0. Feedback from people who actually file
> BEAD reports is the most useful thing you can contribute right now — see
> [CONTRIBUTING.md](CONTRIBUTING.md).

---

## What problem this solves, concretely

BEAD compliance is not judged on averages, and that is where most homegrown reporting
gets into trouble. NTIA evaluates last-mile networks against four separate thresholds,
each computed over a population of individual tests:

| What is measured | The threshold that actually applies |
|---|---|
| Download speed | 80% of measurements at or above 80% of the required speed |
| Upload speed | 80% of measurements at or above 80% of the required speed, counted separately from download |
| Latency | 95% or more of round-trip measurements at or below 100 ms |
| Availability | Average outage under 48 hours per 365 days (about 99.45% uptime) |

Failing any one of the four means non-compliance. A spreadsheet that records mean
download speed and mean latency cannot answer a single one of those questions, because
each needs a numerator and a denominator, not an average.

So the performance schema in this toolkit carries the test counts, not just the means.
That one design decision is most of the value here.

## The three fact families

| Family | One record is | Serves |
|---|---|---|
| [`performance_fact`](schemas/performance/v0/performance_fact.schema.json) | one funded location's performance over one measurement period | ISP milestone reporting; manufacturer factory test export |
| [`deployment_location`](schemas/location/v0/deployment_location.schema.json) | one BEAD-funded location and its place in the build lifecycle | buildout milestone roll-up |
| [`baba_evidence`](schemas/baba/v0/baba_evidence.schema.json) | Build America Buy America provenance for one component | manufacturer attestation; subgrantee evidence bundles |

JSON Schema (draft 2020-12) is the normative definition. The
[pydantic](https://docs.pydantic.dev/) models in `src/bead_data/models.py` are a
reference binding that adds the cross-field rules. Every record carries a
`schema_version` and a `provenance` block, so a fact stays auditable after it has passed
through three organizations.

Each field is documented with the reporting rationale behind it in
[`docs/schema_reference.md`](docs/schema_reference.md). Every program requirement encoded
here is cited to its primary NTIA, FCC, or USAC source in
[`docs/sources.md`](docs/sources.md) — nothing about federal requirements is asserted
here on this project's own authority. The longer argument for the project is in
[`docs/why.md`](docs/why.md).

## Install

Requires Python 3.11 or newer.

```bash
git clone https://github.com/yichenglieng-code/bead-compliance-toolkit.git
cd bead-compliance-toolkit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Use

Validate a submission, whether it arrived as JSON or CSV:

```bash
bead-data validate examples/synthetic_field_telemetry.json
bead-data validate examples/synthetic_factory_export.csv
bead-data validate examples/synthetic_baba_bundle/
```

Failures are reported per record with a field path and an explanation:

```text
record 3: latency_tests_at_or_below_100ms: latency_tests_at_or_below_100ms (900) must not exceed latency_tests_total (840)
record 7: service_status: 'in_progress' is not one of ['planned', 'under_construction', 'installed', 'active', 'suspended']
2 valid, 2 invalid
```

Exit codes are stable so this drops into CI: `0` all valid, `1` readable but some record
is invalid, `2` could not read the input at all.

The schema is autodetected from the fields present, or you can pin it with
`--schema performance|location|baba`.

### Convert between containers

```bash
bead-data convert examples/synthetic_factory_export.csv --to json -o out.json
bead-data convert examples/synthetic_field_telemetry.json --to parquet -o out.parquet
```

Round trips are lossless in both directions, including which optional fields were
absent, and integer counts stay integers rather than becoming `42.0`. Conversion
validates first: invalid input writes nothing and exits `1`, so a bad batch fails on
your machine instead of at the state office.

### Report against the four thresholds

```bash
bead-data report path/to/evidence/ --period 2026-Q3
```

Produces a Markdown summary with an indicative verdict per sample set — one state or
territory, one technology, one committed speed tier, which is how NTIA groups them:

```text
| Sample set   | Tech code | Committed | Locations | Indicative verdict |
|--------------|-----------|-----------|-----------|--------------------|
| NV-71-100x20 | 71        | 100/20    | 6         | **PASS**           |
| NV-72-100x20 | 72        | 100/20    | 4         | **FAIL**           |
```

...then per sample set, each threshold with its numerator and denominator, plus
location counts by build status and BABA coverage by compliance path.

The verdict is **indicative**: it is what the submitted data implies. The binding
determination belongs to the Eligible Entity and NTIA, who also weigh testing
methodology, sampling, and transparency obligations no data file can express. The point
is to find a problem before a reviewer does.

A narrated end-to-end pass — manufacturer export, ISP merge, state office review,
including a worked example where the average looks fine and the sample set still fails —
is in [`examples/walkthrough.md`](examples/walkthrough.md).

## Design principles

1. **One format between three parties.** A manufacturer, an ISP, and a state office
   should not need three different shapes for the same underlying fact.
2. **Normative schema, reference binding.** The JSON Schemas stand alone and can be
   implemented in any language. This Python package is the first binding, not the
   definition.
3. **Vendor-neutral by construction.** Equipment is described by generic class and by
   FCC technology code, never by vendor product naming. A format the whole sector is
   meant to adopt cannot privilege one manufacturer's vocabulary.
4. **Every requirement cited.** Encoded thresholds trace to a primary federal source in
   [`docs/sources.md`](docs/sources.md). Where a detail is genuinely open, the docs say
   so rather than guessing.
5. **Local first.** v0.1 runs on files, with no cloud dependency, so a small ISP can use
   it on a laptop. Streaming and warehouse scale-out patterns are documented in
   `docs/patterns/` as the path up, not required on the way in.
6. **Synthetic examples only.** No real subscriber or location data ships here, ever.

## Roadmap

- Emitter for the USAC PMM CSV format that NTIA designates for actual submission
- Grafana dashboard and OpenTelemetry examples over the performance schema
- Factory test orchestration pattern documentation
- Sampling validation: whether the sample size matches the active subscriber count
- Bindings in additional languages, if there is demand for them

## Contributing

Issues and pull requests are welcome, particularly from people who file BEAD reports and
can say where the schemas are wrong. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache-2.0](LICENSE). Copyright 2026 Yicheng Li. See [NOTICE](NOTICE).

## About

Built and maintained by Yicheng (Ethan) Li, a software engineer specializing in
large-scale distributed systems and manufacturing data infrastructure. He spent three
years building the cloud manufacturing platform behind next-generation fixed wireless
access equipment now deployed across rural America, including networks funded by the
federal BEAD program, and currently works on Tier-0 web-scale systems. He builds open
tooling for broadband compliance data. M.Sc. EE, Columbia University.

This project is independent. It is not affiliated with, endorsed by, or sponsored by
NTIA, the FCC, USAC, or any equipment manufacturer or service provider.
