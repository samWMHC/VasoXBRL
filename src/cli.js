#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const USER_AGENT = "VasoXBRL/0.2 (github.com/samWMHC/VasoXBRL)";
const SUBMISSIONS_URL = "https://data.sec.gov/submissions";
const COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts";
const CACHE_DIR = path.resolve("cache");

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function padCik(cik) {
  return String(cik).padStart(10, "0");
}

async function fetchJson(url) {
  const res = await fetch(url, {
    headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}  ${url}`);
  }
  return res.json();
}

function writeCache(name, data) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  const file = path.join(CACHE_DIR, name);
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
  return file;
}

// ---------------------------------------------------------------------------
// commands
// ---------------------------------------------------------------------------

async function submissions(cik) {
  const padded = padCik(cik);
  const url = `${SUBMISSIONS_URL}/CIK${padded}.json`;
  console.log(`Fetching ${url}`);
  const data = await fetchJson(url);

  const file = writeCache(`submissions_${padded}.json`, data);
  console.log(`Cached → ${file}`);

  const recent = data.filings?.recent;
  if (!recent) {
    console.log("No recent filings found.");
    return;
  }

  const count = Math.min(recent.form.length, 10);
  console.log(`\n${data.name} (CIK ${data.cik})\n`);
  console.log("Recent filings:");
  for (let i = 0; i < count; i++) {
    console.log(
      `  ${recent.filingDate[i]}  ${recent.form[i].padEnd(8)} ${recent.accessionNumber[i]}`
    );
  }
}

async function companyfacts(cik) {
  const padded = padCik(cik);
  const url = `${COMPANYFACTS_URL}/CIK${padded}.json`;
  console.log(`Fetching ${url}`);
  const data = await fetchJson(url);

  const file = writeCache(`companyfacts_${padded}.json`, data);
  console.log(`Cached → ${file}`);

  const namespaces = Object.keys(data.facts || {});
  let totalConcepts = 0;
  for (const ns of namespaces) {
    totalConcepts += Object.keys(data.facts[ns]).length;
  }
  console.log(`\n${data.entityName} (CIK ${data.cik})`);
  console.log(`Namespaces: ${namespaces.join(", ")}`);
  console.log(`Total concepts: ${totalConcepts}`);
}

// ---------------------------------------------------------------------------
// arg parsing
// ---------------------------------------------------------------------------

const USAGE = `Usage: vasoxbrl <command> <cik>

Commands:
  submissions  <cik>   Fetch recent submissions for a company
  companyfacts <cik>   Fetch all XBRL company facts

Examples:
  node src/cli.js submissions 320193
  node src/cli.js companyfacts 320193`;

const [command, cik] = process.argv.slice(2);

if (!command || !cik) {
  console.log(USAGE);
  process.exit(1);
}

switch (command) {
  case "submissions":
    await submissions(cik);
    break;
  case "companyfacts":
    await companyfacts(cik);
    break;
  default:
    console.error(`Unknown command: ${command}\n`);
    console.log(USAGE);
    process.exit(1);
}
