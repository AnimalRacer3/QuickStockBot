#!/usr/bin/env node
/**
 * Validates all fixture files in shared/fixtures/ against their corresponding
 * JSON Schemas in shared/schemas/. Exits non-zero if any fixture is invalid.
 */

import Ajv from "ajv";
import addFormats from "ajv-formats";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const ajv = new Ajv({ strict: false });
addFormats(ajv);

const fixtures = [
  { schema: "ticker-state", fixture: "ticker-state.example" },
  { schema: "order", fixture: "order.example" },
  { schema: "order-status-event", fixture: "order-status-event.example" },
  { schema: "trade", fixture: "trade.example" },
  { schema: "log-event", fixture: "log-event.example" },
  { schema: "account-snapshot", fixture: "account-snapshot.example" },
];

let allPassed = true;

for (const { schema, fixture } of fixtures) {
  const schemaPath = join(root, "schemas", `${schema}.schema.json`);
  const fixturePath = join(root, "fixtures", `${fixture}.json`);

  const schemaDef = JSON.parse(readFileSync(schemaPath, "utf8"));
  const fixtureData = JSON.parse(readFileSync(fixturePath, "utf8"));

  // Trade schema uses internal $ref definitions — resolve them locally
  const validate = ajv.compile(schemaDef);
  const valid = validate(fixtureData);

  if (valid) {
    console.log(`✓  ${fixture}.json`);
  } else {
    console.error(`✗  ${fixture}.json`);
    for (const err of validate.errors ?? []) {
      console.error(`   ${err.instancePath} ${err.message}`);
    }
    allPassed = false;
  }
}

if (!allPassed) {
  console.error("\nSchema validation failed.");
  process.exit(1);
}

console.log(`\nAll ${fixtures.length} fixtures validated successfully.`);
