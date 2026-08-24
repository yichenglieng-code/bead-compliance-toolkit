# Walkthrough: manufacturer to ISP to state broadband office

This follows one batch of evidence through the three parties BEAD reporting
actually involves. Every file used here is in this directory, every number is
synthetic, and every command is runnable from a fresh clone.

All data is fabricated. Locations use an obviously fake `BSL-100200xxxx` pattern;
organizations are named "Example ...". No real subscriber, location, provider, or
manufacturer data appears anywhere in this repository.

To regenerate the files deterministically:

```bash
python examples/generate_examples.py
```

## The cast

| Party | Wants | File here |
|---|---|---|
| **Example Broadband Equipment Co.**, a fixed wireless manufacturer | to hand downstream ISPs test results they can use without writing a parser | `synthetic_factory_export.csv` |
| **Example Rural ISP**, a BEAD subgrantee | to prove its funded network meets the four NTIA thresholds | `synthetic_field_telemetry.json`, `synthetic_locations.json` |
| **The state broadband office**, an Eligible Entity | to check a submitted bundle without hand-inspecting it | runs `validate` and `report` on everything |

---

## Step 1 — The manufacturer exports factory test results

End-of-line verification produces one record per unit. The manufacturer's export
lands as CSV, because that is what came out of the test rig.

```bash
bead-data validate examples/synthetic_factory_export.csv
```

```text
20 valid, 0 invalid
```

Note what the manufacturer did *not* have to decide: how to name the speed fields,
whether latency means idle or loaded, how to express which spectrum the unit uses.
The schema settled all of that. The `technology_code` of `71` says licensed
terrestrial fixed wireless in the FCC's own vocabulary, so nobody downstream has to
guess what "FWA" meant.

### When the export is broken

`synthetic_factory_export.invalid.csv` is the same export with three rows broken on
purpose, one per class of failure:

```bash
bead-data validate examples/synthetic_factory_export.invalid.csv
```

```text
record 2: latency_tests_at_or_below_100ms: latency_tests_at_or_below_100ms (3020) must not exceed latency_tests_total (2520)
record 4: measurement_method: 'speedtest' is not one of ['cwmp_tr069', 'tr369_usp', 'gateway_software', 'ont_cpe_builtin', 'dedicated_measurement_device', 'other']
record 6: uptime_pct: 104.5 is greater than the maximum of 100
3 valid, 3 invalid
```

Exit code is `1`. Each failure is worth understanding, because each is a mistake
real reporting makes:

1. **Row 2** claims more passing latency tests than tests conducted. Arithmetically
   impossible, and it is the signature of a filtered denominator. NTIA forbids
   deleting, trimming, or excluding measurements, and specifically requires
   lost-packet tests to be counted as tests that did not meet the standard. A
   pipeline that drops failures produces exactly this record.
2. **Row 4** uses `speedtest`, which is the intuitive answer and the wrong one.
   NTIA requires *active measurement* and names the acceptable mechanisms. A
   third-party web speed test is not among them.
3. **Row 6** reports 104.5% uptime. Obvious in isolation, easy to miss in row 6 of
   2,000.

## Step 2 — The ISP normalizes its own field telemetry

The ISP's measurement week produces its own facts, in JSON this time.

```bash
bead-data validate examples/synthetic_field_telemetry.json
```

```text
10 valid, 0 invalid
```

Same schema, different container, no conversion needed to compare them. If the ISP
wants everything in one shape for its warehouse:

```bash
bead-data convert examples/synthetic_factory_export.csv --to json -o /tmp/factory.json
bead-data convert examples/synthetic_field_telemetry.json --to parquet -o /tmp/telemetry.parquet
```

Conversion validates before writing. An invalid input writes nothing and exits `1`,
so a bad batch fails on the ISP's machine rather than at the state office.

Round trips are lossless: a record that goes JSON to CSV to JSON comes back
identical, including which optional fields were absent. Integer counts stay
integers through Parquet rather than becoming `42.0`.

## Step 3 — Assemble the bundle

```bash
mkdir -p /tmp/bead-submission
cp examples/synthetic_field_telemetry.json /tmp/bead-submission/
cp examples/synthetic_locations.json /tmp/bead-submission/
cp -r examples/synthetic_baba_bundle /tmp/bead-submission/
```

Three kinds of evidence now sit together: performance facts, the funded-location
roster, and BABA provenance. The BABA bundle has five components — four on the
domestic certification path, one on the waiver path — mirroring the two-path NTIA
framework.

## Step 4 — The state broadband office checks it

First, is it even well-formed?

```bash
bead-data validate /tmp/bead-submission
```

```text
/tmp/bead-submission/synthetic_baba_bundle/aggregation_switch_s48.json [baba]
/tmp/bead-submission/synthetic_baba_bundle/base_node_b200.json [baba]
...
29 valid, 0 invalid
```

The schema of each file is detected from its fields, so the reviewer does not have
to tell the tool what it is looking at.

