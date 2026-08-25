/**
 * A second binding for the BEAD compliance data schemas.
 *
 * This exists to test a claim rather than to add a feature. The README says the
 * JSON Schemas are normative and the Python package is one binding among possible
 * others. That is either true or it is marketing, and the way to find out is to
 * implement it again in a different language and run the same published
 * conformance vectors.
 *
 * The exercise turned out to be informative in a specific way. JSON Schema carries
 * most of the contract on its own: types, ranges, patterns, enums, required
 * fields, and even the conditional requirements for the two BABA compliance paths
 * and for successful speed versus latency observations, all of which are expressed
 * with `if`/`then`. What it cannot express is any rule that compares two values.
 * Those are enumerated in CROSS_FIELD_RULES below, and any implementation in any
 * language has to write them by hand.
 *
 * Documenting that split is more useful than hiding it, because an implementer who
 * runs a schema validator and stops will pass most of the suite and silently miss
 * exactly the rules that protect against a filtered denominator.
 */

import { readFile } from "node:fs/promises";
import { join } from "node:path";

import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const PROVENANCE_ID =
  "https://raw.githubusercontent.com/yichenglieng-code/bead-compliance-toolkit" +
  "/main/schemas/common/v0/provenance.schema.json";

/** Schema file for each fact kind, relative to the schemas root. */
export const SCHEMA_PATHS = {
  performance: "performance/v0/performance_fact.schema.json",
  test: "performance/v0/performance_test.schema.json",
  location: "location/v0/deployment_location.schema.json",
  baba: "baba/v0/baba_evidence.schema.json",
};

/** NTIA sets a minimum speed-test duration of 15 seconds. */
export const MIN_SPEED_TEST_SECONDS = 15;

const BUILT_STATUSES = new Set(["installed", "active"]);

