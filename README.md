# VasoXBRL

Fetch SEC EDGAR filings and build quarterly financial spreadsheets.

## 1. Fetch data (Node 18+, zero dependencies)

```bash
# Fetch company facts for VASO (CIK 839087)
node src/cli.js companyfacts 839087

# Fetch recent submissions
node src/cli.js submissions 839087
```

Responses are cached as JSON under `./cache/`.

## 2. Build Excel workbook (Python)

```bash
pip install -r requirements.txt
python scripts/build_financials.py
```

Reads `cache/companyfacts_0000839087.json` and writes
`output/VASO_financials.xlsx` with six sheets:

| Sheet | Tags |
|---|---|
| IncomeStatement | Revenues, CostOfRevenue, GrossProfit, R&D Expense, SG&A Expense, OperatingExpenses, OperatingIncomeLoss, InterestExpense, NetIncomeLoss |
| BalanceSheet | CashAndCashEquivalents, Assets, Liabilities, LongTermDebt, ShortTermBorrowings, StockholdersEquity |
| CashFlow | OperatingCashFlow, DepreciationAndAmortization, ShareBasedCompensation, CapitalExpenditures, PaymentsOfDividends |
| Shares | SharesOutstanding (end-of-period), WeightedAvgSharesDiluted, EarningsPerShareBasic, EarningsPerShareDiluted |
| Segments_Operational | Dimensional/segment facts if present (checked automatically) |
| RawFacts | Every extracted data point in long-form |

Each tag resolves to the first available US-GAAP concept from a prioritized
fallback list (e.g. Revenues falls back to
RevenueFromContractWithCustomerExcludingAssessedTax, then SalesRevenueNet).

### Excel formatting

- Frozen header row + tag column on all pivoted sheets
- Number formats: USD `#,##0` · Shares `#,##0` · Per-share `0.00`
- Auto-sized column widths
- Header rows with units and a note that values are as-filed XBRL facts

## Project Structure

```
src/
  cli.js                       Node CLI — fetch EDGAR JSON
scripts/
  build_financials.py          Python — JSON → Excel
requirements.txt               pandas + openpyxl
cache/                         Cached JSON responses (git-ignored)
output/                        Generated Excel files (git-ignored)
```
