# Schema field reference

<!-- GENERATED FILE - do not edit by hand.
     Run: python tools/gen_schema_reference.py
     The JSON Schemas under schemas/ are the source of truth. -->

Schema version **0.1.0**. JSON Schema draft 2020-12 is normative; the
pydantic models in `src/bead_data/models.py` are a reference binding that adds the
cross-field rules.

Every field below carries the reporting rationale for why it exists. The federal
requirement behind each one is cited to a primary NTIA, FCC, or USAC source in
[sources.md](sources.md) — nothing here is asserted on this project's own authority.

## Contents

- [Performance Fact](#performance-fact) — `--schema performance`
- [Deployment Location](#deployment-location) — `--schema location`
- [BABA Evidence](#baba-evidence) — `--schema baba`
- [Provenance (shared)](#provenance-shared)
- [FCC fixed technology codes](#fcc-fixed-technology-codes)
- [Cross-field rules](#cross-field-rules)
- [The four compliance thresholds](#the-four-compliance-thresholds)

---

## Performance Fact

`schemas/performance/v0/performance_fact.schema.json`

One funded location's network performance over one measurement period, carrying both the observed central values and the per-test counts that BEAD compliance is actually judged on. Rationale: NTIA judges BEAD last-mile performance on four thresholds evaluated over populations of discrete tests, not on averages. Speed compliance requires that 80 percent of download measurements land at or above 80 percent of the required download speed, and separately the same for upload. Latency compliance requires that 95 percent or more of round-trip latency measurements land at or below 100 milliseconds. Availability compliance requires that average outage time stay under 48 hours across a 365-day period, which corresponds to roughly 99.45 percent uptime. A record that reports only mean speed and mean latency cannot answer any of those four questions, so this schema carries the numerator and denominator for each.

16 required fields, 10 optional. `additionalProperties` is `false`: unknown fields are rejected, which keeps private extensions out of a format meant to be adopted sector-wide.

#### `schema_version`

**Required.** Type `"0.1.0"` (constant). Constraints: must equal `0.1.0`.

Version of this schema the record claims to conform to.

#### `fact_id`

**Required.** Type `string`. Constraints: pattern `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`; format `uuid`.

UUID v4 uniquely identifying this fact. Lets the same fact be de-duplicated after passing through a manufacturer, an ISP, and a state broadband office.

#### `location_ref`

**Required.** Type `string`. Constraints: non-empty.

Identifier of the BEAD location this measurement belongs to. For BEAD submissions this is the FCC Broadband Serviceable Location (BSL) Location ID from the FCC Location Fabric: NTIA directs that because funded locations have no High Cost Universal Broadband (HUBB) Location ID, the BSL identifier occupies the first column of the submitted results file. Synthetic examples in this repository use an obviously fake BSL- prefix.

Examples: `BSL-1002003004`

#### `state_or_territory`

**Required.** Type `string`. Constraints: pattern `^[A-Z]{2}$`.

Two-letter USPS code for the state or territory. Required because NTIA evaluates compliance and draws sample sets per state or territory, so facts cannot be pooled across state lines.

Examples: `NV`, `MO`, `CA`

#### `technology_code`

**Required.** Type `integer`. Constraints: one of `0`, `10`, `40`, `50`, `60`, `61`, `70`, `71`, `72`.

FCC fixed technology code for the technology serving this location. NTIA requires locations to be sampled separately per technology, and treats technologies as different when their FCC technology codes differ. Codes: 0 other, 10 copper wire, 40 coaxial cable or HFC, 50 fiber to the premises, 60 geostationary satellite, 61 non-geostationary satellite, 70 unlicensed terrestrial fixed wireless, 71 licensed terrestrial fixed wireless, 72 licensed-by-rule terrestrial fixed wireless. Next-generation fixed wireless access deployments generally fall under 70, 71, or 72.

#### `committed_down_mbps`

**Required.** Type `number`. Constraints: at least 100.

Committed download speed tier in Mbps for this project, from the subgrantee agreement. Floor of 100 comes from the NTIA definition of committed speed tier, which may not be less than 100 Mbps down and 20 Mbps up. Required speed is the greater of this value and 100.

#### `committed_up_mbps`

**Required.** Type `number`. Constraints: at least 20.

Committed upload speed tier in Mbps for this project, from the subgrantee agreement. Floor of 20 comes from the NTIA definition of committed speed tier.

#### `period_start`

**Required.** Type `string`. Constraints: format `date-time`.

ISO 8601 start of the measurement period. NTIA expects speed and latency testing across a one-week window, by default once per year.

#### `period_end`

**Required.** Type `string`. Constraints: format `date-time`.

ISO 8601 end of the measurement period. Must be at or after period_start.

#### `download_mbps`

**Required.** Type `number`. Constraints: at least 0.

Mean observed download speed in Mbps across successful tests in the period. Informational: NTIA compliance is decided by download_tests_meeting_threshold, not by this mean.

#### `upload_mbps`

**Required.** Type `number`. Constraints: at least 0.

Mean observed upload speed in Mbps across successful tests in the period. Informational, as with download_mbps.

#### `latency_ms_mean`

**Required.** Type `number`. Constraints: at least 0.

Mean observed round-trip latency in milliseconds across latency tests in the period. Informational: NTIA compliance is decided by latency_tests_at_or_below_100ms.

#### `latency_ms_loaded`

Optional. Type `number`. Constraints: at least 0.

Optional mean round-trip latency in milliseconds measured under load. NTIA removed the cross-traffic waiver for latency testing, so loaded latency is meaningful to record even though the compliance threshold does not distinguish it.

#### `download_tests_total`

Optional. Type `integer`. Constraints: at least 0.

Count of download tests observed in the period, including tests that failed to meet the threshold. NTIA forbids deleting, trimming, editing, or excluding test measurements, so this denominator should reflect every test.

#### `download_tests_meeting_threshold`

Optional. Type `integer`. Constraints: at least 0.

Count of download tests at or above 80 percent of the required download speed. Must not exceed download_tests_total. Compliance needs this to be at least 80 percent of the total.

#### `upload_tests_total`

Optional. Type `integer`. Constraints: at least 0.

Count of upload tests observed in the period. Upload and download are counted separately and each must independently satisfy the 80/80 standard.

#### `upload_tests_meeting_threshold`

Optional. Type `integer`. Constraints: at least 0.

Count of upload tests at or above 80 percent of the required upload speed. Must not exceed upload_tests_total.

#### `latency_tests_total`

Optional. Type `integer`. Constraints: at least 0.

Count of latency tests observed in the period. NTIA requires lost-packet tests to be recorded and counted as discrete tests that do not meet the standard, so they belong in this denominator rather than being discarded.

#### `latency_tests_at_or_below_100ms`

Optional. Type `integer`. Constraints: at least 0.

Count of latency tests with round-trip time at or below 100 milliseconds. Must not exceed latency_tests_total. Compliance needs this to be at least 95 percent of the total.

#### `uptime_pct`

**Required.** Type `number`. Constraints: at least 0; at most 100.

Observed availability for the period, as a percentage. The NTIA availability standard of no more than 48 outage hours over any 365-day period corresponds to about 99.45 percent.

#### `outage_hours_365d`

Optional. Type `number`. Constraints: at least 0.

Optional but recommended: total bona fide outage hours over the trailing 365 days. This is the quantity NTIA actually evaluates, with a threshold of 48 hours. Excluded from the total are published standing maintenance windows, scheduled maintenance announced to affected customers in advance, subscriber power failures, subscriber disconnection of equipment, and periods covered by an FCC Disaster Information Reporting System activation or a FEMA declared disaster.

#### `measurement_method`

**Required.** Type `string`. Constraints: one of `cwmp_tr069`, `tr369_usp`, `gateway_software`, `ont_cpe_builtin`, `dedicated_measurement_device`, `other`.

How the measurement was taken. NTIA requires active measurement, meaning devices or software sending packets to servers at the edge of the provider network, rather than readings drawn from classical network management systems. Permitted approaches: standardized CPE WAN Management Protocols TR-069 (cwmp_tr069) and TR-369 User Services Platform (tr369_usp), software on a supplied residential gateway (gateway_software), capability built into an optical network terminal or other customer premises equipment (ont_cpe_builtin), or a dedicated measurement device installed at the subscriber location (dedicated_measurement_device). NTIA encourages the gateway and CPE options because they impose no subscriber burden and need no subscriber consent, whereas separate measurement hardware does require consent.

#### `device_class`

**Required.** Type `string`. Constraints: one of `base_node`, `remote_node`, `cpe`, `other`.

Vendor-neutral class of equipment serving the location. Deliberately generic so that no vendor product naming leaks into an interchange format meant to be adopted sector-wide.

#### `sample_set_id`

Optional. Type `string`. Constraints: non-empty.

Optional grouping key for the sample set this fact belongs to. An NTIA sample set is the collection of test subjects within one state or territory, served by one provider, on one technology, under one committed speed tier. Compliance is evaluated per sample set, so carrying the grouping key makes aggregation reproducible.

Examples: `NV-71-100x20-2026`

#### `is_cai`

Optional. Type `boolean`. Constraints: defaults to `false`.

Whether this location is a community anchor institution. CAIs carry a different NTIA service standard of 1 Gbps download and 1 Gbps upload, rather than the 100/20 Mbps standard for broadband serviceable locations.

#### `provenance`

**Required.** Shared object; see [Provenance](#provenance-shared) below.

---

## Deployment Location

`schemas/location/v0/deployment_location.schema.json`

One BEAD-funded location and where it sits in the build lifecycle. Rationale: BEAD money is awarded and accounted for at the location level, keyed to the FCC Broadband Serviceable Location Fabric, and buildout progress rolls up from locations through the subgrantee to the state broadband office and then to NTIA in semiannual reports. This schema is the shared unit for that roll-up, and it is also the join key for performance facts, which reference a location through location_ref.

8 required fields, 5 optional. `additionalProperties` is `false`: unknown fields are rejected, which keeps private extensions out of a format meant to be adopted sector-wide.

#### `schema_version`

**Required.** Type `"0.1.0"` (constant). Constraints: must equal `0.1.0`.

Version of this schema the record claims to conform to.

#### `location_id`

**Required.** Type `string`. Constraints: non-empty.

FCC Broadband Serviceable Location (BSL) Location ID from the FCC Location Fabric. Each BSL in the Fabric is a single point, defined by coordinates falling within a structure's footprint, carrying a unique Commission-issued Location ID. Synthetic examples in this repository use an obviously fake BSL- prefix so that no real address is implied.

Examples: `BSL-1002003004`

#### `state_or_territory`

**Required.** Type `string`. Constraints: pattern `^[A-Z]{2}$`.

Two-letter USPS code. NTIA evaluates and reports per state or territory.

#### `latitude`

**Required.** Type `number`. Constraints: at least -90; at most 90.

Decimal degrees. Should match the Fabric point for location_id.

#### `longitude`

**Required.** Type `number`. Constraints: at least -180; at most 180.

Decimal degrees. Should match the Fabric point for location_id.

#### `service_status`

**Required.** Type `string`. Constraints: one of `planned`, `under_construction`, `installed`, `active`, `suspended`.

Where this location sits in the build lifecycle. Distinguishing installed (service available at the location) from active (a subscriber is taking service) matters for BEAD reporting, because NTIA sample sizes are computed from active subscribers rather than from passed locations.

#### `install_date`

**Conditionally required** — when `service_status` is `installed` or `active`. Type `string`. Constraints: format `date`.

ISO 8601 date on which service became available at this location. Required when service_status is installed or active, because a location cannot be reported as built without a build date to substantiate milestone progress.

#### `technology_code`

**Required.** Type `integer`. Constraints: one of `0`, `10`, `40`, `50`, `60`, `61`, `70`, `71`, `72`.

FCC fixed technology code for the technology serving this location. See the performance_fact schema for the full code list. Deliberately carries no default: NTIA separates sample sets by technology code, so the code decides which population a location is judged against. Next-generation fixed wireless access builds use 70 for entirely unlicensed spectrum, 71 for licensed spectrum, or 72 for licensed-by-rule spectrum such as CBRS general authorized access, and defaulting to any one of the three would silently mislabel the other two.

#### `max_advertised_down_mbps`

Optional. Type `number`. Constraints: at least 0.

Optional maximum advertised download speed in Mbps offered at this location.

#### `max_advertised_up_mbps`

Optional. Type `number`. Constraints: at least 0.

Optional maximum advertised upload speed in Mbps offered at this location.

#### `is_cai`

Optional. Type `boolean`. Constraints: defaults to `false`.

Whether this location is a community anchor institution, which carries the 1 Gbps symmetric NTIA service standard instead of 100/20 Mbps.

#### `active_subscriber_count`

Optional. Type `integer`. Constraints: at least 0.

Optional count of active subscribers at this location. Feeds NTIA sample-size determination, which tests 5 locations when a sample population has 50 or fewer active subscribers, at least 10 percent when it has 51 through 500, and 50 locations once it exceeds 500.

#### `provenance`

**Required.** Shared object; see [Provenance](#provenance-shared) below.

---

## BABA Evidence

`schemas/baba/v0/baba_evidence.schema.json`

Build America, Buy America provenance for one component used in a BEAD-funded build. Rationale: NTIA operates a two-part compliance framework, and every component travels down exactly one of two paths. Equipment that requires domestic production is substantiated by a manufacturer's BABA certification letter, furnished to the subgrantee, which the subgrantee retains for the state broadband office or NTIA on request. Equipment covered by a BABA waiver is instead substantiated through a waiver reporting tracker of finished waived electronics, which the subgrantee compiles, shares with the state broadband office, and which reaches NTIA through semiannual reports. The two paths demand genuinely different fields, so this schema makes the path explicit in compliance_path and conditionally requires the fields that path needs.

10 required fields, 12 optional. `additionalProperties` is `false`: unknown fields are rejected, which keeps private extensions out of a format meant to be adopted sector-wide.

#### `schema_version`

**Required.** Type `"0.1.0"` (constant). Constraints: must equal `0.1.0`.

Version of this schema the record claims to conform to.

#### `evidence_id`

**Required.** Type `string`. Constraints: pattern `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`; format `uuid`.

UUID v4 uniquely identifying this evidence record.

#### `compliance_path`

**Required.** Type `string`. Constraints: one of `domestic_certification`, `waiver`.

Which NTIA compliance path substantiates this component. Use domestic_certification when the component requires domestic production and is backed by a manufacturer's BABA certification letter. Use waiver when the component is covered by a BABA waiver and is therefore reported through the waiver reporting tracker instead. NTIA states plainly that a certification letter is not needed for waived equipment, so the two paths are mutually exclusive.

#### `component`

**Required.** Type `string`. Constraints: non-empty.

Name of the device, subassembly, or material. Maps to Product Name in the manufacturer certification letter.

Examples: `Example FWA Remote Node R100`

#### `component_type`

**Required.** Type `string`. Constraints: one of `device`, `subassembly`, `iron_steel`, `construction_material`, `other`.

Broad BABA category. BABA reaches iron, steel, manufactured products, and construction materials used in a federally funded infrastructure project. device and subassembly are manufactured products; iron_steel and construction_material carry their own BABA treatment, including a Department-wide public interest waiver for minor components within iron and steel products.

#### `component_description`

**Required.** Type `string`. Constraints: non-empty.

Plain-language description of what the component is or does. Both NTIA artifacts require this: the certification letter asks for a product description, and the waiver reporting tracker asks for a common-language description of the product's function.

Examples: `Outdoor subscriber radio unit terminating the fixed wireless link at the customer premises.`

#### `product_category`

**Conditionally required** — on the `waiver` path. Type `string`. Constraints: one of `router`, `switch`, `radio`, `antenna`, `power_system`, `optical_transport`, `cable`, `enclosure`, `other`.

Category of electronic product. Required on the waiver path, where the NTIA reporting tracker asks for the category of electronic product using examples such as router, switch, power system, and radio.

#### `manufacturer_name`

**Required.** Type `string`. Constraints: non-empty.

Public legal name of the manufacturer. Required on both paths: the certification letter identifies the certifying manufacturer, and the waiver reporting tracker asks for the name of the manufacturer.

Examples: `Example Broadband Equipment Co.`

#### `origin_country`

**Required.** Type `string`. Constraints: pattern `^[A-Z]{2}$`.

ISO 3166-1 alpha-2 country of origin. Required on both paths. On the waiver path this is the field that gives NTIA visibility into the country of origin of finished waived electronics used in BEAD builds.

Examples: `US`, `MX`, `VN`

#### `quantity`

**Required.** Type `integer`. Constraints: at least 1.

Number of units covered by this evidence record. Required on both paths: the certification letter and the waiver reporting tracker both call for quantity.

#### `manufacturing_location`

**Conditionally required** — on the `domestic_certification` path. Type `string`. Constraints: non-empty.

Where manufacturing occurred. Required on the domestic_certification path, where the certification letter must state the location of manufacturing.

Examples: `Austin, Texas, United States`

#### `certification_ref`

**Conditionally required** — on the `domestic_certification` path. Type `string`. Constraints: non-empty.

Identifier of the manufacturer's BABA certification letter substantiating this component. Required on the domestic_certification path. The subgrantee retains the letter itself in case the state broadband office or NTIA requests it.

Examples: `CERT-2026-0417-A`

#### `requirement_ref`

Optional. Type `string`. Constraints: non-empty.

Reference to the specific BABA domestic manufacturing requirement being certified against, which is the first key element NTIA lists for the certification letter.

Examples: `BEAD BABA waiver, Section III.A.2.a (Electronics)`

#### `certifying_representative`

Optional. Type `string`. Constraints: non-empty.

Authorized company representative who signed the certification letter. Prefer a role title over a personal name when this record will be published.

#### `waiver_ref`

**Conditionally required** — on the `waiver` path. Type `string`. Constraints: non-empty.

Identifier of the BABA waiver covering this component. Required on the waiver path.

Examples: `BEAD-BABA-WAIVER-2024-02-23`

#### `waiver_type`

Optional. Type `string`. Constraints: one of `public_interest`, `nonavailability`, `unreasonable_cost`, `general_applicability`, `de_minimis`.

Statutory basis for the waiver. The Act contemplates a public interest waiver, a nonavailability waiver where domestic products are not produced in sufficient and reasonably available quantities or satisfactory quality, and an unreasonable cost waiver where domestic sourcing would raise total project cost by more than 25 percent. general_applicability covers program-wide waivers such as the BEAD electronics waiver, and de_minimis covers the Department-wide small-purchase and minor-component waivers.

#### `hs_code_10`

**Conditionally required** — on the `waiver` path. Type `string`. Constraints: pattern `^[0-9]{10}$`.

Ten-digit Harmonized System code. Required on the waiver path, where the NTIA reporting tracker specifies a 10-digit HS code.

Examples: `8517620090`

#### `product_identifier`

**Conditionally required** — on the `waiver` path. Type `string`. Constraints: non-empty.

Manufacturer's product identifier, such as a stock keeping unit, product ID, or part number. Required on the waiver path.

Examples: `EX-RN-R100-US`

#### `bead_project_ref`

Optional. Type `string`. Constraints: non-empty.

Optional identifier of the BEAD project this component was used in, so evidence can be filtered per project during a state broadband office review.

Examples: `NV-BEAD-2026-014`

#### `attestation_doc_sha256`

Optional. Type `string`. Constraints: pattern `^[0-9a-f]{64}$`.

Optional SHA-256 digest, lowercase hex, of the underlying certification letter or waiver document. Lets a reviewer confirm that the retained document is the one this record describes, without the document having to travel alongside the record.

#### `attestation_doc_uri`

Optional. Type `string`. Constraints: format `uri`.

Optional URI where the underlying document is retained.

#### `provenance`

**Required.** Shared object; see [Provenance](#provenance-shared) below.

---

## Provenance (shared)

`schemas/common/v0/provenance.schema.json`

Who produced a compliance fact, with what, and when. Required on every fact in this toolkit. Rationale: NTIA requires BEAD subgrantees to document the methodology, standards, and parameters used to produce performance evidence, to supply that documentation with each submission alongside a change log of material changes, and to certify the accuracy of what is reported. Evidence that travels between a manufacturer, an ISP, and a state broadband office is only auditable if it carries its own origin.

Required on all three fact families.

#### `source_org`

**Required.** Type `string`. Constraints: non-empty.

Organization that produced the fact (manufacturer, ISP/subgrantee, or testing vendor).

Examples: `Example Rural ISP`

#### `collected_by`

**Required.** Type `string`. Constraints: non-empty.

Person or system identifier that produced the fact. Prefer a system or service name over a named individual so records can be published without exposing personal data.

Examples: `mfg-exporter`, `field-telemetry-collector`

#### `collected_at`

**Required.** Type `string`. Constraints: format `date-time`.

ISO 8601 date-time at which the fact was produced.

#### `tool`

Optional. Type `string`. Constraints: non-empty.

Producing tool and version. Supports the NTIA transparency requirement to describe the software and systems used in testing.

Examples: `bead-data 0.1.0`

#### `methodology_ref`

Optional. Type `string`. Constraints: non-empty.

Pointer to the published testing methodology, standards, and parameters this fact was produced under. NTIA requires subgrantees to publish testing methodology on their network management practices page; this field links a fact to that disclosure.

Examples: `https://example-isp.example/network-management-practices#bead-testing-v3`

In CSV and Parquet, provenance flattens to `provenance.`-prefixed columns and nests again on read.

---

## FCC fixed technology codes

Used by `technology_code` on both `performance_fact` and `deployment_location`.
These are the FCC's own codes, reproduced so the meaning of the field is
unambiguous.

NTIA treats technologies as different when their FCC technology codes differ, and
sample sets are separated on that basis. The code therefore decides which
population a location is judged against, which is why the field carries no default.

| Code | Name | Covers |
|---|---|---|
| `0` | Other | Any fixed technology not covered by another code |
| `10` | Copper wire | DSL, ethernet over copper, T-1 |
| `40` | Coaxial cable / HFC | DOCSIS and hybrid fiber-coaxial |
| `50` | Fiber to the premises | Fiber to the home or business; excludes fiber to the curb |
| `60` | Geostationary satellite | Fixed service over geostationary orbit |
| `61` | Non-geostationary satellite | Fixed service over low or medium earth orbit |
| `70` | Unlicensed terrestrial fixed wireless | Entirely unlicensed spectrum |
| `71` | Licensed terrestrial fixed wireless | Entirely licensed spectrum, or a hybrid including licensed-by-rule |
| `72` | Licensed-by-rule terrestrial fixed wireless | CBRS general authorized access and similar |

Next-generation fixed wireless access deployments generally fall under `70`, `71`,
or `72`, depending on spectrum.

---

## Cross-field rules

Rules spanning more than one field. Implemented in the pydantic models, and in the
JSON Schema through conditional `allOf` blocks where it can express them. Each has
a dedicated test.

**Performance Fact** — `period_end` must be at or after `period_start`

> A measurement period that ends before it starts cannot be reconciled against a testing window.

**Performance Fact** — each `*_tests_meeting_threshold` must not exceed its `*_tests_total`

> NTIA forbids deleting, trimming, or excluding test measurements. More passing tests than total tests is the signature of a filtered denominator, not a rounding quirk.

**Deployment Location** — `install_date` is required when `service_status` is `installed` or `active`

> A location reported as built is being counted toward a buildout milestone, and a milestone claim with no date cannot be substantiated on review.

**BABA Evidence** — `compliance_path` `domestic_certification` requires `certification_ref` and `manufacturing_location`

> These are key elements of the manufacturer's BABA certification letter.

**BABA Evidence** — `compliance_path` `waiver` requires `waiver_ref`, `hs_code_10`, `product_identifier`, and `product_category`

> These are key elements of the NTIA waiver reporting tracker.

**BABA Evidence** — the two paths are mutually exclusive

> NTIA states that a certification letter is not needed for waived equipment, so a component travels exactly one path. Both set at once misstates which path a reviewer should follow.

---

## The four compliance thresholds

What the performance fields are ultimately for. NTIA evaluates a BEAD last-mile
network against four thresholds, each computed over a population of discrete
tests, and a provider is non-compliant if it fails **any** one of them.

| Threshold | Rule | Fields that answer it |
|---|---|---|
| Download | 80% of measurements at or above 80% of required download speed | `download_tests_meeting_threshold` / `download_tests_total` |
| Upload | the same, counted separately from download | `upload_tests_meeting_threshold` / `upload_tests_total` |
| Latency | 95% or more of round-trip measurements at or below 100 ms | `latency_tests_at_or_below_100ms` / `latency_tests_total` |
| Availability | average outage under 48 hours per 365 days (about 99.45% uptime) | `outage_hours_365d`, falling back to `uptime_pct` |

Required speed is the greater of the program floor (100/20 Mbps for a broadband
serviceable location, 1 Gbps symmetric for a community anchor institution) and the
committed speed tier in the subgrantee agreement. So for a 100/20 commitment the
working bar is 80/16 Mbps.

This is why `performance_fact` carries counts and not only means: a record holding
mean download speed and mean latency cannot answer any of the four questions,
because each needs a numerator and a denominator. `bead-data report` computes all
four per sample set.

The determination `report` produces is **indicative**. The binding determination is
made by the Eligible Entity and NTIA, who also weigh testing methodology, sampling
method, and transparency obligations that no data file can express.
