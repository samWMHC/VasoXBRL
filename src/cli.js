#!/usr/bin/env node

import { Command } from "commander";
import { EdgarClient } from "./client/edgar.js";
import { XbrlParser } from "./parser/xbrl.js";

const program = new Command();

program
  .name("vasoxbrl")
  .description("Fetch and parse SEC XBRL filings")
  .requiredOption(
    "-u, --user-agent <string>",
    "User-Agent for SEC requests (e.g. 'MyApp admin@example.com')"
  );

program
  .command("facts")
  .description("Fetch a filing and extract XBRL facts")
  .argument("<cik>", "Company CIK number")
  .option("-f, --form <type>", "Form type", "10-K")
  .action(async (cik, opts) => {
    const client = new EdgarClient({
      userAgent: program.opts().userAgent,
    });
    const parser = new XbrlParser();

    const filing = await client.getRecentFiling(cik, opts.form);
    console.log(
      `Found ${opts.form} filed ${filing.filingDate} (${filing.accessionNumber})`
    );

    const doc = await client.getFilingDocument(
      cik,
      filing.accessionNumber,
      filing.primaryDocument
    );
    const parsed = parser.parse(doc);
    const facts = parser.extractFacts(parsed);

    console.log(`Extracted ${facts.length} facts`);
    console.log(JSON.stringify(facts.slice(0, 20), null, 2));
    if (facts.length > 20) {
      console.log(`... and ${facts.length - 20} more`);
    }
  });

program
  .command("submissions")
  .description("Show recent submissions for a company")
  .argument("<cik>", "Company CIK number")
  .action(async (cik) => {
    const client = new EdgarClient({
      userAgent: program.opts().userAgent,
    });
    const data = await client.getSubmissions(cik);
    const recent = data.filings?.recent;
    if (!recent) {
      console.log("No recent filings found.");
      return;
    }

    const count = Math.min(recent.form.length, 10);
    console.log(`${data.name} (CIK ${data.cik})\n`);
    console.log("Recent filings:");
    for (let i = 0; i < count; i++) {
      console.log(
        `  ${recent.filingDate[i]}  ${recent.form[i].padEnd(8)} ${recent.accessionNumber[i]}`
      );
    }
  });

program.parseAsync();
