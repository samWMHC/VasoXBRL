# VasoXBRL

Fetch SEC EDGAR filings and build quarterly financial spreadsheets.

## Quick start

```bash
pip install -r requirements.txt

# Step 1 — fetch aggregate company facts
node src/cli.js companyfacts 839087

# Step 2 — download individual 10-Q/10-K XBRL (last 10 years)
node src/cli.js filings 839087

# Step 3 — build Excel workbook
python scripts/build_financials.py
```

Output: `output/VASO_financials.xlsx`

## CLI commands (Node 18+, zero dependencies)

```bash
node src/cli.js submissions  <cik>   # fetch recent submissions JSON
node src/cli.js companyfacts <cik>   # fetch aggregated XBRL company facts
node src/cli.js filings      <cik>   # download 10-Q/10-K FilingSummary + R-files
```

All responses are cached under `./cache/`. The `filings` command creates
`cache/filings/{cik}/{accession}/` with `FilingSummary.xml`, `R*.xml`
report files, and a `meta.json` for each filing.

## Excel workbook sheets

### Companyfacts-based (from `companyfacts` command)

| Sheet | Contents |
|---|---|
| IncomeStatement | Revenues, CostOfRevenue, GrossProfit, R&D, SG&A, OperatingExpenses, OperatingIncomeLoss, InterestExpense, NetIncomeLoss |
| BalanceSheet | CashAndCashEquivalents, Assets, Liabilities, LongTermDebt, ShortTermBorrowings, StockholdersEquity |
| CashFlow | OperatingCashFlow, D&A, ShareBasedCompensation, CapEx, PaymentsOfDividends |
| Shares | SharesOutstanding, WeightedAvgSharesDiluted, EPS Basic, EPS Diluted |
| Segments_Operational | Dimensional/segment facts if present |
| RawFacts | All companyfacts data points in long-form |

### Filing-level (from `filings` command)

| Sheet | Contents |
|---|---|
| BalanceSheet_Full | Every line item from the Balance Sheet per the filing's presentation hierarchy (section headers, subtotals, indentation preserved) |
| IncomeStatement_Full | Every line item from the Income Statement / Operations statement |
| RawStatementFacts | Long-form: statement, label, element/tag, value, currency, periodEnd, accession, filingDate, form |

Filing-level sheets use the SEC XBRL viewer's R-file reports. The row
order matches the most recently filed statement; values are deduplicated
(newest filing wins for each period).

### Excel formatting

- Frozen header row + tag/label column on all wide sheets
- Number formats: USD `#,##0` / Shares `#,##0` / Per-share `0.00`
- Bold total rows on statement sheets
- Auto-sized column widths
- Header rows noting units and that values are as-filed XBRL facts

## Project structure

```
src/
  cli.js                       Node CLI — fetch & cache EDGAR data
scripts/
  build_financials.py          Python — companyfacts + filings → Excel
  parse_statements.py          Python — parse FilingSummary.xml + R*.xml
requirements.txt               pandas + openpyxl
cache/                         Cached data (git-ignored)
output/                        Generated Excel files (git-ignored)
```
