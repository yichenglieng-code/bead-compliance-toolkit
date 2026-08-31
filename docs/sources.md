# Sources

Every federal program requirement encoded in these schemas traces to a primary
source below. Nothing about BEAD, BABA, or FCC reporting is asserted on this
project's own authority.

Sources were read and the schemas checked against them on **2026-08-31**. Federal
reporting rules change; if you are relying on this toolkit for a live filing,
re-check the primary sources and please open an issue if something here has gone
stale.

This page summarizes and paraphrases the sources. Where a number matters, the
number is stated with its source. For the binding text, read the source.

## Primary sources

| # | Source | Publisher | Version / date |
|---|---|---|---|
| S1 | [BEAD Program: Performance Measures for BEAD Last-Mile Networks](https://broadbandusa.ntia.gov/sites/default/files/2025-09/Performance_Measures_Policy_Notice.pdf) (Policy Notice) | NTIA | v1.0, September 19, 2025 |
| S2 | [Build America, Buy America Compliance and Documentation Requirements and Procedures](https://broadbandusa.ntia.gov/sites/default/files/2025-10/NTIA_BABA_Compliance_and_Reporting_Requirements.pdf) | NTIA | October 2025 |
| S3 | [Fixed Technology Codes](https://help.bdc.fcc.gov/hc/en-us/articles/5290793888795-Fixed-Technology-Codes) | FCC, Broadband Data Collection | updated February 28, 2025 |
| S4 | [What is the Location Fabric?](https://help.bdc.fcc.gov/hc/en-us/articles/5375384069659-What-is-the-Location-Fabric) and [What a Broadband Serviceable Location Is and Is Not](https://help.bdc.fcc.gov/hc/en-us/articles/16842264428059-About-the-Fabric-What-a-Broadband-Serviceable-) | FCC, Broadband Data Collection | 2025 |
| S5 | [PMM Data Formatting Guide](https://www.usac.org/wp-content/uploads/high-cost/documents/Tools/PMM-Data-Formating-Guide.pdf) | USAC | current as retrieved |
| S6 | [Anticipated Post-Final Proposal BEAD Semiannual Report Requirements](https://broadbandusa.ntia.doc.gov/sites/default/files/2024-12/BEAD_Anticipated_SAR_Reporting_Requirements_Guidance_v1.3.pdf) | NTIA | v1.3, December 2024 |

## What each encoded requirement rests on

### Performance thresholds

| Encoded as | Requirement | Source |
|---|---|---|
| `committed_down_mbps` minimum 100, `committed_up_mbps` minimum 20 | A committed speed tier may not fall below 100 Mbps down and 20 Mbps up. Required speed is the greater of that floor and whatever the subgrantee agreement commits to. | S1 §2(c), §3.12 |
| `is_cai` | Community anchor institutions carry a 1 Gbps symmetric standard rather than 100/20 Mbps. | S1 §1 |
| `download_tests_meeting_threshold` / `download_tests_total`, and the upload pair | Speed compliance requires 80 percent of measurements at or above 80 percent of the required speed. Download and upload are counted separately and each must independently satisfy the standard. For a 100/20 commitment the working figure is 80/16 Mbps. | S1 §3.12, §5 |
| `latency_tests_at_or_below_100ms` / `latency_tests_total` | Latency compliance requires 95 percent or more of round-trip measurements at or below 100 ms, measured to a server at or reached through an FCC-designated internet exchange point. | S1 §1, §3.11, §5 |
| `latency_tests_total` includes lost-packet tests | Providers must record observed latency for all measurements including lost-packet tests, and may not discard them, because they count as discrete tests that do not meet the standard. | S1 §3.11 |
| `outage_hours_365d` threshold of 48, `uptime_pct` of about 99.45 | Outages should not exceed, on average, 48 hours over any 365-day period, which NTIA states corresponds to roughly 99.45 percent annual uptime. | S1 §3.13, §5 |
| Exclusions noted in the `outage_hours_365d` description | Published standing maintenance windows, scheduled maintenance announced in advance, subscriber power failures, subscriber disconnection of equipment, and periods covered by an FCC DIRS activation or a FEMA declared disaster are excluded from outage totals. | S1 §3.13 |
| `measurement_method` enum | Metrics must come from active measurement, meaning devices or software sending packets to servers at the provider network edge, rather than from classical network management systems. Permitted approaches include CWMP TR-069, TR-369 USP, software on a supplied residential gateway, capability built into an ONT or other CPE, and dedicated measurement devices. | S1 §3.6 |
| The four-threshold framing in `report` output | A provider is non-compliant if it fails any of the four thresholds — download, upload, latency, or availability — for any applicable speed tier and technology. | S1 §5 |
| `sample_set_id`, `state_or_territory` | A sample set is the collection of test subjects within one state or territory, served by one provider, on one technology, under one committed speed tier. Compliance is judged per sample set. | S1 §2(e), §3.3 |
| `sample_population_active_subscribers`, `active_subscriber_count` rationale | Sample size is based on active subscribers to plans meeting or exceeding the committed speed tier, counted across all of one subgrantee's BEAD-funded projects in the state or territory for that technology and tier. Five or fewer means test all; 6 through 50 means test 5; 51 through 500 means test at least 10 percent; above 500 means test 50. Larger samples are permitted, but every included location's results must be reported. | S1 §3.2–§3.3 |
| `period_start` / `period_end` | Speed and latency testing runs for one week, by default one measurement period per year, during testing hours of 6:00 pm to 12:00 am local time including weekends. | S1 §3.5, §3.7 |

### Technology codes

`technology_code` on both `performance_fact` and `deployment_location` uses the FCC
fixed technology codes verbatim (S3): 0 other, 10 copper wire, 40 coaxial cable or
HFC, 50 fiber to the premises, 60 geostationary satellite, 61 non-geostationary
satellite, 70 unlicensed terrestrial fixed wireless, 71 licensed terrestrial fixed
wireless, 72 licensed-by-rule terrestrial fixed wireless.

NTIA treats technologies as different when their FCC technology codes differ, which
is why sample sets separate on this field (S1 §3.3). Next-generation fixed wireless
access deployments fall under 70, 71, or 72 depending on spectrum.

### Location identity

`location_ref` and `location_id` hold an FCC Broadband Serviceable Location (BSL)
Location ID from the FCC Location Fabric. The Fabric represents each BSL as a
single point defined by coordinates falling within a structure's footprint, and
assigns it a unique Commission-issued Location ID (S4).

For BEAD performance submissions specifically, NTIA notes that funded network
locations have no HUBB Location ID, so the BSL identifier occupies the first column
of the submitted results file (S1 §5).

### BABA evidence

The `compliance_path` discriminator exists because NTIA runs a two-part framework
and each path calls for different fields (S2).

| Path | Substantiated by | Fields this schema requires |
|---|---|---|
| `domestic_certification` | Manufacturer's BABA certification letter, furnished to the subgrantee and retained for the state broadband office or NTIA on request | `certification_ref`, `manufacturing_location`; plus `component`, `component_description`, `quantity` from the letter's key elements, and optional `requirement_ref` and `certifying_representative` |
| `waiver` | Waiver reporting tracker of finished waived electronics, compiled by the subgrantee, shared with the state broadband office, and reaching NTIA through semiannual reports | `waiver_ref`, `hs_code_10`, `product_identifier`, `product_category`; plus `manufacturer_name`, `component_description`, `origin_country`, `quantity` from the tracker's key elements |

The paths are mutually exclusive because NTIA states that a certification letter is
not needed for waived equipment (S2).

`waiver_type` reflects the statutory bases: a public interest waiver, a
nonavailability waiver where domestic products are not available in sufficient and
reasonably available quantities or satisfactory quality, and an unreasonable cost
waiver where domestic sourcing would raise total project cost by more than 25
percent. Program-wide and de minimis waivers are also represented (S2).

For context on the underlying standard, a manufactured product counts as produced
in the United States when it was manufactured in the United States and the cost of
its US-origin components exceeds 55 percent of total component cost, though NTIA
waived the 55 percent component-cost test for certain BEAD equipment (S2, citing
2 CFR §184.6).

### Provenance

The required `provenance` block reflects the NTIA transparency requirement that
subgrantees document the methodology, standards, and parameters used to measure
performance, provide that documentation with each submission along with a change
log of material changes, publish testing methodology on their network management
practices page, and certify the accuracy of what is reported (S1 §4).

`methodology_ref` is the field that links an individual fact to that published
disclosure.

## Known gaps and open questions

These are unresolved rather than quietly guessed at:

1. **Sampling provenance.** The toolkit checks the section 3.2 arithmetic against
   `sample_population_active_subscribers`. It cannot prove the reported population
   is complete or that locations were selected randomly; the generated submission
   manifest keeps the random-selection method as an explicit human-supplied item.
2. **BSL Location ID format.** The Fabric assigns unique Commission-issued Location
   IDs (S4), but this project has not found a published constraint on their lexical
   form, so `location_id` validates only as a non-empty string. Tightening this
   would need an authoritative format statement.
3. **Restructuring.** The BEAD program was restructured in 2025 and the FAQ document
   has been revised repeatedly since. The thresholds cited above come from the
   September 2025 performance measures notice and the October 2025 BABA document,
   which are the most recent versions located. Confirm against the current NOFO and
   FAQ before relying on them.
4. **State-level variation.** Eligible Entities may impose additional detail in
   subgrantee agreements, though they may not change what NTIA requires (S1 §3.15).
   State-specific extensions are out of scope for v0.

## Attribution

The NTIA, FCC, and USAC documents cited above are U.S. government works or are
published by their issuers for public use. Content on this page has been rephrased
and condensed for compliance with content-licensing restrictions; consult the
primary sources for authoritative text.

This project is independent and is not affiliated with, endorsed by, or sponsored
by NTIA, the FCC, USAC, or any equipment manufacturer or service provider.
