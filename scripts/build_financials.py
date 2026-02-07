#!/usr/bin/env python3
"""
Read cache/companyfacts_0000839087.json (VASO / Vaso Corporation)
and produce output/VASO_financials.xlsx with quarterly financials.
"""

import json
import pathlib
import sys

import pandas as pd
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INPUT = pathlib.Path("cache/companyfacts_0000839087.json")
OUTPUT = pathlib.Path("output/VASO_financials.xlsx")

# Each entry: (display_tag, sheet, unit_class, [primary_tag, ...fallbacks])
# unit_class: "usd", "shares", "per_share"
TAG_SPEC = [
    # ── Income Statement ──
    ("Revenues", "IncomeStatement", "usd", [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ]),
    ("CostOfRevenue", "IncomeStatement", "usd", [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
    ]),
    ("GrossProfit", "IncomeStatement", "usd", [
        "GrossProfit",
    ]),
    ("ResearchAndDevelopmentExpense", "IncomeStatement", "usd", [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ]),
    ("SellingGeneralAndAdministrativeExpense", "IncomeStatement", "usd", [
        "SellingGeneralAndAdministrativeExpense",
        "SellingAndMarketingExpense",
        "GeneralAndAdministrativeExpense",
    ]),
    ("OperatingExpenses", "IncomeStatement", "usd", [
        "OperatingExpenses",
        "CostsAndExpenses",
    ]),
    ("OperatingIncomeLoss", "IncomeStatement", "usd", [
        "OperatingIncomeLoss",
    ]),
    ("InterestExpense", "IncomeStatement", "usd", [
        "InterestExpense",
        "InterestExpenseDebt",
        "InterestIncomeExpenseNet",
    ]),
    ("NetIncomeLoss", "IncomeStatement", "usd", [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ]),
    # ── Balance Sheet ──
    ("CashAndCashEquivalents", "BalanceSheet", "usd", [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
        "Cash",
    ]),
    ("Assets", "BalanceSheet", "usd", [
        "Assets",
    ]),
    ("Liabilities", "BalanceSheet", "usd", [
        "Liabilities",
    ]),
    ("LongTermDebt", "BalanceSheet", "usd", [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
    ]),
    ("ShortTermBorrowings", "BalanceSheet", "usd", [
        "ShortTermBorrowings",
        "DebtCurrent",
        "LongTermDebtCurrent",
        "ShortTermDebtWeightedAverageInterestRate",
    ]),
    ("StockholdersEquity", "BalanceSheet", "usd", [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ]),
    # ── Cash Flow ──
    ("OperatingCashFlow", "CashFlow", "usd", [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ]),
    ("DepreciationAndAmortization", "CashFlow", "usd", [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ]),
    ("ShareBasedCompensation", "CashFlow", "usd", [
        "ShareBasedCompensation",
        "AllocatedShareBasedCompensationExpense",
        "ShareBasedCompensationExpenseAfterTax",
    ]),
    ("CapitalExpenditures", "CashFlow", "usd", [
        "CapitalExpenditures",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ]),
    ("PaymentsOfDividends", "CashFlow", "usd", [
        "PaymentsOfDividends",
        "PaymentsOfDividendsCommonStock",
        "Dividends",
    ]),
    # ── Shares & EPS ──
    ("SharesOutstanding", "Shares", "shares", [
        "CommonStockSharesOutstanding",
        "CommonStockSharesIssued",
    ]),
    ("WeightedAvgSharesDiluted", "Shares", "shares", [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberDilutedSharesOutstandingAdjustment",
    ]),
    ("EarningsPerShareBasic", "Shares", "per_share", [
        "EarningsPerShareBasic",
        "IncomeLossFromContinuingOperationsPerBasicShare",
    ]),
    ("EarningsPerShareDiluted", "Shares", "per_share", [
        "EarningsPerShareDiluted",
        "IncomeLossFromContinuingOperationsPerDilutedShare",
    ]),
]

# Build lookup: display_tag → (sheet, unit_class)
TAG_META = {display: (sheet, uc) for display, sheet, uc, _ in TAG_SPEC}

# Ordered display tags per sheet (for row ordering)
SHEET_TAG_ORDER = {}
for display, sheet, _, _ in TAG_SPEC:
    SHEET_TAG_ORDER.setdefault(sheet, []).append(display)

SHEETS = ["IncomeStatement", "BalanceSheet", "CashFlow", "Shares"]

