#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const USER_AGENT = "VasoXBRL/0.3 (github.com/samWMHC/VasoXBRL)";
const SUBMISSIONS_URL = "https://data.sec.gov/submissions";
const COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts";
const ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data";
const CACHE_DIR = path.resolve("cache");

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function padCik(cik) {
  return String(cik).padStart(10, "0");
}

function rawCik(cik) {
  return String(Number(cik));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

async function fetchText(url) {
  const res = await fetch(url, {
    headers: { "User-Agent": USER_AGENT, Accept: "*/*" },
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}  ${url}`);
  }
  return res.text();
}

function writeCache(name, data) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  const file = path.join(CACHE_DIR, name);
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
  return file;
}

/** Load submissions JSON, using cache when available. */
async function loadSubmissions(cik) {
  const padded = padCik(cik);
  const cached = path.join(CACHE_DIR, `submissions_${padded}.json`);
  if (fs.existsSync(cached)) {
    return JSON.parse(fs.readFileSync(cached, "utf-8"));
  }
  const url = `${SUBMISSIONS_URL}/CIK${padded}.json`;
  console.log(`Fetching ${url}`);
  const data = await fetchJson(url);
  writeCache(`submissions_${padded}.json`, data);
  return data;
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
  console.log(`Cached -> ${file}`);

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
  console.log(`Cached -> ${file}`);

  const namespaces = Object.keys(data.facts || {});
  let totalConcepts = 0;
  for (const ns of namespaces) {
    totalConcepts += Object.keys(data.facts[ns]).length;
  }
  console.log(`\n${data.entityName} (CIK ${data.cik})`);
  console.log(`Namespaces: ${namespaces.join(", ")}`);
  console.log(`Total concepts: ${totalConcepts}`);
}

async function filings(cik) {
  const padded = padCik(cik);
  const cikNum = rawCik(cik);

  // 1. Get submissions
  const subs = await loadSubmissions(cik);
  console.log(`${subs.name} (CIK ${subs.cik})`);

  // 2. Collect all filings — recent page + any additional pages
  const cutoffYear = new Date().getFullYear() - 10;
  const cutoffDate = `${cutoffYear}-01-01`;

  const all = [];
  const recent = subs.filings?.recent;
  if (recent) {
    for (let i = 0; i < recent.form.length; i++) {
      all.push({
        accession: recent.accessionNumber[i],
        form: recent.form[i],
        date: recent.filingDate[i],
        primaryDoc: recent.primaryDocument[i],
      });
    }
  }

  // Fetch additional submission pages if the oldest recent filing is
  // still newer than our cutoff.
  const oldest = all.length > 0 ? all[all.length - 1].date : "";
  if (oldest > cutoffDate && subs.filings?.files?.length > 0) {
    for (const ref of subs.filings.files) {
      console.log(`Fetching additional submissions: ${ref.name}`);
      await sleep(150);
      const page = await fetchJson(`${SUBMISSIONS_URL}/${ref.name}`);
      if (page.accessionNumber) {
        for (let i = 0; i < page.accessionNumber.length; i++) {
          all.push({
            accession: page.accessionNumber[i],
            form: page.form[i],
            date: page.filingDate[i],
            primaryDoc: page.primaryDocument[i],
          });
        }
      }
    }
  }

  // 3. Filter for 10-Q / 10-K in the last 10 years
  const targets = all.filter(
    (f) => (f.form === "10-Q" || f.form === "10-K") && f.date >= cutoffDate
  );
  console.log(
    `\n${targets.length} 10-Q/10-K filings since ${cutoffDate}\n`
  );

  // 4. Download FilingSummary.xml + R-files for each filing
  const filingsDir = path.join(CACHE_DIR, "filings", padded);
  let downloaded = 0;
  let skipped = 0;

  for (const filing of targets) {
    const dir = path.join(filingsDir, filing.accession);
    const metaFile = path.join(dir, "meta.json");

    if (fs.existsSync(metaFile)) {
      skipped++;
      continue;
    }

    const accFlat = filing.accession.replace(/-/g, "");
    const base = `${ARCHIVES_URL}/${cikNum}/${accFlat}`;

    console.log(
      `  ${filing.date}  ${filing.form.padEnd(5)} ${filing.accession}`
    );
    fs.mkdirSync(dir, { recursive: true });

    // -- FilingSummary.xml --
    let summaryText;
    try {
      await sleep(150);
      summaryText = await fetchText(`${base}/FilingSummary.xml`);
      fs.writeFileSync(path.join(dir, "FilingSummary.xml"), summaryText);
    } catch (e) {
      console.log(`    (no FilingSummary.xml — skipping)`);
      fs.writeFileSync(
        metaFile,
        JSON.stringify(
          {
            cik: cikNum,
            accession: filing.accession,
            form: filing.form,
            filingDate: filing.date,
            primaryDocument: filing.primaryDoc,
            error: "No FilingSummary.xml",
          },
          null,
          2
        )
      );
      continue;
    }

    // -- extract R-file names via regex --
    const rFileNames = [
      ...summaryText.matchAll(/<XmlFileName>(R\d+\.xml)<\/XmlFileName>/g),
    ].map((m) => m[1]);

    // -- download each R-file --
    const savedRFiles = [];
    for (const rName of rFileNames) {
      await sleep(150);
      try {
        const rText = await fetchText(`${base}/${rName}`);
        fs.writeFileSync(path.join(dir, rName), rText);
        savedRFiles.push(rName);
      } catch {
        // not every R-file may exist; OK to skip
      }
    }

    // -- metadata --
    fs.writeFileSync(
      metaFile,
      JSON.stringify(
        {
          cik: cikNum,
          accession: filing.accession,
          form: filing.form,
          filingDate: filing.date,
          primaryDocument: filing.primaryDoc,
          rFiles: savedRFiles,
        },
        null,
        2
      )
    );

    downloaded++;
  }

  if (skipped > 0) console.log(`\n${skipped} filings already cached`);
  if (downloaded > 0) console.log(`${downloaded} filings downloaded`);
  console.log(`Cached to ${filingsDir}`);
}

// ---------------------------------------------------------------------------
// arg parsing
// ---------------------------------------------------------------------------

const USAGE = `Usage: vasoxbrl <command> <cik>

Commands:
  submissions  <cik>   Fetch recent submissions for a company
  companyfacts <cik>   Fetch all XBRL company facts
  filings      <cik>   Download 10-Q/10-K XBRL for last 10 years

Examples:
  node src/cli.js submissions 320193
  node src/cli.js companyfacts 320193
  node src/cli.js filings 839087`;

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
  case "filings":
    await filings(cik);
    break;
  default:
    console.error(`Unknown command: ${command}\n`);
    console.log(USAGE);
    process.exit(1);
}
