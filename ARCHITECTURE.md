# Architecture

How this codebase is put together, and why. Written for someone who has just cloned
it and needs to change something without breaking a contract they cannot see.

If you only read one thing here, read [The two invariants](#the-two-invariants).

## The shape of it

```
        schemas/**.json                    normative contract (JSON Schema 2020-12)
              │
              │  the artifact. everything below is an implementation of it.
              ▼
  ┌───────────────────────────┐
  │  thresholds.py            │  federal numbers, no imports
  │  sampling.py              │  section 3.2 sample-size arithmetic
  │  schemas.py               │  locate + load + compile schemas
  └───────────┬───────────────┘
              ▼
  ┌───────────────────────────┐
  │  models.py                │  pydantic binding + cross-field rules
  │  convert.py               │  JSON / CSV / Parquet, lossless both ways
  └───────────┬───────────────┘
              ▼
  ┌───────────────────────────┐
  │  validate.py              │  load → schema pass → model pass → errors
  └───────────┬───────────────┘
              ▼
  ┌───────────────────────────┐
  │  aggregate.py             │  raw observations → derived facts
  │  submit.py                │  raw observations → USAC CSV templates
  └───────────┬───────────────┘
              ▼
  ┌───────────────────────────┐
  │  report.py                │  sampling + four threshold verdicts → Markdown
  │  metrics.py               │  the same verdicts → Prometheus exposition
  └───────────┬───────────────┘
              ▼
        cli.py                       argument parsing, exit codes, nothing else
```

Dependencies point one way only. There are no import cycles, and a test would be a
reasonable thing to add if you want to keep it that way.

## Module by module

| Module | Lines | Responsibility |
|---|---|---|
| `thresholds.py` | ~130 | Every federal number, and nothing else. No imports from the package. |
| `sampling.py` | ~45 | NTIA section 3.2 sample-size arithmetic, including ceiling at the 10% boundary. |
| `schemas.py` | ~180 | Find the schema files, load them, compile validators, hold the FCC technology code table and the `FACT_KINDS` registry. |
| `models.py` | ~450 | Pydantic models bound to the schemas. Carries the cross-field rules. |
| `convert.py` | ~215 | Lossless conversion between JSON, CSV, and Parquet. |
| `validate.py` | ~400 | Reading files, detecting which schema applies, two-pass validation, per-field error reporting. |
| `aggregate.py` | ~250 | Rolling raw observations into per-location facts. |
| `submit.py` | ~280 | Writing the USAC submission templates. |
| `report.py` | ~760 | Sample-set grouping, sampling and four threshold evaluations, Markdown rendering. |
| `metrics.py` | ~310 | Prometheus exposition of the same numbers. |
| `cli.py` | ~450 | Click commands, exit codes. Contains no domain logic. |

### Where to look for what

- **A threshold is wrong** → `thresholds.py`, and update `docs/sources.md` in the same
  commit. Nothing else hardcodes a federal number.
- **A field is missing or wrong** → the JSON Schema first, then `models.py`. See
  [docs/extending.md](docs/extending.md).
- **A validation error is unhelpful** → `validate.py`, specifically `_json_path` and
  `_schema_error_fields`. Naming the offending field is a deliberate feature; see
  invariant 2 below.
- **A sample-size minimum is wrong** → `sampling.py` and the constants in
  `thresholds.py`.
- **A compliance verdict looks wrong** → `report.py`, class `SampleSet`. Sampling
  and each performance threshold have their own methods.
- **Output format** → `convert.py` for containers, `submit.py` for USAC, `report.py`
  for Markdown, `metrics.py` for Prometheus.

## The two invariants

Everything else is negotiable. These two are the reason the project exists, and
breaking either silently would make it actively harmful.

### 1. Counts, never only averages

BEAD performance compliance is evaluated over populations of discrete tests, not on
central values. `performance_fact` therefore carries a numerator *and* a denominator
for each threshold, and `bead-data report` computes rates from them.

A worked case from this repository's own example data: mean upload throughput of
17.90 Mbps clears the applicable 16 Mbps bar while only 59.52% of individual
measurements do, against a required 80%. **The average passes and the network fails.**

Concretely, this means:

- Never add a code path that decides a threshold from a mean.
- `aggregate.py` derives counts from raw observations rather than accepting asserted
  ones, which makes a filtered denominator arithmetically impossible instead of
  merely prohibited. Preserve that property.
- The cross-field rule rejecting a passing count above its total is not a sanity
  check. It is the detector for the most consequential way this reporting goes wrong.

### 2. Absent evidence is not passing evidence

`NO DATA` is a distinct verdict from `FAIL`, and a missing metric series is distinct
from a zero.

- `SampleSet.verdict()` returns `NO_DATA` when a threshold has nothing to evaluate
  and nothing has failed. A confirmed failure still outranks it, because the set is
  already known to fail.
- `metrics.py` emits **no sample at all** for a threshold with no data, rather than a
  `0` that reads as catastrophic failure or a `1` that reads as a pass.
- Validation errors name the offending field. `record 1: <record>: invalid` is
  accurate and useless; a submitter needs to know which of 26 fields to fix.

If you find yourself defaulting a missing value so a code path gets simpler, that is
this invariant being violated.

## Design decisions you might otherwise undo

Recorded because each looks like an oddity until you know the reason. Fuller
discussion in [docs/decisions.md](docs/decisions.md).

| Decision | Why |
|---|---|
| Timestamps are `str`, not `datetime` | Coercion rewrites the caller's formatting, so a JSON → CSV → JSON round trip stops returning what went in. |
| Parquet uses an explicit Arrow schema | Inferred dtypes turn an integer column into a float the moment one value is missing, so a test count comes back as `42.0`. |
| `technology_code` has no default | Defaulting to licensed fixed wireless silently mislabels unlicensed and CBRS builds, and the code decides which population a location is judged against. |
| `additionalProperties: false` everywhere | A shared format cannot quietly carry private extensions, or two parties disagree about what a record means. |
| Derived `fact_id` is deterministic | Re-aggregating the same observations must not create a second copy of the same fact for anything de-duplicating on it. |
| `report` prefers derived facts over asserted ones | Derived counts cannot understate a denominator. The substitution is recorded in the output rather than done silently. |
| The schema pass short-circuits the model pass | A record that fails JSON Schema would mostly get the same fault restated in different words. |
| `submit` refuses aggregated input | Facts cannot be expanded back into individual test rows, and inventing them would be fabricating measurements. |

## Generated artifacts

Four things in the repository are generated and committed. CI fails on a stale copy
of the first two.

| Artifact | Generator | Checked by |
|---|---|---|
| `docs/schema_reference.md` | `tools/gen_schema_reference.py` | test + CI |
| `conformance/` | `tools/gen_conformance.py` | test + CI |
| `examples/synthetic_*.{json,csv}` | `examples/generate_examples.py` | properties asserted in tests |
| `examples/synthetic_raw_tests.json` | `examples/generate_raw_tests.py` | properties asserted in tests |

They are committed rather than built on demand so that a consumer of the schemas, or
a reader of the docs, needs nothing but the repository. Edit the generator, never the
output.

## Testing strategy

460 tests. The interesting ones are not the unit tests.

- **Drift tests** (`test_schemas.py`) assert the pydantic models cover exactly the
  schema properties and agree on which are required. This has already caught a
  contradiction where a field was both required and defaulted.
- **The conformance suite** (`test_conformance.py`) runs the published vectors and
  asserts *which field* is blamed, not merely that validation failed. It found three
  defects on its first run.
- **Example-property tests** (`test_report.py`) pin claims the documentation makes
  about the example data, so regenerating the examples cannot silently turn prose
  false. One of those claims was wrong when first written; the test exists because of
  it.
- **Repo hygiene** (`test_repo_hygiene.py`) verifies the synthetic-data promise rather
  than trusting it, and forbids test modules importing each other.

Run `pytest`, not `python -m pytest`. The two differ in whether the working directory
lands on `sys.path`, and an import that works only under the module form will pass
locally and fail in CI. That happened.

## The other implementation

`bindings/typescript/` implements the same schemas in JavaScript and passes the same
87 conformance vectors. It exists to test the claim that the schemas are the artifact,
not to add a feature.

If you change a cross-field rule, change it there too, or the conformance suite will
tell you. Its README documents which rules JSON Schema can express and which every
implementation must hand-write — a distinction worth reading before you assume a
schema validator is sufficient.

## What is deliberately absent

- **No network, no server, no database.** v0 operates on files so a small ISP can run
  it on a laptop. Streaming and warehouse scale-out are documented as patterns in
  `docs/patterns/`, not built.
- **No authentication or secrets handling.** Nothing here should ever need a
  credential. If a change introduces one, that is a design question, not an
  implementation detail.
- **No adoption telemetry.** The tool does not report usage anywhere.

## Where to start reading

1. [docs/why.md](docs/why.md) — the problem, and the specific technical mistake this
   exists to prevent.
2. [examples/walkthrough.md](examples/walkthrough.md) — the whole thing end to end on
   synthetic data.
3. `schemas/performance/v0/performance_fact.schema.json` — the field descriptions
   carry the reporting rationale.
4. `src/bead_data/report.py`, class `SampleSet` — sampling and the four performance
   thresholds, one method each. This is the core of what the toolkit does.
