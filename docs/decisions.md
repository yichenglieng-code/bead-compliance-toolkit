# Decision log

Decisions that are not obvious from the code, with the reasoning that produced them.

The purpose is narrow: **stop a future maintainer from confidently undoing something
deliberate.** Several entries below look like defects until you know why they are that
way, and at least three were arrived at by getting it wrong first.

Each records the decision, the reasoning, and what would justify revisiting it. If you
change one, update its entry rather than deleting it.

---

## 1. The schemas are normative; the Python package is a binding

**Decision.** JSON Schema files under `schemas/` define the format. Every
implementation, including this repository's Python one, is subordinate to them.

**Why.** A format that only exists as one library's behaviour cannot be adopted by an
organization that does not run that library. The audience includes manufacturers, ISPs,
and state agencies with unrelated technology stacks.

**Consequences.** A drift test asserts the models match the schemas exactly. The
[conformance suite](../conformance/README.md) exists so the contract is testable
independently. A TypeScript binding exists so the claim is demonstrated rather than
asserted.

**Revisit if.** Never, while the goal is sector-wide adoption. This is the foundation.

---

## 2. `performance_fact` carries test counts, not only averages

**Decision.** Each threshold gets a numerator and a denominator. Means are kept but
labelled context only.

**Why.** NTIA evaluates over populations of discrete tests. A record holding only mean
speed and mean latency cannot answer any of the four compliance questions. Worse, it
fails in the dangerous direction: in this repository's own example data, mean upload of
17.90 Mbps clears the 16 Mbps bar while only 59.52% of measurements do, against a
required 80%. The average says pass and the network fails.

**Consequences.** This is invariant 1 in [../ARCHITECTURE.md](../ARCHITECTURE.md). It
motivated the `performance_test` schema and `aggregate` (entry 8), the cross-field count
rule, and most of the reporting design.

**Revisit if.** NTIA changes to an average-based standard. Nothing short of that.

---

## 3. Absent evidence is reported as absent, never as zero or pass

**Decision.** `NO DATA` is a distinct verdict. `metrics.py` emits no sample at all for a
threshold with no data.

**Why.** A zero reads as catastrophic failure and a one reads as a pass. Both are
false, and a compliance tool that quietly scores missing evidence is worse than
useless — it is actively misleading to someone relying on it.

**Consequences.** Invariant 2. `SampleSet.verdict()` distinguishes three outcomes, and a
confirmed failure outranks missing data because the set is already known to fail. The
Prometheus behaviour needs a documented alert rule to catch absence, which
`dashboards/README.md` provides.

**Revisit if.** Never.

---

## 4. Timestamps stay strings

**Decision.** Date and date-time fields are `str` in the models, parsed for validation
but never coerced.

**Why.** Coercing to `datetime` and re-serialising rewrites the caller's formatting, so
a JSON → CSV → JSON round trip stops returning what went in. Losslessness is a promise
the project makes.

**Consequences.** Comparison rules parse on demand. Slightly more code, exact fidelity.

**Revisit if.** Someone finds a formatting-preserving datetime type. Even then, the
round-trip tests are the arbiter.

---

## 5. Parquet uses an explicit Arrow schema

**Decision.** Build the Arrow schema from the JSON Schema declarations rather than
letting pandas infer dtypes.

**Why.** Inference turns an integer column into a float the moment one value is
missing, so `download_tests_total` comes back as `42.0`. A count that is not an integer
is a count somebody will mis-handle.

**Revisit if.** Never; inference cannot know the declared type.

---

## 6. `technology_code` has no default

**Decision.** Required on both `performance_fact` and `deployment_location`, with no
default, despite an early draft defaulting it to 71.

**Why.** NTIA separates sample sets by FCC technology code, so the code decides which
population a location is judged against. Defaulting to licensed fixed wireless would
silently mislabel unlicensed (70) and CBRS (72) builds — and mislabelled is worse than
missing, because missing gets noticed.

**How it was found.** The schema/model drift test caught the field being simultaneously
`required` and defaulted, which is incoherent. Resolving that contradiction surfaced
the substantive question.

**Revisit if.** Never.

---

## 7. `additionalProperties: false` on every schema

**Decision.** Unknown fields are rejected.

**Why.** A shared format cannot quietly carry private extensions, or two parties end up
disagreeing about what a record means while both believe they are conforming.

**Consequences.** An organization needing an extra field must propose it. That friction
is intentional. Rejections name the offending property (entry 12).

**Revisit if.** A genuine need appears for namespaced extensions. Then design them
explicitly, with a reserved prefix and documented semantics — do not simply relax this.

---

## 8. Counts are derived from raw observations, not accepted as asserted

**Decision.** Added the `performance_test` schema and `bead-data aggregate`, so
threshold counts can be computed rather than declared.

**Why.** The schema could only *prohibit* a filtered denominator — dropping failed
measurements before aggregating so a pass rate looks better than reality. Deriving both
sides from the same list of observations makes it arithmetically impossible instead.

**Consequences.** `report` prefers derived facts over asserted ones for the same
location, and records the substitution in its own output. `submit` requires raw
observations because facts cannot be expanded back into test rows.

**Revisit if.** Never; this is the project's strongest integrity property.

---

## 9. BABA is modelled as two mutually exclusive paths

**Decision.** A `compliance_path` discriminator, with each path conditionally requiring
different fields, rather than an optional certification reference and an optional waiver
reference.

**Why.** NTIA runs two distinct frameworks and states plainly that a certification
letter is *not needed* for waived equipment. The paths require genuinely different
fields — a waiver needs a 10-digit HS code and a product identifier, a certification
needs a manufacturing location. A record carrying both misstates which path a reviewer
should follow.

