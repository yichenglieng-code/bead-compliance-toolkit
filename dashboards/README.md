# Observability starter kit

A compliance dashboard is only worth having if it answers the question a state
broadband office will ask. So these panels are built around the four NTIA
thresholds, and deliberately keep observed averages in a corner labelled *context
only* — because an average is exactly what makes a failing sample set look healthy.

Everything here consumes `bead-data metrics`, which emits the same numbers as
`bead-data report` in Prometheus exposition format.

## Quick look, no infrastructure

```bash
bead-data metrics examples --period 2026-Q3
```

```text
bead_sample_set_compliant{sample_set="NV-71-100x20",technology="licensed_fixed_wireless",...} 1
bead_sample_set_compliant{sample_set="NV-72-100x20",technology="licensed_by_rule_fixed_wireless",...} 0
bead_upload_pass_ratio{sample_set="NV-72-100x20",...} 0.595238
```

That is the whole value proposition in three lines: one sample set is failing, and
it is failing on upload.

## Wiring it up

`bead-data metrics` writes a snapshot, not a long-running endpoint. Compliance
evidence arrives in periodic batches, not as a live stream, so a scrape target that
recomputes on every request would be wasted work. Two straightforward options:

### Option A — node_exporter textfile collector

Recompute on a schedule and drop the file where Prometheus already looks:

```bash
bead-data metrics /srv/bead/evidence \
  --period 2026-Q3 \
  -o /var/lib/node_exporter/textfile/bead.prom
```

```cron
17 6 * * * bead-data metrics /srv/bead/evidence -o /var/lib/node_exporter/textfile/bead.prom.$$ && mv /var/lib/node_exporter/textfile/bead.prom.$$ /var/lib/node_exporter/textfile/bead.prom
```

Write to a temporary name and move into place. The collector will happily read a
half-written file otherwise, and a truncated exposition looks like metrics that
suddenly vanished.

### Option B — static file served over HTTP

```bash
bead-data metrics /srv/bead/evidence -o /var/www/metrics/bead.prom
```

```yaml
scrape_configs:
  - job_name: bead-compliance
    scrape_interval: 15m
    metrics_path: /metrics/bead.prom
    static_configs:
      - targets: ["evidence.internal:80"]
```

## Import the Grafana dashboard

`grafana/bead_compliance.json`, via Dashboards → New → Import. It asks for a
Prometheus datasource and provides `state` and `technology` template variables.

Panels:

| Panel | Answers |
|---|---|
| Non-compliant sample sets | is anything failing right now |
| Threshold verdicts | which of the four, in which sample set |
| Speed pass ratios | how far from the 80% requirement, download and upload separately |
| Latency pass ratio | how far from the 95% requirement |
| Mean outage hours | how close to the 48 hour ceiling |
| Observed means | context for interpreting a failure, never for judging one |
| Locations by build status | buildout progress |
| BABA units | split by compliance path and country of origin |

The threshold panels draw their limit lines at 0.8, 0.95, and 48 to match the
exported `bead_threshold_*` metrics. If a federal threshold ever changes, the
exporter is the single place to change it, and `docs/sources.md` records where each
value came from.

## Alerting

The rule worth having is the one that fires while there is still a construction
season left to respond in.

```yaml
groups:
  - name: bead-compliance
    rules:
      - alert: BEADSampleSetNonCompliant
        expr: bead_sample_set_compliant == 0
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "Sample set {{ $labels.sample_set }} fails an NTIA threshold"
          description: >-
            {{ $labels.state }} / {{ $labels.technology }} is failing at least one of
            the four BEAD last-mile thresholds. Run: bead-data report on the evidence
            directory to see which.

      - alert: BEADSpeedMarginThin
        expr: |
          bead_download_pass_ratio < 0.85 or bead_upload_pass_ratio < 0.85
        for: 6h
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.sample_set }} is within 5 points of failing on speed"

      - alert: BEADOutageBudgetBurning
        expr: bead_outage_hours_mean > 38
        for: 6h
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.sample_set }} has used most of its 48 hour outage budget"

      - alert: BEADInvalidRecords
        expr: bead_records_invalid > 0
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Evidence contains records that fail validation"
```

