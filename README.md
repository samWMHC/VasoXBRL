# VasoXBRL

Fetch SEC EDGAR filings — zero external dependencies (Node 18+).

## Usage

```bash
# Fetch recent submissions for Apple (CIK 320193)
node src/cli.js submissions 320193

# Fetch all XBRL company facts for Apple
node src/cli.js companyfacts 320193
```

Responses are cached as JSON under `./cache/`.

## Project Structure

```
src/
  cli.js       Single-file CLI (fetch, fs, process.argv — no deps)
cache/         Cached JSON responses (git-ignored)
```