**Revisit if.** NTIA restructures the framework.

---

## 10. Verdicts are labelled indicative, not binding

**Decision.** Every output says the determination is what the submitted data implies,
and that the binding determination belongs to the Eligible Entity and NTIA.

**Why.** It is true. The tool can validate sample-size arithmetic against a declared
population, but it cannot prove that the population is complete, that subjects were
selected randomly, or that every transparency obligation was met. Overclaiming would
expose users to relying on a verdict this tool is not positioned to give.

**Revisit if.** Never. If anything, strengthen it.

---

## 11. Documentation is generated where it can be

**Decision.** `docs/schema_reference.md` and the whole conformance suite are generated
from the schemas and committed, with CI failing on a stale copy.

**Why.** A field reference maintained separately from the schemas goes stale, and a
stale reference is worse than none because someone will build against it.

**Consequences.** Edit the generator, never the output. Committing the generated files
means a consumer needs nothing but the repository.

---

## 12. Validation errors name the field, not the record

**Decision.** `required` and `additionalProperties` failures are resolved to the
offending property name, even though JSON Schema reports them against the object.

**Why.** "record 1: this record is invalid" is accurate and useless when the record has
26 fields. The person receiving the error has to fix data, not admire the diagnosis.

**How it was found.** The conformance suite caught the `additionalProperties` case on
its first run against this implementation. 183 passing tests had missed it, because they
only checked the field name appeared somewhere in the message rather than that it was
blamed as a field.

---

## 13. Derived `fact_id` is deterministic, and shaped as UUID v4

**Decision.** Derive it from a hash of location and period, then force the version bits
to v4.

**Why.** Re-aggregating the same observations must produce the same id, or anything
de-duplicating on it accumulates a fresh copy of the same fact every run. A v5 UUID
would be the conventional way to express "derived from these inputs", but the schema
requires v4.

**How it was found.** The aggregation pipeline validates its own output, which rejected
the v5 id immediately.

**Revisit if.** A future schema version allows v5. Then use it, and say so.

---

## 14. `uptime_pct` is not inferred during aggregation

**Decision.** `aggregate` emits 100 and prints a note telling the operator to correct it
from their outage records.

**Why.** Outage duration is genuinely not observable from a sample of speed and latency
tests. Inferring it from gaps between observations would be a guess presented as a
measurement.

**Consequences.** An availability determination on purely derived facts is not
trustworthy until corrected. The note says so every run.

**Revisit if.** An outage-event schema is added. That is the right fix, and it is
roadmap rather than done.

---

## 15. Thresholds live in a dependency-free module

**Decision.** `thresholds.py` holds every federal number and imports nothing from the
package.

**Why.** They started in `report.py`, which meant `aggregate.py` imported `report.py`
for constants while `report.py` imported `aggregate.py` to roll up observations — a
circular dependency held together by a late import inside a function. That works and is
confusing, which is the wrong trade in code a stranger has to maintain.

**Consequences.** One file to edit when a federal requirement changes, paired with
`sources.md`. No import cycles anywhere.

---

## 16. No network, no server, no credentials

**Decision.** v0 operates on local files. Streaming and warehouse architecture is
documented in `docs/patterns/` and not built.

**Why.** The smallest thing that is genuinely useful, and a rural co-op can run it on a
laptop. A hosted service would also make the project a dependency rather than a format.

**Consequences.** `$ref` resolution is local so validation never touches the network.
Nothing in the codebase needs a secret.

**Revisit if.** Never for the core. A separate service could consume the format without
this repository growing one.

---

## 17. Synthetic example data, generated deterministically

**Decision.** All examples produced by committed scripts with a fixed seed. No real
subscriber, location, provider, or manufacturer data.

**Why.** Privacy, obviously. But also auditability: a reader can see how a number was
arrived at rather than trusting a hand-typed file.

**Consequences.** Regenerating must be deterministic. Tests assert properties the
documentation claims about the examples — added after a walkthrough claim turned out to
be false when checked, which is entry 18.

---

## 18. Example data is engineered to demonstrate the central failure

**Decision.** The CBRS sample set is built so mean upload clears the bar while the
measurement population does not.

**Why.** The claim that averages hide threshold failures is the project's core argument,
and it is more convincing shown than asserted.

**How it was found.** The walkthrough originally claimed mean upload was "comfortably
above" the bar. Checking it against the data showed 15.65 Mbps — *below* the bar,
making the claim false. Rather than soften the prose, the generator was changed so the
data genuinely exhibits the property, and a test now pins it so regenerating cannot
quietly make the documentation false again.

**Lesson worth keeping.** Verify asserted numbers against the actual data before
writing them down.

---

## 19. Sampling metadata is repeated, and absence blocks a pass

**Decision.** `sample_population_active_subscribers` is optional on both raw tests
and performance facts, but when supplied it must repeat consistently across a sample
set. `report` treats missing or partially reported population metadata as `NO DATA`,
conflicting values as a failure, and an undersized sample as a failure.

**Why.** NTIA section 3.2 defines the minimum from a sample-set-level population,
while the existing interchange records are per observation or per location. Repeating
one small integer preserves the file-first design and lets raw-test aggregation carry
the evidence without introducing a separate manifest whose join could silently drift.

**Consequences.** The arithmetic can prevent a false pass, but cannot prove that the
declared active-subscriber population is true or that locations were selected randomly.
Outputs continue to label the determination indicative and say exactly what remains a
human responsibility.

**Revisit if.** A future schema version adds a first-class sample-set manifest. That
would normalize the metadata, but it must retain the same absence and consistency
semantics.