NUMBER_FMT = {"usd": "#,##0", "shares": "#,##0", "per_share": "0.00"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_facts(path: pathlib.Path) -> dict:
    with open(path) as f:
        return json.load(f)


def resolve_tag(gaap: dict, candidates: list[str]) -> tuple[str | None, dict | None]:
    """Return the first matching (actual_tag, concept_dict) from candidates."""
    for tag in candidates:
        if tag in gaap:
            return tag, gaap[tag]
    return None, None


def extract_rows(raw: dict) -> list[dict]:
    """Pull every data point for the TAG_SPEC we care about into flat rows."""
    gaap = raw.get("facts", {}).get("us-gaap", {})
    rows = []
    for display, sheet, unit_class, candidates in TAG_SPEC:
        actual_tag, concept = resolve_tag(gaap, candidates)
        if concept is None:
            continue
        for unit_key, entries in concept.get("units", {}).items():
            for e in entries:
                fy = e.get("fy")
                fp = e.get("fp")
                if fy is None or fp is None:
                    continue
                rows.append({
                    "tag": display,
                    "actual_tag": actual_tag,
                    "sheet": sheet,
                    "unit_class": unit_class,
                    "fy": int(fy),
                    "fp": fp,
                    "end": e.get("end"),
                    "val": e.get("val"),
                    "unit": unit_key,
                    "form": e.get("form"),
                    "filed": e.get("filed"),
                    "accn": e.get("accn"),
                    "frame": e.get("frame"),
                })
    return rows


def quarter_label(fy: int, fp: str) -> str:
    return f"{fy}-{fp}"


def sort_key(col: str):
    parts = col.split("-")
    yr = int(parts[0])
    qtr = parts[1]
    qmap = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}
    return (yr, qmap.get(qtr, 9))


