# Factory test orchestration for broadband equipment

Patterns for running end-of-line test on radio hardware at production volume, and
for getting the resulting data into a shape that survives the trip downstream.

This is a patterns document, not an implementation. It describes shapes that
generalize across manufacturers, deliberately at the level of "here is the
constraint and here is what it forces", because the specific orchestrator, message
bus, and warehouse you pick matter far less than getting these five decisions right.

Vendor-neutral throughout. No product names, no company-specific processes.

## Why factory data is the upstream half of BEAD compliance

A fixed wireless radio is tested several times before it reaches a tower: board
level, after assembly, after calibration, and in final functional test. Those
results are the earliest performance evidence that exists for a device, produced
months before the unit ever carries subscriber traffic.

Two audiences want that data, and they want different things:

- **Manufacturing** wants yield, drift, and station health, in near real time,
  because a calibration station going out of tolerance at 06:00 is a scrap pile by
  noon.
- **Downstream compliance** wants a durable, attributable record that a specific
  unit met specification, keyed so it can be joined to a funded location years
  later.

Most factory data platforms are built for the first audience and retrofitted for
the second. The retrofit is where the pain lives, because the second audience needs
identity and provenance decisions that have to be made at capture time and cannot
be reconstructed afterward.

## Constraint: the factory floor is not a datacenter

Everything below follows from this. A test cell is a machine on a factory network,
often on the far side of a link you do not control, sometimes in a building with
scheduled power interruptions, usually operated by people whose job is throughput
rather than data hygiene.

Concretely:

- **The network is not reliable and not fast.** Uplink from a plant to a cloud
  region may be a business broadband line shared with everything else on site.
- **Test cells cannot block on the cloud.** If a station stalls waiting for an API,
  the line stops. Throughput loss is measured in units per hour and noticed
  immediately.
- **Clocks drift.** Station clocks are frequently wrong, sometimes by hours.
- **Software versions diverge.** A plant will run three versions of a test sequence
  simultaneously because one cell was down during the last rollout.
- **The plant is not yours.** Contract manufacturing means limited physical access,
  limited network control, and change windows negotiated in advance.

A platform designed as though the factory were a datacenter fails on the first bad
uplink day, and it fails in the worst way: silently dropping results while the line
keeps running.

## Pattern 1 — Buffer at the edge, always

Every test cell writes results locally first, to durable storage, and a separate
process ships them. The test sequence's completion never depends on the shipper
succeeding.

This inverts the intuitive design, where the test uploads its own result. That
version couples line throughput to network health, and the coupling is discovered
during an outage rather than during design.

What the buffer needs:

- **Durability across power loss.** Append to disk and fsync before reporting the
  test complete. A result that exists only in memory does not exist.
- **A bounded, monitored queue.** Depth is one of the most useful health signals in
  the whole system: a rising queue means the uplink is degraded, hours before
  anyone reports a problem.
- **At-least-once delivery with idempotent keys.** See pattern 2.
- **Backpressure that degrades gracefully.** When the buffer approaches its limit,
  shed the least valuable data first — verbose traces before pass/fail records —
  rather than dropping uniformly or blocking.

The shipper should batch and compress. Individual test records are small and
numerous, and per-record round trips over a constrained uplink waste most of the
link on protocol overhead.

## Pattern 2 — Decide identity at capture time

The single most consequential decision, and the one most often deferred until it is
expensive.

Every test result needs a stable, globally unique identifier assigned **at the
station, at capture**, not by the ingest tier on arrival. Ingest-assigned ids make
retries indistinguishable from genuine duplicates, which means you cannot safely
retry, which means at-least-once delivery is unavailable, which means you drop data
on network failures.

A test result should carry:

| Identity element | Why |
|---|---|
| Result id, generated at the station | idempotency key for retries and deduplication |
| Device serial | joins every test of one unit across its whole history |
| Station id | isolates a drifting or miscalibrated cell |
| Test sequence name and **version** | results are only comparable within a version |
| Station-local timestamp **and** a monotonic sequence number | see below |
| Operator or shift identifier, where policy permits | correlates human factors with yield |

On clocks: station wall-clock time is untrustworthy, but ordering within a station
matters for drift analysis. Carry both a wall-clock timestamp and a monotonically
increasing per-station counter. The counter gives you reliable ordering; the
timestamp gives you approximate absolute time; disagreement between them tells you
a clock was corrected. Do not overwrite the station timestamp with ingest time.
Record both and keep them distinguishable — the gap between them is a measurement
of your own pipeline's health.

## Pattern 3 — Separate the streams by urgency, not by source

Factory test data splits naturally into three flows with genuinely different
requirements, and conflating them means over-engineering one or under-serving
another.

| Flow | Latency need | Volume | Retention |
|---|---|---|---|
| Pass/fail and key parametrics | seconds to minutes | low | years |
| Full parametric measurements | minutes to hours | medium | months to years |
| Raw traces and captures | best effort | very high | days to weeks |

The first flow drives the line-stop decision, so it gets the reliable path and the
tight alerting. The third is enormous, rarely read, and mostly useful for
post-failure forensics; putting it through the same reliable path is how a pipeline
ends up expensive and slow at the same time.

A single logical schema with tiered payloads works well: a compact record that
always ships, carrying a reference to bulky artifacts that ship on a lazier path or
are fetched on demand.

## Pattern 4 — Version the test sequence in the data, and treat it as a schema

