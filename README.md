# VasoXBRL

Fetch and parse SEC XBRL filings from EDGAR.

## Setup

```bash
npm install
```

## Usage

### CLI

```bash
# Show recent filings for a company (by CIK)
npx vasoxbrl -u "YourApp you@example.com" submissions 320193

# Extract XBRL facts from the latest 10-K
npx vasoxbrl -u "YourApp you@example.com" facts 320193

# Extract from a 10-Q instead
npx vasoxbrl -u "YourApp you@example.com" facts 320193 -f 10-Q
```

### Library

```js
import { EdgarClient, XbrlParser } from "vasoxbrl";

const client = new EdgarClient({ userAgent: "YourApp you@example.com" });
const parser = new XbrlParser();

const filing = await client.getRecentFiling("320193", "10-K");
const doc = await client.getFilingDocument("320193", filing.accessionNumber, filing.primaryDocument);
const facts = parser.extractFacts(parser.parse(doc));
```

## Project Structure

```
src/
  cli.js              CLI entry point
  index.js            Library exports
  client/edgar.js     SEC EDGAR HTTP client
  parser/xbrl.js      XBRL document parser
```
