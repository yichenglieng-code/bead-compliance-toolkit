# Extending the toolkit

Concrete recipes. Several artifacts here are coupled and two are generated, so
changing a schema touches more files than you would guess. This page lists them in
order so nothing is missed.

Read [../ARCHITECTURE.md](../ARCHITECTURE.md) first, particularly the two invariants.

## Before you start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                                  # not `python -m pytest`; see CONTRIBUTING
```

The full local gate, matching CI:

```bash
ruff check . && ruff format --check . && pytest -q \
  && python tools/gen_schema_reference.py --check \
  && python tools/gen_conformance.py --check \
  && (cd bindings/typescript && npm install --silent && npm run conformance)
```

Do not pipe those through anything. `ruff format --check . | tail -1` returns the
pipe's exit status, not the check's, which is how unformatted code once reached CI
from this repository.

## Recipe: add an optional field to an existing schema

The cheapest change. Adding an optional field is a minor change under the v0
compatibility rules in [../CONTRIBUTING.md](../CONTRIBUTING.md).

1. **Schema.** Add the property to `schemas/<family>/v0/*.schema.json`. It needs a
   `description` explaining what it is **and why BEAD reporting needs it** — a test
   fails on an undocumented field, deliberately, because a field nobody can explain
   is a field nobody else will adopt.
   - Do **not** add it to `required`.
   - Note the tooling quirk: some editors refuse to write a file containing a remote
     `$schema` URI. If you hit that, write the file with a placeholder key and swap it
     afterwards, or edit with a plain text editor.
2. **Source.** If the field encodes a federal requirement, add the citation to
   [sources.md](sources.md). If it does not, say so in the description.
3. **Model.** Add the field to the matching class in `src/bead_data/models.py` with a
   default of `None`. The drift test asserts model fields match schema properties
   exactly, so this is not optional.
4. **Regenerate.** `python tools/gen_schema_reference.py`
5. **Test.** Add a case exercising it. If it interacts with another field, add a
   cross-field rule and a conformance vector (next recipe).
6. **Changelog.** Under `## Unreleased`, `### Added`.

## Recipe: add a cross-field rule

Rules comparing two values cannot be expressed in JSON Schema, so they live in code
and must be implemented in **every** binding.

1. **Python.** Add a `@model_validator(mode="after")` to the class in `models.py`.
   Open the message with the offending field name — `validate.py` recovers the field
   path from the message when pydantic reports no location, so a message starting
   with the field name is what makes the error actionable.
2. **TypeScript.** Add the rule to `CROSS_FIELD_RULES` in
   `bindings/typescript/src/index.mjs`, returning `{ field, message }`. The
   conformance suite will fail until you do.
3. **Conformance vector.** Add a `Case` to `tools/gen_conformance.py` under the
   `crossfield/` group, with `expect_fields` naming the field that should be blamed.
   Write the `rationale` for an implementer who thinks the rule is wrong.
4. `python tools/gen_conformance.py && python tools/gen_schema_reference.py`
   — the reference has a cross-field rules section fed from `CROSS_FIELD_RULES` in
   the generator, so add it there too.
5. **Unit test.** Assert the field path *and* the message, not just that validation
   failed.

## Recipe: add a whole fact family

Larger, but mechanical once you know the sequence.

1. **Schema** at `schemas/<family>/v0/<name>.schema.json`. Include `schema_version`
   as a `const`, a required `provenance` block `$ref`, and
   `"additionalProperties": false`.
2. **Register** it in `FACT_KINDS` in `src/bead_data/schemas.py`. Pick
   `signature_fields` that are *required* and *unique* among families — autodetection
   relies on both, and a test enforces it.
3. **Model** in `models.py`, and add it to the `MODELS` dict.
4. **Generators.** Add the kind to `KIND_ORDER` in `tools/gen_schema_reference.py`,
   and to `conditional_map()` if it has conditional requirements.
5. **Conformance.** Add a base instance to `BASE` and `SCHEMA_OF` in
   `tools/gen_conformance.py`, then vectors including at least one valid case. A test
   derives the expected schema list from `FACT_KINDS`, so a family without vectors
   fails.
6. **TypeScript.** Add it to `SCHEMA_PATHS` in `bindings/typescript/src/index.mjs`
   and to `CROSS_FIELD_RULES` if applicable.
7. **Report and metrics.** If it belongs in a report, add a field to `Corpus` in
   `report.py` — `gather()` dispatches on kind by attribute name, so a missing
   attribute is an `AttributeError` at runtime rather than a clean error. This has
   happened.
8. **Regenerate both artifacts, run the full gate, update the changelog.**

## Recipe: change a federal threshold

When NTIA or the FCC revises a requirement.

1. **`src/bead_data/thresholds.py`** — the only place a federal number lives.
2. **[sources.md](sources.md)** — update the citation, the version, and the
   "sources were read on" date. If the old value was correct at a past date, say so
   rather than pretending it was always the new value.
3. Check `test_report.py::test_thresholds_match_documented_constants` and the
   dashboard panel limits in `dashboards/grafana/bead_compliance.json`; a test
   asserts the panels match the exported thresholds.
4. `CHANGELOG.md` under `### Changed`, stating the effective date of the change.

A threshold change alters compliance outcomes for existing data. Say so explicitly in
the changelog entry.

## Recipe: add an output format

`convert.py` for containers, or a new module for a submission format.

Emitters must **validate before writing** and write nothing on invalid input.
Emitting evidence that would be rejected downstream just moves the rejection to
someone else's desk.

If the format is per-test, take `performance_test` records. Do not accept aggregated
facts and synthesise rows — see `submit.py`, which refuses exactly that.

## Recipe: add a CLI command

`cli.py` holds argument parsing and exit codes and no domain logic. Put the logic in
a module, call it from the command.

Exit codes are a published contract:

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | input was readable but some record is invalid |
| 2 | usage, I/O, or parse error; nothing could be processed |

Keeping "invalid data" and "could not read the data" distinct is what lets a state
broadband office script tell a rejected submission from a broken one. Add exit-code
assertions to `test_cli.py`.

## Recipe: port to another language

`bindings/typescript/` is the reference for how.

1. Load the JSON Schemas and validate with any draft 2020-12 validator. Register the
   provenance schema locally so `$ref` resolution never touches the network.
2. Implement the cross-field rules by hand. They are enumerated in
   [schema_reference.md](schema_reference.md) and in the TypeScript README.
3. Report errors with a field path matching what the conformance suite expects.
4. Run the suite: for each case in `conformance/manifest.json`, validate the
   instance, compare against `valid`, and for invalid cases assert every path in
   `expect_fields` appears among the fields you blame. It is a subset requirement, so
   blaming extra related fields is fine.

If it passes all 87, open an issue. A second independent implementation is the most
useful contribution this project can receive.

## Things that will bite you

Collected from actually making these mistakes.

| Symptom | Cause |
|---|---|
| Tests pass locally, fail in CI with `ModuleNotFoundError` | `python -m pytest` puts the CWD on `sys.path`; the console script does not. Shared test code goes in `tests/helpers.py`. |
| CI lint fails though you checked | You piped the check through `tail` and got the pipe's exit code. |
| `AttributeError` in `gather()` | New fact kind without a matching `Corpus` field. |
| Conformance suite fails after a schema edit | You changed the schema but not the models, the TypeScript rules, or the generated suite. |
| Integer comes back from Parquet as a float | Something bypassed the explicit Arrow schema in `convert.py`. |
| Round trip loses a field | An emitter wrote an empty string where the field was absent. Absent and empty must stay distinguishable. |
| Doc reference test fails | Regenerate with `python tools/gen_schema_reference.py`. |

## Releasing

See [../RELEASING.md](../RELEASING.md).