function parseTime(value) {
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

/**
 * Rules JSON Schema cannot express, because each compares two values.
 *
 * Each returns an array of `{ field, message }`. Keeping them as data rather than
 * inline branches means the list is auditable against docs/schema_reference.md.
 */
export const CROSS_FIELD_RULES = {
  performance: [
    function periodOrder(record) {
      const start = parseTime(record.period_start);
      const end = parseTime(record.period_end);
      if (start === null || end === null || end >= start) return [];
      return [
        {
          field: "period_end",
          message: `period_end (${record.period_end}) must be at or after period_start (${record.period_start})`,
        },
      ];
    },
    function testCounts(record) {
      const pairs = [
        ["download_tests_meeting_threshold", "download_tests_total"],
        ["upload_tests_meeting_threshold", "upload_tests_total"],
        ["latency_tests_at_or_below_100ms", "latency_tests_total"],
      ];
      const out = [];
      for (const [subsetKey, totalKey] of pairs) {
        const subset = record[subsetKey];
        const total = record[totalKey];
        if (subset == null || total == null) continue;
        if (subset > total) {
          out.push({
            field: subsetKey,
            message: `${subsetKey} (${subset}) must not exceed ${totalKey} (${total})`,
          });
        }
      }
      return out;
    },
  ],

  location: [
    function installDateRequired(record) {
      if (!BUILT_STATUSES.has(record.service_status)) return [];
      if (record.install_date) return [];
      return [
        {
          field: "install_date",
          message: `install_date is required when service_status is '${record.service_status}'`,
        },
      ];
    },
  ],

  baba: [
    function pathExclusivity(record) {
      if (record.compliance_path === "domestic_certification" && record.waiver_ref) {
        return [
          {
            field: "waiver_ref",
            message:
              "waiver_ref must not be set when compliance_path is 'domestic_certification'; a component follows exactly one path",
          },
        ];
      }
      if (record.compliance_path === "waiver" && record.certification_ref) {
        return [
          {
            field: "certification_ref",
            message:
              "certification_ref must not be set when compliance_path is 'waiver'; a component follows exactly one path",
          },
        ];
      }
      return [];
    },
  ],

  test: [
    function timeOrder(record) {
      if (!record.ended_at) return [];
      const start = parseTime(record.started_at);
      const end = parseTime(record.ended_at);
      if (start === null || end === null || end >= start) return [];
      return [
        {
          field: "ended_at",
          message: `ended_at (${record.ended_at}) must be at or after started_at (${record.started_at})`,
        },
      ];
    },
    function noResultWhenNotRun(record) {
      if (record.test_status === "success") return [];
      const out = [];
      for (const key of ["bytes_transferred", "latency_ms_rtt"]) {
        if (record[key] != null) {
          out.push({
            field: key,
            message: `${key} must not be set when test_status is '${record.test_status}'; a test that did not run has no result`,
          });
        }
      }
      return out;
    },
    function packetAccounting(record) {
      const { packets_sent: sent, packets_received: received } = record;
      if (sent == null || received == null || received <= sent) return [];
      return [
        {
          field: "packets_received",
          message: `packets_received (${received}) must not exceed packets_sent (${sent})`,
        },
      ];
    },
    function minimumSpeedTestDuration(record) {
      if (record.test_status !== "success") return [];
      if (record.test_type === "latency") return [];
      if (!record.ended_at) return [];
      const start = parseTime(record.started_at);
      const end = parseTime(record.ended_at);
      if (start === null || end === null) return [];
      const seconds = (end - start) / 1000;
      if (seconds >= MIN_SPEED_TEST_SECONDS) return [];
      return [
        {
          field: "ended_at",
          message: `ended_at implies a ${seconds}s speed test; NTIA requires a minimum duration of ${MIN_SPEED_TEST_SECONDS} seconds`,
        },
      ];
    },
  ],
};

/** Load the schemas and build a validator. */
export async function createValidator(schemasRoot) {
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);

  const provenance = JSON.parse(
    await readFile(join(schemasRoot, "common/v0/provenance.schema.json"), "utf8"),
  );
  ajv.addSchema(provenance, PROVENANCE_ID);

  const compiled = {};
  for (const [kind, relPath] of Object.entries(SCHEMA_PATHS)) {
    const schema = JSON.parse(await readFile(join(schemasRoot, relPath), "utf8"));
    compiled[kind] = ajv.compile(schema);
  }

  /**
   * Validate one record. Returns `{ valid, errors }` where each error carries the
   * field path it blames, matching what the conformance suite checks.
   */
  function validate(record, kind) {
    const validateSchema = compiled[kind];
    if (!validateSchema) throw new Error(`unknown schema kind: ${kind}`);

    const errors = [];
    if (!validateSchema(record)) {
      for (const err of validateSchema.errors ?? []) {
        errors.push({ field: fieldPathFor(err), message: err.message ?? "invalid" });
      }
      // Mirrors the Python binding: a record failing the schema pass is not put
      // through the cross-field pass, which would mostly restate the same fault.
      return { valid: false, errors };
    }

    for (const rule of CROSS_FIELD_RULES[kind] ?? []) {
      errors.push(...rule(record));
    }
    return { valid: errors.length === 0, errors };
  }

  return { validate, kinds: Object.keys(compiled) };
}

/**
 * Field path to blame for one Ajv error.
 *
 * `required` and `additionalProperties` failures point at the object rather than
 * at a field inside it, so the offending property is recovered from the error
 * params. Reporting `<record>` would be accurate and useless.
 */
export function fieldPathFor(err) {
  const prefix = (err.instancePath ?? "").replace(/^\//, "").split("/").join(".");

  if (err.keyword === "required") {
    const name = err.params?.missingProperty;
    if (name) return prefix ? `${prefix}.${name}` : name;
  }
  if (err.keyword === "additionalProperties") {
    const name = err.params?.additionalProperty;
    if (name) return prefix ? `${prefix}.${name}` : name;
  }
  return prefix || "<record>";
}
