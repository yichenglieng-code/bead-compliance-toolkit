# Conformance suite

Test vectors for the BEAD compliance data schemas, as plain JSON. No Python, no
dependency on this repository's implementation.

If you are implementing these schemas in another language, this is how you check
whether you got it right — and how you hold this project accountable for the
behaviour it documents.

## Why this exists

A published schema is a claim. A published set of vectors is a claim you can test.

The JSON Schemas in `../schemas/` constrain field types, ranges, patterns, and
enums, and JSON Schema tooling in any language will enforce them. But several of
the rules that actually matter for BEAD reporting are cross-field, and they are the
ones most likely to be implemented inconsistently or skipped:

- a passing test count that exceeds its total, which is the signature of a filtered
  denominator rather than a rounding error
- a location reported as built without a build date
- BABA evidence carrying both compliance paths, or neither path's required fields

Those are the cases this suite pins hardest.

## Layout

```
manifest.json          index of every case, machine-readable
cases/<group>/<name>.json
```

Groups: `performance`, `location`, `baba`, `provenance`, `crossfield`, `strict`.

## Case format

```json
{
  "conformance_suite_version": "0.1.0",
  "name": "crossfield/download_passing_exceeds_total",
  "schema": "performance",
  "description": "More passing download tests than total download tests.",
  "rationale": "NTIA forbids deleting, trimming, or excluding measurements...",
  "valid": false,
  "instance": { "...": "the record under test" },
  "expect_fields": ["download_tests_meeting_threshold"]
}
```

| Field | Meaning |
|---|---|
| `schema` | which fact family to validate against: `performance`, `location`, or `baba` |
| `valid` | whether a conforming implementation must accept the instance |
| `instance` | the record under test |
| `expect_fields` | present only when `valid` is false: field paths a conforming implementation should blame |
| `rationale` | why the rule exists, so you can argue with it |

`rationale` is part of the artifact rather than a code comment on purpose. If you
think a case is wrong, you need to know what it asserts and on whose authority.
Every federal requirement behind these cases is cited in
[`../docs/sources.md`](../docs/sources.md).

## What conformance means

An implementation conforms when, for every case:

1. `valid: true` instances are accepted.
2. `valid: false` instances are rejected.
3. For rejected instances, every path in `expect_fields` appears among the fields
   the implementation blames.

Rule 3 is the one worth taking seriously. Rejecting a bad record while pointing at
the wrong field does not help whoever has to fix the data, and "the record is
invalid" is not an actionable error message when the record has 26 fields.

`expect_fields` is a **subset** requirement, not an exact match. Reporting
additional related fields is fine; missing an expected one is not.

## Running it

Any language. The shape is:

```
for case in manifest.cases:
    payload  = read_json(case.path)
    result   = your_validator(payload.instance, schema=payload.schema)
    assert result.valid == payload.valid
    if not payload.valid:
        assert set(payload.expect_fields) <= set(result.blamed_fields)
```

Against this repository's Python implementation:

```bash
pytest tests/test_conformance.py -v
```

## It has already earned its place

The first run against the reference implementation failed three cases. Unknown-field
rejections were reporting the record as a whole rather than naming the offending
property, so a submitter with a stray column got told their record was invalid
without being told which column. The existing unit tests had not caught it because
they only asserted that the stray field appeared somewhere in the message.

That is the point of writing the contract down separately from the implementation.

## Versioning

`conformance_suite_version` tracks the suite; `schema_version` in `manifest.json`
tracks the schemas it targets. Adding cases is a minor bump. Changing what an
existing case expects is a breaking change to the contract and needs a new schema
version, not an edit — see [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

The suite is generated from declarative definitions in
`../tools/gen_conformance.py`. Edit that and regenerate rather than editing case
files by hand; a test asserts the committed suite is current.

## If you find a gap

A rule this suite does not cover, or a case you believe is wrong, is a useful issue.
Include the instance and what you expect, and cite the requirement if you have one.
