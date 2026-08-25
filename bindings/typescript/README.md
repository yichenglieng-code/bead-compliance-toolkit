# TypeScript / JavaScript binding

A second implementation of the BEAD compliance data schemas, verified against the
same [conformance suite](../../conformance/README.md) as the Python one.

```bash
npm install
npm run conformance
```

```text
conformance suite 0.1.0 (schemas 0.1.0): 87 cases
binding covers: baba, location, performance, test

87 passed

An independent implementation passes every published vector.
```

## Why this exists

To test a claim, not to add a feature.

The project says the JSON Schemas are the artifact and the Python package is one
binding among possible others. That is either true or it is marketing. The way to
find out is to implement it again, in a different language, with a different
validator, and run the same published vectors.

It passes. So an organization that does not run Python can adopt the format without
adopting this project.

## What the exercise revealed

Something worth knowing before you write your own binding.

JSON Schema carries most of the contract by itself. Types, ranges, patterns, enums,
required fields — and also the conditional requirements, which are expressed with
`if`/`then`: the two BABA compliance paths, and the different fields a successful
speed observation needs versus a successful latency observation. Any JSON Schema
validator in any language enforces all of that for free.

What JSON Schema cannot express is **any rule that compares two values.** Those
have to be written by hand in every implementation:

| Schema | Rule |
|---|---|
| `performance_fact` | `period_end` at or after `period_start` |
| `performance_fact` | each `*_tests_meeting_threshold` not exceeding its `*_tests_total` |
| `deployment_location` | `install_date` present when `service_status` is installed or active |
| `baba_evidence` | the two compliance paths being mutually exclusive |
| `performance_test` | `ended_at` at or after `started_at` |
| `performance_test` | no measurement present when the test did not run |
| `performance_test` | `packets_received` not exceeding `packets_sent` |
| `performance_test` | a successful speed test spanning at least 15 seconds |

They live in `CROSS_FIELD_RULES` in `src/index.mjs`, kept as data rather than
inline branches so the list can be audited against
[`docs/schema_reference.md`](../../docs/schema_reference.md).

**This is the trap.** An implementer who runs a schema validator and stops will pass
most of the conformance suite and silently miss these — including the count rule
that is the whole defence against a filtered denominator. The suite catches that,
which is a large part of why it exists.

## Usage

```js
import { createValidator } from "./src/index.mjs";

const { validate } = await createValidator("../../schemas");

const result = validate(record, "performance");
if (!result.valid) {
  for (const { field, message } of result.errors) {
    console.error(`${field}: ${message}`);
  }
}
```

`validate(record, kind)` takes a kind of `performance`, `test`, `location`, or
`baba`, and returns `{ valid, errors }` where each error names the field it blames.
Field paths match what the conformance suite expects, which is how the two
implementations stay comparable.

As in the Python binding, a record that fails schema validation is not then put
through the cross-field pass, since that would mostly restate the same fault.

## Status

Validation only. The Python package additionally does conversion, aggregation,
reporting, metrics, and USAC submission output. Those are conveniences; validation
is the part that has to agree between implementations, and it is the part the
conformance suite pins.

If you want the rest in JavaScript, that is a reasonable issue to open — or a
reasonable pull request.

## Publishing

Not published to npm. It is here as a proof and a reference. If there is demand,
say so in an issue rather than assuming.
