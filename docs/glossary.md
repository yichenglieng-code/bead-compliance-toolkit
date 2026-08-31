# Glossary

Most people arriving here are strong on software and new to broadband compliance, or
the reverse. This is the vocabulary the schemas use, in plain terms.

Authoritative definitions are in the primary sources cited in
[sources.md](sources.md). Where this page simplifies, that page governs.

## Programs and money

**BEAD** — Broadband Equity, Access, and Deployment. A $42.45 billion federal program
funding broadband construction to unserved and underserved locations. Money flows
NTIA → states → subgrantees.

**NTIA** — National Telecommunications and Information Administration, part of the
Department of Commerce. Administers BEAD and issues the policy notices this toolkit
encodes.

**Eligible Entity** — a state, territory, or the District of Columbia receiving BEAD
funds. Colloquially "the state broadband office". Selects subgrantees, reviews their
evidence, reports upward. **Makes the binding compliance determination**, which is why
everything this toolkit produces is labelled *indicative*.

**Subgrantee / subrecipient** — the organization that actually builds and operates the
network, usually an ISP. Produces most of the evidence these schemas carry.

**Funded Network** — a network built or upgraded with BEAD money. Only funded networks
are subject to the performance standards.

**Period of performance** — the window during which reporting obligations apply.
Distinct from the longer **Federal Interest Period**, during which the service
obligation continues.

**SAR** — Semiannual Report. The twice-yearly report an Eligible Entity submits to
NTIA. Performance results are summarized into the first SAR of the calendar year.

## Locations

**BSL** — Broadband Serviceable Location. A place where fixed broadband is or could be
installed. The unit BEAD money is accounted for in.

**Location Fabric / the Fabric** — the FCC dataset of every BSL in the United States.
Represents each as a single point inside a structure's footprint with a unique
**Location ID**.

**Location ID** — the FCC-issued identifier for a BSL. `location_ref` and `location_id`
in these schemas. Synthetic examples here use an obviously fake `BSL-1002…` prefix.

**HUBB** — High Cost Universal Broadband portal, where FCC high-cost programs report
deployment. Relevant only because the USAC submission template's first column is
labelled "HUBB Location ID", and NTIA directs that BEAD submissions put the **BSL**
identifier there instead, since funded locations have no HUBB ID.

**CAI** — Community Anchor Institution. A school, library, health clinic, and similar.
Judged against **1 Gbps symmetric** rather than 100/20 Mbps, so a CAI in a sample set
raises the bar for the whole set. The `is_cai` flag.

**BDC** — Broadband Data Collection. The FCC system where providers file availability
data. Source of the Fabric and the technology codes.

## Technology

**ngFWA** — next-generation fixed wireless access. Fixed wireless using modern radio
techniques to deliver service comparable to wired broadband. Common in rural BEAD
builds because it is cheaper to deploy than fiber over long distances.

**FCC technology code** — the FCC's numeric classification of how a location is
served. Matters because **NTIA separates sample sets by technology code**, so the code
decides which population a location is judged against. Fixed wireless splits into
three by spectrum licensing:

| Code | Meaning |
|---|---|
| 70 | unlicensed spectrum |
| 71 | licensed spectrum |
| 72 | licensed-by-rule, including CBRS general authorized access |

Full table in [schema_reference.md](schema_reference.md).

**CBRS** — Citizens Broadband Radio Service, shared spectrum in the 3.5 GHz band.
**GAA** (General Authorized Access) is its lowest tier: usable without a licence, and
shared, so performance degrades under contention. Code 72. The example data in this
repository fails its upload threshold on a CBRS sample set for exactly this reason.

**Base node / remote node / CPE** — vendor-neutral equipment classes. A base node
serves a sector from a tower; a remote node terminates the link at the premises; CPE
is customer premises equipment generally. Deliberately generic: no vendor vocabulary
belongs in a sector-wide format.

**ONT** — Optical Network Terminal, the device terminating fiber at a premises. Named
because NTIA lists ONT-based measurement as an acceptable method.

