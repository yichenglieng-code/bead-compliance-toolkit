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

The longer version of this argument, with a worked example where mean upload speed clears
the threshold and the sample set still fails, is written up in
[**Your BEAD performance report probably passes on averages and fails on the rules**](https://yichenglieng-code.github.io/bead-compliance-averages/).

## The three fact families

| Family | One record is | Serves |
|---|---|---|
| [`performance_test`](schemas/performance/v0/performance_test.schema.json) | one discrete speed or latency observation | what NTIA judges and USAC accepts |
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
[`docs/why.md`](docs/why.md), and the upstream manufacturing context is in
[`docs/patterns/factory_test_orchestration.md`](docs/patterns/factory_test_orchestration.md).

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

### Go from raw observations to a submission

The full chain a subgrantee actually runs:

```bash
bead-data validate  examples/synthetic_raw_tests.json --schema test
bead-data aggregate examples/synthetic_raw_tests.json -o facts.json
bead-data report    evidence/ --period 2026-Q3
bead-data submit    examples/synthetic_raw_tests.json -d submission/
```

`aggregate` derives `performance_fact` records from raw observations, and that is worth
more than convenience: **when the threshold counts are computed from the observations, a
filtered denominator becomes arithmetically impossible rather than merely prohibited.**
A submitter cannot understate a denominator by dropping failures, because both sides are
counted from the same list.

`submit` writes the USAC performance measurement CSV templates NTIA designates for
submission — one file per technology and committed speed tier, BSL identifier in the first
column — plus a manifest listing what still requires a person, including the officer
certification and the random selection method. Those are left as blanks, not filler.

It requires raw observations. Aggregated facts cannot be expanded back into individual
test rows, and inventing them would be fabricating measurements.

### Convert between containers

```bash
bead-data convert examples/synthetic_factory_export.csv --to json -o out.json
bead-data convert examples/synthetic_field_telemetry.json --to parquet -o out.parquet
```

Round trips are lossless in both directions, including which optional fields were
absent, and integer counts stay integers rather than becoming `42.0`. Conversion
validates first: invalid input writes nothing and exits `1`, so a bad batch fails on
your machine instead of at the state office.

### Validate sample size and report the four thresholds

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

...then per sample set, the section 3.2 sample-size check and each performance
threshold with its numerator and denominator, plus location counts by build status
and BABA coverage by compliance path. Supply
`sample_population_active_subscribers` on every fact in a sample set; if it is
missing or inconsistent, the set reports `NO DATA`, never a false pass.

The verdict is **indicative**: it is what the submitted data implies. The binding
determination belongs to the Eligible Entity and NTIA, who also weigh testing
methodology, whether the declared population is true, random selection, and
transparency obligations arithmetic cannot prove. The point is to find a problem
before a reviewer does.

A narrated end-to-end pass — manufacturer export, ISP merge, state office review,
including a worked example where the average looks fine and the sample set still fails —
is in [`examples/walkthrough.md`](examples/walkthrough.md).

## Implementing this in another language

The schemas are the artifact; this Python package is one binding, not the definition.
There is a [conformance suite](conformance/README.md) of **87 plain-JSON test vectors**
stating an instance, whether it must validate, and which fields a conforming
implementation should blame when it does not.

A [TypeScript binding](bindings/typescript/README.md) passes all 87, which is how the
language-independence claim gets checked rather than merely stated.

That exercise surfaced something worth knowing before you write your own: JSON Schema
carries most of the contract, including the conditional requirements, but **it cannot
express any rule that compares two values.** Those have to be written by hand in every
implementation, and they include the count rule that is the whole defence against a
filtered denominator. An implementer who runs a schema validator and stops will pass most
of the suite and silently miss them. The list is enumerated in the TypeScript README.

The suite found three defects in this implementation on its first run.

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

### Feed a dashboard

```bash
bead-data metrics path/to/evidence/ --period 2026-Q3
```

Emits the same numbers in Prometheus exposition format, so the threshold verdicts can
drive an alert instead of a document:

```text
bead_sample_set_compliant{sample_set="NV-72-100x20",technology="licensed_by_rule_fixed_wireless"} 0
bead_upload_pass_ratio{sample_set="NV-72-100x20"} 0.595238
```

A Grafana dashboard, Prometheus alert rules, and an OpenTelemetry collector config are in
[`dashboards/`](dashboards/README.md). Alerting on `bead_sample_set_compliant == 0` is the
rule worth having, because it fires while there is still time to respond.

Note that a missing series is not a zero: a threshold with no data reported emits no
sample at all, rather than a 0 that would read as total failure or a 1 that would read as
a pass.

## Roadmap

- Outage-event records so availability can be derived rather than supplied
- Publication to a public package registry
- Bindings in additional languages, if there is demand for them

## Documentation

| If you want to | Read |
|---|---|
| Understand the problem and why this exists | [docs/why.md](docs/why.md) |
| See it work end to end | [examples/walkthrough.md](examples/walkthrough.md) |
| Look up a field | [docs/schema_reference.md](docs/schema_reference.md) |
| Check a federal requirement, or what is unverified | [docs/sources.md](docs/sources.md) |
| Decode the jargon | [docs/glossary.md](docs/glossary.md) |
| Understand the codebase | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Change or extend something | [docs/extending.md](docs/extending.md) |
| Know why something is the way it is | [docs/decisions.md](docs/decisions.md) |
| Implement the schemas elsewhere | [conformance/README.md](conformance/README.md) |
| See a second implementation | [bindings/typescript/README.md](bindings/typescript/README.md) |
| Wire up dashboards and alerts | [dashboards/README.md](dashboards/README.md) |
| Understand the upstream factory side | [docs/patterns/factory_test_orchestration.md](docs/patterns/factory_test_orchestration.md) |
| Contribute | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Know how the project is run, or take it over | [GOVERNANCE.md](GOVERNANCE.md) |
| Cut a release | [RELEASING.md](RELEASING.md) |
| See what changed | [CHANGELOG.md](CHANGELOG.md) |
| Report a vulnerability | [SECURITY.md](SECURITY.md) |

## Contributing

Issues and pull requests are welcome, particularly from people who file BEAD reports and
can say where the schemas are wrong. See [CONTRIBUTING.md](CONTRIBUTING.md), and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

If you are picking this up cold, [ARCHITECTURE.md](ARCHITECTURE.md) and
[docs/extending.md](docs/extending.md) are written for exactly that. The project is
maintained by one person and [GOVERNANCE.md](GOVERNANCE.md) says plainly what that means,
including what to do if the maintainer goes quiet.

## License and use

[Apache-2.0](LICENSE). Copyright 2026 Yicheng Li. See [NOTICE](NOTICE).

Use it commercially, embed it in a product, fork it, or implement the schemas in another
language without asking. No attribution negotiation, no contributor licence agreement, no
per-seat terms. A format meant to sit between three parties cannot be one that any of them
has to seek permission to adopt.

The JSON Schemas are the normative artifact and stand on their own. Nothing here obliges an
adopter to run this implementation, or to use Python at all.

## About

Built and maintained by [Yicheng (Ethan) Li](https://yichenglieng-code.github.io/), a
software engineer specializing in
large-scale distributed systems and manufacturing data infrastructure. He spent three
years building the cloud manufacturing platform behind next-generation fixed wireless
access equipment now deployed across rural America, including networks funded by the
federal BEAD program, and currently works on Tier-0 web-scale systems. He builds open
tooling for broadband compliance data. M.Sc. EE, Columbia University.

This project is independent. It is not affiliated with, endorsed by, or sponsored by
NTIA, the FCC, USAC, or any equipment manufacturer or service provider.
