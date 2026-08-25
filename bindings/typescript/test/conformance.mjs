/**
 * Run the published conformance suite against the TypeScript binding.
 *
 * This is the point of the binding existing. If a second, independent
 * implementation in another language passes the same vectors, the claim that the
 * schemas are the artifact and Python is merely one binding is demonstrated rather
 * than asserted.
 *
 * Usage:
 *   npm install && npm run conformance
 */

import { readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { createValidator } from "../src/index.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..", "..");
const SCHEMAS = join(REPO, "schemas");
const CONFORMANCE = join(REPO, "conformance");

function red(s) {
  return `\u001b[31m${s}\u001b[0m`;
}
function green(s) {
  return `\u001b[32m${s}\u001b[0m`;
}
function dim(s) {
  return `\u001b[2m${s}\u001b[0m`;
}

async function main() {
  const manifest = JSON.parse(await readFile(join(CONFORMANCE, "manifest.json"), "utf8"));
  const { validate, kinds } = await createValidator(SCHEMAS);

  console.log(
    `conformance suite ${manifest.conformance_suite_version} ` +
      `(schemas ${manifest.schema_version}): ${manifest.case_count} cases`,
  );
  console.log(dim(`binding covers: ${kinds.sort().join(", ")}`));
  console.log("");

  const failures = [];
  let passed = 0;

  for (const entry of manifest.cases) {
    const kase = JSON.parse(await readFile(join(CONFORMANCE, entry.path), "utf8"));
    const result = validate(kase.instance, kase.schema);

    if (result.valid !== kase.valid) {
      failures.push({
        name: kase.name,
        why: kase.valid
          ? `should validate but was rejected: ${result.errors
              .map((e) => `${e.field}: ${e.message}`)
              .join("; ")}`
          : "should have been rejected but validated",
      });
      continue;
    }

    if (!kase.valid) {
      const blamed = new Set(result.errors.map((e) => e.field));
      const missing = (kase.expect_fields ?? []).filter((f) => !blamed.has(f));
      if (missing.length > 0) {
        failures.push({
          name: kase.name,
          why:
            `rejected, but did not blame ${missing.join(", ")}. ` +
            `Blamed: ${[...blamed].sort().join(", ") || "(nothing)"}`,
        });
        continue;
      }
    }

    passed += 1;
  }

  console.log(`${green(`${passed} passed`)}${failures.length ? `, ${red(`${failures.length} failed`)}` : ""}`);

  if (failures.length > 0) {
    console.log("");
    for (const f of failures) {
      console.log(`${red("FAIL")} ${f.name}`);
      console.log(`     ${f.why}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log("");
  console.log("An independent implementation passes every published vector.");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
