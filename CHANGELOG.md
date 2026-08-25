# Changelog

Notable changes to the schemas and the tooling.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Schema compatibility rules are in [CONTRIBUTING.md](CONTRIBUTING.md): adding an
optional field is minor, while removing or renaming a field, adding a required one,
or tightening a constraint needs a new schema version directory rather than an edit
to `v0`.

## Unreleased

### Added

- **`performance_test` schema** — one discrete speed or latency observation, the
  level NTIA actually judges and USAC actually accepts. This is what makes the two
  items below possible.
- **`bead-data aggregate`** — derives `performance_fact` records from raw
  observations. The reason this matters is not convenience: when the threshold
  counts are computed from the observations, a filtered denominator becomes
  arithmetically impossible rather than merely prohibited.
- **`bead-data submit`** — writes the USAC performance measurement CSV templates
  that NTIA designates for submission, one file per technology and committed speed
  tier, with the BSL identifier in the first column. Emits a manifest listing what
  still requires a person, including the officer certification and the random
  selection method, as explicit blanks rather than plausible filler.
- **Conformance suite** — 87 language-agnostic JSON vectors under `conformance/`,
  stating an instance, whether it must validate, and which fields a conforming
  implementation should blame. See [`conformance/README.md`](conformance/README.md).
- **TypeScript binding** — a second, independent implementation under
  `bindings/typescript/`, passing all 87 vectors. Confirms the schemas are the
  artifact rather than a description of the Python package.
- `tests_not_run_total` on `performance_fact` (optional), so test attempts excluded
  from threshold denominators stay visible instead of silently disappearing.
- `SECURITY.md` and this changelog.
- `report` now aggregates raw observations found in an evidence directory
  automatically, and records in its output when a derived fact supersedes an
  asserted one for the same location.

### Fixed

- **Unknown-field rejections now name the offending property.** Previously a stray
  column produced `record 1: <record>: ...`, so a submitter was told their record
  was invalid without being told which field. Found by the conformance suite on its
  first run against this implementation; the existing unit test had missed it
  because it only checked that the field name appeared somewhere in the message.

### Changed

- The FCC technology code table now lives in one place, `bead_data.schemas`, shared
  by the schemas, the generated field reference, and the metrics label values.

## 0.1.0 — 2026-08-24

First release.

### Added

- Three fact families as versioned JSON Schema (draft 2020-12), plus a shared
  `provenance` block required on every fact:
  - `performance_fact` — one funded location over one measurement period, carrying
    the per-test counts each NTIA threshold is actually judged on rather than only
    averages
  - `deployment_location` — one BEAD-funded location and its place in the build
    lifecycle
  - `baba_evidence` — Build America Buy America provenance, modelling NTIA's two
    mutually exclusive compliance paths
- Python reference binding with pydantic models carrying the cross-field rules, and
  a drift test asserting the models and schemas stay in step.
- `bead-data` CLI: `validate`, `convert`, `report`, `metrics`.
- Lossless conversion between JSON, CSV, and Parquet, including an explicit Arrow
  schema so integer counts survive a Parquet round trip as integers.
- Compliance evaluation against all four NTIA thresholds, grouped into sample sets
  by state or territory, technology code, and committed speed tier. Missing data
  reports as NO DATA rather than as a pass.
- Prometheus metrics export, a Grafana dashboard, alert rules, and an OpenTelemetry
  collector configuration under `dashboards/`.
- Synthetic examples with an end-to-end walkthrough, including a worked case where
  mean upload throughput clears the threshold and the sample set fails anyway.
- `docs/sources.md`, citing every encoded federal requirement to a primary NTIA,
  FCC, or USAC source, with a known-gaps section for what could not be verified.
- Generated field reference, with a test and CI step asserting the committed copy is
  current.
- Factory test orchestration patterns in `docs/patterns/`.