def build_pivot(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    sub = df[df["sheet"] == sheet_name].copy()
    if sub.empty:
        return sub

    sub = sub[sub["fp"].isin(["Q1", "Q2", "Q3", "Q4", "FY"])]
    sub["quarter"] = sub.apply(lambda r: quarter_label(r["fy"], r["fp"]), axis=1)
    sub = sub.sort_values("filed", ascending=False)
    sub = sub.drop_duplicates(subset=["tag", "quarter"], keep="first")

    pivot = sub.pivot_table(
        index="tag", columns="quarter", values="val", aggfunc="first"
    )
    pivot = pivot[sorted(pivot.columns, key=sort_key)]

    tag_order = SHEET_TAG_ORDER.get(sheet_name, [])
    ordered = [t for t in tag_order if t in pivot.index]
    pivot = pivot.loc[ordered]
    return pivot


# ---------------------------------------------------------------------------
# Segment / operational dimension scanning
# ---------------------------------------------------------------------------


def extract_segment_rows(raw: dict) -> list[dict]:
    """
    Scan every fact across all namespaces for entries that carry a
    segment/dimension member (indicated by a non-empty 'segment' or the
    presence of dimension-like keys in the frame string).

    The SEC companyfacts JSON is entity-level and usually does NOT include
    dimensional breakdowns.  We look anyway so the user knows it was checked.
    """
    rows = []
    for ns, concepts in raw.get("facts", {}).items():
        for tag, concept in concepts.items():
            for unit_key, entries in concept.get("units", {}).items():
                for e in entries:
                    frame = e.get("frame") or ""
                    # companyfacts frames with dimensions contain a member
                    # suffix like "CY2023Q1I_us-gaap_SomeSegmentMember"
                    if "_" not in frame:
                        continue
                    parts = frame.split("_", 1)
                    if len(parts) < 2:
                        continue
                    dimension_hint = parts[1]
                    # Skip frames that are just the standard period marker
                    if dimension_hint.startswith(("I", "Q")):
                        continue
                    fy = e.get("fy")
                    fp = e.get("fp")
                    if fy is None or fp is None:
                        continue
                    rows.append({
                        "namespace": ns,
                        "tag": tag,
                        "dimension_member": dimension_hint,
                        "fy": int(fy),
                        "fp": fp,
                        "end": e.get("end"),
                        "val": e.get("val"),
                        "unit": unit_key,
                        "form": e.get("form"),
                        "filed": e.get("filed"),
                        "frame": frame,
                    })
    return rows


# ---------------------------------------------------------------------------
# Excel formatting
# ---------------------------------------------------------------------------

HEADER_NOTE = "Values are as-filed XBRL facts sourced from SEC EDGAR companyfacts."


def _unit_label(sheet_name: str) -> str:
    labels = set()
    for display, sheet, uc, _ in TAG_SPEC:
        if sheet == sheet_name:
            labels.add({"usd": "USD", "shares": "Shares", "per_share": "USD/share"}[uc])
    return ", ".join(sorted(labels))


def format_sheet(ws, sheet_name: str, pivot: pd.DataFrame):
    """Apply formatting to a pivoted data sheet."""
    # Row 1 = header note, Row 2 = unit label, Row 3 = column headers from pandas
    # pandas wrote starting at row 1 with header in row 1.
    # We inserted header rows via startrow=2 so:
    #   Row 1: note   Row 2: units   Row 3: quarter headers   Row 4+: data

    # Freeze below the header rows and to the right of the tag column
    ws.freeze_panes = "B4"

    # Determine unit_class per row tag for number formatting
    tag_uc = {}
    for display, sheet, uc, _ in TAG_SPEC:
        if sheet == sheet_name:
            tag_uc[display] = uc

    num_data_cols = pivot.shape[1]
    num_data_rows = pivot.shape[0]

    # Number-format data cells (row 4+, col B+)
    for r_idx in range(num_data_rows):
        tag_name = pivot.index[r_idx]
        uc = tag_uc.get(tag_name, "usd")
        fmt = NUMBER_FMT.get(uc, "#,##0")
        for c_idx in range(num_data_cols):
            cell = ws.cell(row=4 + r_idx, column=2 + c_idx)
            cell.number_format = fmt

    # Auto-width columns
    for col_idx in range(1, 2 + num_data_cols):
        max_len = 0
        col_letter = get_column_letter(col_idx)
        for row in ws.iter_rows(min_row=1, max_row=3 + num_data_rows,
                                min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 3, 40)


def format_segment_sheet(ws, num_rows: int, num_cols: int):
    ws.freeze_panes = "B2"
    for col_idx in range(1, num_cols + 1):
        max_len = 0
        col_letter = get_column_letter(col_idx)
        for row in ws.iter_rows(min_row=1, max_row=1 + num_rows,
                                min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 3, 50)


def format_raw_sheet(ws, num_rows: int, num_cols: int):
    ws.freeze_panes = "A2"
    for col_idx in range(1, num_cols + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        # Sample first 50 rows for width heuristic
        for row in ws.iter_rows(min_row=1, max_row=min(51, 1 + num_rows),
                                min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max_len + 3, 40)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not INPUT.exists():
        print(f"ERROR: {INPUT} not found.", file=sys.stderr)
        print("Run this first:  node src/cli.js companyfacts 839087", file=sys.stderr)
        sys.exit(1)

    raw = load_facts(INPUT)
    entity = raw.get("entityName", "Unknown")
    print(f"Entity: {entity}")

    rows = extract_rows(raw)
    if not rows:
        print("No matching US-GAAP facts found.", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(rows)
    print(f"Total data points extracted: {len(df)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        # ── Pivoted sheets ──
        for sheet_name in SHEETS:
            pivot = build_pivot(df, sheet_name)
            if pivot.empty:
                pd.DataFrame({"note": [f"No {sheet_name} data found"]}).to_excel(
                    writer, sheet_name=sheet_name, index=False
                )
                print(f"  {sheet_name}: (empty)")
                continue

            # Write header note and unit label above the pivot
            ws = writer.book.create_sheet(sheet_name)
            writer.sheets[sheet_name] = ws
            ws.cell(row=1, column=1, value=HEADER_NOTE)
            ws.cell(row=2, column=1, value=f"Units: {_unit_label(sheet_name)}")

            pivot.to_excel(writer, sheet_name=sheet_name, startrow=2)
            format_sheet(ws, sheet_name, pivot)
            print(f"  {sheet_name}: {pivot.shape[0]} tags x {pivot.shape[1]} quarters")

        # ── Segments / Operational ──
        seg_rows = extract_segment_rows(raw)
        seg_sheet = "Segments_Operational"
        if seg_rows:
            seg_df = pd.DataFrame(seg_rows)
            seg_df.to_excel(writer, sheet_name=seg_sheet, index=False)
            ws = writer.sheets[seg_sheet]
            format_segment_sheet(ws, len(seg_df), len(seg_df.columns))
            print(f"  {seg_sheet}: {len(seg_df)} rows")
        else:
            pd.DataFrame({
                "note": [
                    "No segment/dimension facts found in companyfacts for this issuer."
                ]
            }).to_excel(writer, sheet_name=seg_sheet, index=False)
            print(f"  {seg_sheet}: (none found)")

        # ── RawFacts ──
        df.to_excel(writer, sheet_name="RawFacts", index=False)
        ws = writer.sheets["RawFacts"]
        format_raw_sheet(ws, len(df), len(df.columns))
        print(f"  RawFacts: {len(df)} rows")

    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