**TR-069 / CWMP / TR-369 / USP** — Broadband Forum protocols for managing customer
premises equipment remotely. NTIA lists them as acceptable ways to run performance
tests, because they impose no burden on the subscriber and collect no user data.

**IXP** — Internet Exchange Point. Performance tests must measure to a server at or
reached through an **FCC-designated** IXP, so results reflect the provider's network
rather than the wider internet.

## Measurement

**Test** — one discrete observation of speed or latency, from a subscriber's premises
to a remote server. The `performance_test` schema. This is the unit NTIA judges.

**Sample set** — test subjects in one state or territory, served by one provider, on
one technology, under one committed speed tier. **Compliance is evaluated per sample
set**, and sets are judged independently, so one can fail while another passes.

**Test subject** — a randomly selected active subscriber participating in testing.
Random selection is required so providers cannot pick their best-performing customers.

**Committed speed tier** — the lowest download/upload combination a subgrantee
committed to in its subgrant agreement. May not fall below 100/20 Mbps.

**Required speed** — the greater of the program floor and the committed tier. The
threshold is then 80% *of that*.

**The 80/80 rule** — 80% of measurements must reach 80% of the required speed.
Download and upload are counted **separately** and each must satisfy it alone. For a
100/20 commitment the working bars are 80 Mbps and 16 Mbps.

**Crosstalk / cross-traffic** — the subscriber's own traffic during a test. Above 10%
of the committed speed in the direction under test, a provider may defer the test and
report that none completed for that hour. Recorded here as `not_run_crosstalk`.

**Lost-packet test** — a latency test where packets did not return. Must be recorded
and **may not be discarded**; it counts as a discrete test that did not meet the
standard. Represented as a successful test with `packets_received` of 0 — the test
ran, it just failed.

**Availability** — outage time. The standard is an average under 48 hours per 365
days, about 99.45% uptime. Excludes published maintenance, announced scheduled
maintenance, subscriber power failures, subscriber equipment disconnection, and
declared disaster periods.

**PMM** — Performance Measurement Module. The USAC system and CSV templates NTIA
designates for submitting results. What `bead-data submit` produces.

**USAC** — Universal Service Administrative Company. Administers FCC universal service
programs and publishes the PMM templates.

## Provenance

**BABA** — Build America, Buy America. Requires iron, steel, manufactured products,
and construction materials in federally funded infrastructure to be produced in the
United States, unless waived.

**Manufactured product** — produced in the US when manufactured in the US *and* more
than 55% of component cost is US-origin, though NTIA waived the 55% test for certain
BEAD equipment.

**The two compliance paths** — the distinction the `baba_evidence` schema is built
around. A component travels exactly one:

- **Domestic certification** — equipment requiring domestic production, backed by a
  manufacturer's certification letter the subgrantee retains.
- **Waiver** — equipment covered by a BABA waiver, reported instead through a waiver
  tracker of finished waived electronics.

NTIA states a certification letter is **not needed** for waived equipment, which is
why the paths are mutually exclusive rather than merely different.

**Waiver types** — *public interest*; *nonavailability*, where domestic products are
not available in sufficient quantity or quality; *unreasonable cost*, where domestic
sourcing would raise project cost by more than 25%; plus program-wide and de minimis
waivers.

**HS code** — Harmonized System code classifying a traded product. The waiver tracker
requires 10 digits.

## This project's own terms

**Fact** — one record in one of the schema families. Carries `provenance` and a
`schema_version`.

**Derived vs asserted counts** — an asserted count is one a submitter wrote down; a
derived count is computed from raw observations by `bead-data aggregate`. Derived
counts matter because a **filtered denominator** becomes arithmetically impossible
rather than merely prohibited.

**Filtered denominator** — the failure this toolkit exists to catch: dropping failed
measurements before aggregating, so a pass rate looks better than reality. Detectable
because a passing count then exceeds its total.

**Indicative verdict** — what `report` produces. What the submitted data implies. The
binding determination belongs to the Eligible Entity and NTIA, who also weigh testing
methodology and sampling that no data file expresses.

**Conformance vector** — one test case in [../conformance/](../conformance/README.md):
an instance, whether it must validate, and which fields a conforming implementation
should blame.