Then, what does the data say?

```bash
bead-data report /tmp/bead-submission --period 2026-Q3
```

### The interesting part

```text
| Sample set   | Tech code | Committed | Locations | Indicative verdict |
|--------------|-----------|-----------|-----------|--------------------|
| NV-71-100x20 | 71        | 100/20    | 6         | **PASS**           |
| NV-72-100x20 | 72        | 100/20    | 4         | **FAIL**           |
```

Two sample sets, because NTIA separates them by technology: `71` is licensed
spectrum, `72` is licensed-by-rule spectrum such as CBRS general authorized access.
They are judged independently, and here they diverge.

The licensed set clears everything:

```text
| Threshold                                | Observed                        | Required      | Verdict |
|------------------------------------------|---------------------------------|---------------|---------|
| Download (at or above 80 Mbps)           | 96.83% (244 of 252 tests)       | at least 80%  | PASS    |
| Upload (at or above 16 Mbps)             | 96.83% (244 of 252 tests)       | at least 80%  | PASS    |
| Latency (at or below 100 ms)             | 99.05% (14,977 of 15,120 tests) | at least 95%  | PASS    |
| Availability (outage hours per 365 days) | 17.1 h mean across 6 location(s)| under 48 h    | PASS    |
```

The CBRS set does not:

```text
| Threshold                                | Observed                        | Required      | Verdict |
|------------------------------------------|---------------------------------|---------------|---------|
| Download (at or above 80 Mbps)           | 90.48% (152 of 168 tests)       | at least 80%  | PASS    |
| Upload (at or above 16 Mbps)             | 59.52% (100 of 168 tests)       | at least 80%  | FAIL    |
| Latency (at or below 100 ms)             | 96.72% (9,749 of 10,080 tests)  | at least 95%  | PASS    |
| Availability (outage hours per 365 days) | 35.6 h mean across 4 location(s)| under 48 h    | PASS    |
```

**Upload fails at 59.52% against a required 80%.** Three things about that are
worth drawing out, because they are the whole argument for this schema:

1. **Averages would have hidden it.** Mean upload across the failing set is
   **17.90 Mbps**, above the 16 Mbps bar. The set fails anyway, because the rule is
   about the *share of measurements* clearing the bar, not the average. On a bursty
   contended link the successful tests run far enough above the bar to drag the
   average over it while most tests still fall short. A report built on means would
   have shown a passing number for a failing network. This is the entire reason
   `performance_fact` carries test counts.

2. **Download passing is irrelevant to upload.** NTIA counts the two directions
   separately and each must independently clear 80/80. Strong download cannot
   offset weak upload, and a combined "speed" metric would have obscured this.

3. **One failed threshold is enough.** Three of four passed. The sample set is
   still non-compliant, because a provider fails if it misses any of the four.

The failure mode is also realistic: CBRS is shared spectrum, so upload suffers
first under contention. That is the kind of problem worth finding in July, while
there is still time to add capacity, rather than in the state office's review.

### The rest of the report

Location progress, rolled up by build status:

```text
| Service status     | Locations | Share |
|--------------------|-----------|-------|
| planned            | 2         | 14.3% |
| under_construction | 2         | 14.3% |
| installed          | 3         | 21.4% |
| active             | 6         | 42.9% |
| suspended          | 1         | 7.1%  |

Built (installed or active): **9 of 14** (64.3%).
```

BABA coverage, split by the path each component travels:

```text
| Compliance path                              | Records | Share | Units |
|----------------------------------------------|---------|-------|-------|
| Domestic certification (manufacturer letter) | 4       | 80.0% | 350   |
| Waiver (reporting tracker)                   | 1       | 20.0% | 6     |
| **Total**                                    | **5**   | 100%  | **356**|
```

Plus units by country of origin, which is the visibility the waiver reporting
tracker exists to give NTIA, and a note that one record carries neither an
attestation digest nor a document URI. That record is valid — the fields are
optional — but a reviewer cannot tie it to a retained document, which is worth
knowing before the review rather than during it.

## What the reviewer did not have to do

No custom parser. No agreeing on field names with each submitter. No hand-checking
whether 59.52% clears 80%. No wondering whether the submitter quietly dropped
failing tests, because the denominators are in the data and a cross-field rule
rejects a filtered one.

## Honest limits

- The verdict is **indicative**. The binding determination belongs to the Eligible
  Entity and NTIA, who also weigh testing methodology, sampling method, and
  transparency obligations that no data file expresses.
- NTIA designates the USAC PMM CSV format for actual submission, which is per-test
  rather than per-location-per-period. These schemas are the interchange layer
  above that. An emitter for the USAC format is on the roadmap.
- Sampling is not validated here. Whether the right locations were randomly
  selected, and whether the sample size matches the active subscriber count, is
  outside what these records can prove.

Thresholds used above are cited to primary sources in
[`../docs/sources.md`](../docs/sources.md).
