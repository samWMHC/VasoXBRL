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
`output/VASO_financials.xlsx` with five sheets:

| Sheet | Contents |
|---|---|
| IncomeStatement | Revenues, CostOfRevenue, GrossProfit, OperatingIncomeLoss, NetIncomeLoss |
| BalanceSheet | Assets, Liabilities, StockholdersEquity |
| CashFlow | NetCashProvidedByUsedInOperatingActivities, PaymentsOfDividends |
| Shares | WeightedAverageNumberOfDilutedSharesOutstanding |
| RawFacts | Every extracted data point in long-form |

Quarters appear as columns (e.g. `2023-Q1`, `2023-Q2`, …, `2023-FY`).

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