The two warning rules exist because a threshold alert that fires the moment you are
already non-compliant has told you too late. 0.85 and 38 hours are arbitrary margins,
not requirements — tune them.

## OpenTelemetry

If your stack is OTel rather than Prometheus, the exposition output is directly
scrapeable by the collector's Prometheus receiver, with no change to this tooling:

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: bead-compliance
          scrape_interval: 15m
          metrics_path: /metrics/bead.prom
          static_configs:
            - targets: ["evidence.internal:80"]

processors:
  resource:
    attributes:
      - key: service.name
        value: bead-compliance
        action: upsert
      - key: deployment.environment
        value: production
        action: upsert
  batch: {}

exporters:
  otlphttp:
    endpoint: "https://otel-gateway.internal:4318"

service:
  pipelines:
    metrics:
      receivers: [prometheus]
      processors: [resource, batch]
      exporters: [otlphttp]
```

Gauges map cleanly onto the OTel metric model. The `sample_set`, `state`,
`technology`, and `threshold` labels become attributes.

## Metric reference

All metrics are gauges, prefixed `bead_`.

| Metric | Labels | Meaning |
|---|---|---|
| `bead_sample_set_compliant` | sample set | 1 pass, 0 fail. **Absent** when a threshold has no data |
| `bead_threshold_compliant` | sample set, `threshold` | per-threshold verdict, one of download, upload, latency, availability |
| `bead_download_pass_ratio` | sample set | share of download tests at or above 80% of required |
| `bead_upload_pass_ratio` | sample set | same for upload, judged separately |
| `bead_latency_pass_ratio` | sample set | share of round-trip tests at or below 100 ms |
| `bead_download_tests_total` / `_meeting_threshold` | sample set | the numerator and denominator, exported so a reviewer can recompute |
| `bead_upload_tests_total` / `_meeting_threshold` | sample set | as above |
| `bead_latency_tests_total` / `bead_latency_tests_within_ceiling` | sample set | as above; the total includes lost-packet tests |
| `bead_outage_hours_mean` | sample set | mean outage hours over the trailing 365 days |
| `bead_uptime_pct_mean` | sample set | mean reported uptime |
| `bead_required_down_mbps` / `_up_mbps` | sample set | the required speed this set is judged against |
| `bead_download_mbps_mean` / `bead_upload_mbps_mean` / `bead_latency_ms_mean` | sample set | observed means, context only |
| `bead_sample_set_locations` | sample set | distinct funded locations |
| `bead_locations` | state, service status, technology | funded locations by build status |
| `bead_baba_records` | compliance path | BABA evidence records |
| `bead_baba_units` | compliance path, origin country | component units |
| `bead_records` | `kind` | valid records per fact family |
| `bead_records_invalid` | — | records excluded for failing validation |
| `bead_files_read` | — | evidence files read |
| `bead_threshold_*` | — | the federal thresholds themselves, so panels need not hardcode them |

Sample-set labels throughout are `sample_set`, `state`, `technology_code`,
`technology`, `committed_down_mbps`, `committed_up_mbps`.

### One thing to be careful about

A missing series is not a zero. When a sample set reports no latency tests, there is
no `bead_latency_pass_ratio` sample for it at all — not a 0, which would look like
total failure, and not a 1, which would look like a pass. Absent evidence is absent,
and the graph should show a gap.

This matters for alert rules: `bead_sample_set_compliant == 0` will not fire for a
sample set whose data is simply missing. If you need to catch that too, alert on the
absence:

```yaml
- alert: BEADSampleSetNoVerdict
  expr: bead_sample_set_locations unless bead_sample_set_compliant
  for: 1h
  annotations:
    summary: "{{ $labels.sample_set }} has locations but no verdict — a threshold has no data"
```

## Scope

These are reference examples, not a hosted service. The verdicts are indicative: the
binding determination is made by the Eligible Entity and NTIA, who also weigh testing
methodology, sampling method, and transparency obligations that no metric expresses.
