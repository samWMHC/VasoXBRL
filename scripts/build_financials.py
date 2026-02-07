#!/usr/bin/env python3
"""
Read cache/companyfacts_0000839087.json (VASO / Vaso Corporation)
and produce output/VASO_financials.xlsx with quarterly financials.
"""

import json
import pathlib
import sys

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INPUT = pathlib.Path("cache/companyfacts_0000839087.json")
OUTPUT = pathlib.Path("output/VASO_financials.xlsx")

TAGS = {
    # Income Statement
    "Revenues": "IncomeStatement",
    "CostOfRevenue": "IncomeStatement",
    "GrossProfit": "IncomeStatement",
    "OperatingIncomeLoss": "IncomeStatement",
    "NetIncomeLoss": "IncomeStatement",
    # Balance Sheet
    "Assets": "BalanceSheet",
    "Liabilities": "BalanceSheet",
    "StockholdersEquity": "BalanceSheet",
    # Cash Flow
    "NetCashProvidedByUsedInOperatingActivities": "CashFlow",
    "PaymentsOfDividends": "CashFlow",
    # Shares
    "WeightedAverageNumberOfDilutedSharesOutstanding": "Shares",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_facts(path: pathlib.Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_rows(raw: dict) -> list[dict]:
    """Pull every data point for the TAGS we care about into flat rows."""
    gaap = raw.get("facts", {}).get("us-gaap", {})
    rows = []
    for tag, sheet in TAGS.items():
        concept = gaap.get(tag)
        if concept is None:
            continue
        # units can be "USD", "USD/shares", "shares", etc.
        for unit_key, entries in concept.get("units", {}).items():
            for e in entries:
                fy = e.get("fy")
                fp = e.get("fp")
                if fy is None or fp is None:
                    continue
                rows.append(
                    {
                        "tag": tag,
                        "sheet": sheet,
                        "fy": int(fy),
                        "fp": fp,
                        "end": e.get("end"),
                        "val": e.get("val"),
                        "unit": unit_key,
                        "form": e.get("form"),
                        "filed": e.get("filed"),
                        "accn": e.get("accn"),
                        "frame": e.get("frame"),
                    }
                )
    return rows


def quarter_label(fy: int, fp: str) -> str:
    """FY2023 Q1 -> '2023-Q1', FY -> '2023-FY'."""
    return f"{fy}-{fp}"


def build_pivot(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """
    For a given sheet category, keep only quarterly (Q1-Q4) rows,
    deduplicate (keep latest filing per tag+quarter), and pivot
    so that quarters are columns.
    """
    sub = df[df["sheet"] == sheet_name].copy()
    if sub.empty:
        return sub

    # Keep Q1-Q4 and FY; drop anything else (like Q1-Q3 cumulative marked as
    # a different fp). Sort so the latest filing date wins on dedup.
    sub = sub[sub["fp"].isin(["Q1", "Q2", "Q3", "Q4", "FY"])]
    sub["quarter"] = sub.apply(lambda r: quarter_label(r["fy"], r["fp"]), axis=1)
    sub = sub.sort_values("filed", ascending=False)
    sub = sub.drop_duplicates(subset=["tag", "quarter"], keep="first")

    pivot = sub.pivot_table(
        index="tag", columns="quarter", values="val", aggfunc="first"
    )

    # Sort columns chronologically
    def sort_key(col: str):
        parts = col.split("-")
        yr = int(parts[0])
        qtr = parts[1]
        qmap = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 5}
        return (yr, qmap.get(qtr, 9))

    pivot = pivot[sorted(pivot.columns, key=sort_key)]

    # Reorder rows to match the TAGS declaration order
    tag_order = [t for t, s in TAGS.items() if s == sheet_name]
    ordered = [t for t in tag_order if t in pivot.index]
    pivot = pivot.loc[ordered]

    return pivot


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
        for sheet_name in ["IncomeStatement", "BalanceSheet", "CashFlow", "Shares"]:
            pivot = build_pivot(df, sheet_name)
            if pivot.empty:
                # Write a placeholder so the sheet still exists
                pd.DataFrame({"note": [f"No {sheet_name} data found"]}).to_excel(
                    writer, sheet_name=sheet_name, index=False
                )
            else:
                pivot.to_excel(writer, sheet_name=sheet_name)
            print(f"  {sheet_name}: {pivot.shape[0]} tags x {pivot.shape[1]} quarters")

        # Sheet 5: RawFacts (long-form, all rows)
        df.to_excel(writer, sheet_name="RawFacts", index=False)
        print(f"  RawFacts: {len(df)} rows")

    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