A parametric limit change makes yesterday's results incomparable to today's. If the
sequence version is not in every record, you will eventually compute a yield trend
across a limit change and reach a confident wrong conclusion.

Treat test sequence definitions with the discipline normally reserved for API
schemas:

- **Version explicitly**, and stamp the version into every result.
- **Additive changes are cheap; redefinitions are not.** Adding a new measurement is
  a minor version. Changing a limit, a unit, or the meaning of an existing
  measurement is a breaking change and needs a new major version, not an edit.
- **Never reuse a measurement name with different semantics.** This is the factory
  equivalent of changing a field's type in a published schema, and it corrupts
  historical analysis silently.
- **Keep limits as data, not code.** Limits change more often than logic, they change
  through a different approval process, and they need their own audit trail.
- **Expect concurrent versions.** Multiple sequence versions run simultaneously
  during any rollout. The data model must represent that as a normal state, not an
  error.

## Pattern 5 — Make the compliance record a first-class output

This is the pattern most directly connected to the rest of this repository, and the
one most often bolted on late.

Manufacturing analytics and compliance evidence want different shapes. Analytics
wants wide, denormalized, cheap to scan. Compliance wants narrow, attributable,
durable, and joinable to a funded location years after the fact.

Build the compliance projection as a deliberate output of the pipeline rather than a
query someone writes later. It needs:

- **Provenance on every record.** Producing organization, producing system, and
  production time. Not reconstructable after the fact, which is why the
  [`provenance`](../schema_reference.md#provenance-shared) block in these schemas is
  required rather than optional.
- **Stable external identifiers.** Device serial is what lets a factory record join
  to a deployment record. Guard it accordingly.
- **Counts, not just aggregates.** Where a compliance threshold is defined over a
  population of measurements — as all four BEAD performance thresholds are — the
  projection must carry numerators and denominators. An average discards exactly the
  information the rule needs. This is the [central design point](../why.md) of the
  `performance_fact` schema.
- **Immutability and correction by supersession.** Never update a compliance record
  in place. Emit a correction that references what it supersedes, so the audit trail
  survives.
- **No confidential process detail.** A compliance record travels to parties outside
  the manufacturer. Yield rates, station identities, and internal limit values
  generally should not travel with it. Project deliberately, and decide what crosses
  the boundary at design time rather than at disclosure time.

The [`performance_fact`](../../schemas/performance/v0/performance_fact.schema.json)
schema in this repository is one such projection, with `device_class` kept
deliberately generic so no vendor vocabulary leaks into a sector-wide interchange
format.

## Scale-out path

v0.1 of this toolkit runs on files, with no cloud dependency, because that is the
smallest thing that is genuinely useful and a small ISP can run it on a laptop. The
path up, when volume justifies it:

```
test cells → local durable buffer → batching shipper
                                         ↓
                            ingest API (idempotent, keyed)
                                         ↓
                              append-only event log
                                    ↓         ↓
                    stream processing      raw landing zone
                    (yield, drift,         (traces, captures)
                     station health)
                          ↓                     ↓
                    operational alerts      warehouse tables
                                                ↓
                                    compliance projection
                                    (this repository's schemas)
                                                ↓
                                    validate → report → submit
```

Sequencing advice, in the order the constraints actually bite:

1. **Edge buffering and capture-time identity first.** These are the two decisions
   that are expensive to retrofit, because both change the data itself. Everything
   downstream is replaceable; the data you failed to capture is not.
2. **Append-only log second.** Once results land durably and in order, every
   consumer becomes independently rebuildable.
3. **Stream processing when someone is waiting on an answer.** Not before. Batch
   aggregation over the log answers most questions, and the operational cost of a
   streaming tier is real.
4. **The compliance projection whenever there is a downstream consumer**, which for
   BEAD-funded equipment is from the first shipment.

## Failure modes worth designing against

Each of these is a real class of failure that produces plausible, wrong data rather
than an obvious outage. Those are the expensive ones.

| Failure | Symptom | Guard |
|---|---|---|
| Filtered denominators | pass rates that look impossibly good | reject counts where the passing subset exceeds the total, as `performance_fact` does |
| Silent drop on uplink failure | yield appears to improve during an outage | monitor buffer depth and delivery lag as first-class metrics, alert on both |
| Clock correction | results reordered, negative durations | carry a monotonic sequence alongside wall-clock; never overwrite station time |
| Sequence version drift | yield trends that cross a limit change | version in every record; refuse cross-version aggregation |
| Duplicate ingest on retry | inflated volumes, double-counted failures | capture-time idempotency keys |
| Unit ambiguity | measurements off by 1000 | units in the schema, never implied by field name |
| Provenance added later | records that cannot be attributed on audit | make provenance required at capture |

## Relationship to this toolkit

This document is the upstream context for the schemas here. The toolkit does not
orchestrate factory tests, and does not try to: orchestration is specific to a
manufacturer's stations, sequences, and plant network in ways a shared library
cannot usefully abstract.

What is shared is the boundary. Once a factory produces a compliance projection, the
[`performance_fact`](../schema_reference.md#performance-fact) schema is a format for
it that downstream ISPs and state broadband offices can consume without a custom
parser. `examples/synthetic_factory_export.csv` shows that export shape, and
[`examples/walkthrough.md`](../../examples/walkthrough.md) follows it through to a
state office review.

If you run a factory data platform and these patterns are wrong, or missing
something that bit you, please open an issue. Direct experience is more valuable
here than more writing.
