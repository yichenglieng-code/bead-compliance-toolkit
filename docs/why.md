# Why this exists

## The problem

The federal BEAD program directs $42.45 billion toward building broadband to
unserved and underserved American locations. Money moves from NTIA to states, and
from states to subgrantees, most of them internet service providers. In exchange,
evidence has to move back the other way, continuously, for years.

Three parties produce and consume that evidence:

- **Equipment manufacturers** attest what they shipped, where it was made, and how
  it performed at end of line.
- **ISPs holding BEAD subgrants** demonstrate that the networks they built actually
  deliver the speed, latency, and reliability they committed to, per funded
  location.
- **State broadband offices**, the Eligible Entities, verify submissions and report
  up to NTIA on a semiannual cycle.

Nothing about the underlying facts is exotic. A location has an FCC Broadband
Serviceable Location ID, a status, and coordinates. A performance measurement has a
speed, a latency, a time, and a method. A component has an origin, a manufacturer,
and either a domestic-production certification or a waiver.

What is missing is a shared way to say any of it.

## What that costs

Today the exchange runs on bespoke spreadsheets, one-off export scripts, and manual
review. Every new pairing — this manufacturer with that ISP, that ISP with its state
office — tends to mean another custom parser and another round of email about what a
column meant.

Three consequences follow:

1. **Integration cost scales with the number of pairings, not participants.** N
   manufacturers and M ISPs produce something closer to N×M mappings than to N+M.
2. **The cost falls hardest where there is least capacity to absorb it.** A large
   carrier has a data engineering team. A rural cooperative building fifty towers
   does not, and every dollar it spends on reporting plumbing is a dollar not spent
   on towers. Grant money funds spreadsheets.
3. **Errors survive longer.** When validation is a human reading rows, mistakes
   reach the state office, and correcting them there costs a review cycle.

## The specific technical mistake this fixes

There is one error common enough, and consequential enough, to be worth naming.

BEAD performance compliance is not judged on averages. NTIA evaluates four
thresholds, each computed over a population of individual tests:

| Threshold | Rule |
|---|---|
| Download | 80% of measurements at or above 80% of required speed |
| Upload | the same, counted separately from download |
| Latency | 95% or more of round-trip measurements at or below 100 ms |
| Availability | average outage under 48 hours per 365 days |

Failing any one means non-compliance.

A reporting pipeline that records mean download speed and mean latency — the
intuitive design, and a common one — cannot evaluate a single one of those four
rules. Each needs a numerator and a denominator, not a central value.

And the failure is silent in the dangerous direction. `examples/walkthrough.md`
works through a case drawn from this repository's synthetic data where mean upload
is 17.90 Mbps against a 16 Mbps bar, comfortably clear, while only 59.52% of
individual upload tests clear that bar against a required 80%. The average says
pass. The network fails. On a contended shared-spectrum link, where the successful
tests run well above the bar and drag the mean up, this is not a contrived case.

So `performance_fact` carries the counts. That single decision is most of what this
toolkit contributes.

## The approach

An open, versioned data format with a reference implementation, and nothing else.

- **JSON Schema is normative.** The schemas stand alone and can be implemented in
  any language. The Python package is the first binding, not the definition.
- **Three fact families, one shape each.** Performance, location, BABA provenance.
  A manufacturer, an ISP, and a state office use the same shape for the same fact.
- **Vendor-neutral by construction.** Equipment is described by generic class and by
  FCC technology code, never by vendor product naming. A format the whole sector is
  meant to adopt cannot privilege one manufacturer's vocabulary.
- **Every requirement cited.** Encoded thresholds trace to a primary NTIA, FCC, or
  USAC source in [sources.md](sources.md), with a known-gaps section for what could
  not be verified rather than a guess dressed as a fact.
- **Local first.** v0.1 runs on files with no cloud dependency, so a small ISP can
  use it on a laptop. Streaming and warehouse scale-out belong in `patterns/` as the
  path up, not a precondition for getting value.
- **Synthetic data only.** No real subscriber or location data, ever.

## What success looks like

Not adoption metrics. Concretely:

1. A manufacturer exports once, and every downstream ISP can read it without a
   custom parser.
2. An ISP finds a threshold failure in July, while there is still a construction
   season left to fix it, instead of at a state office review in January.
3. A state broadband office validates a submitted bundle by running a command.
4. A small provider gets the same compliance posture as a large carrier on day one,
   because the tooling is free and the format is open.

## What this is not

- **Not a submission system.** NTIA designates the USAC PMM CSV format for actual
  submission, which is per-test rather than per-location-per-period. These schemas
  are the interchange layer above it. An emitter is on the roadmap.
- **Not a compliance determination.** `bead-data report` produces an *indicative*
  verdict from submitted data. The binding determination belongs to the Eligible
  Entity and NTIA, who also weigh testing methodology, sampling method, and
  transparency obligations no data file expresses.
- **Not a sampling validator.** Whether the right locations were randomly selected,
  and whether sample size matches active subscriber count, is outside what these
  records can prove.
- **Not affiliated with anyone.** Independent project, not endorsed by or sponsored
  by NTIA, the FCC, USAC, or any manufacturer or provider.

## Contributing

The schemas are early and almost certainly wrong in places only practitioners can
see. If you file BEAD reports, build equipment that feeds them, or review
submissions, [CONTRIBUTING.md](../CONTRIBUTING.md) explains what is most useful —
and concrete disagreement with a citation is the most useful thing of all.
