"""
Parse SEC EDGAR filing-level XBRL documents:
  - FilingSummary.xml  -> identify which R-file is Balance Sheet / Income Statement
  - R*.xml             -> extract line items in presentation order with values

Uses only the Python stdlib (xml.etree.ElementTree).
"""

import json
import pathlib
import re
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

_NS_RE = re.compile(r'\s+xmlns(?::\w+)?="[^"]*"')


def _parse_xml(text: str) -> ET.Element:
    """Parse XML after stripping namespace declarations."""
    return ET.fromstring(_NS_RE.sub("", text))


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _bool(el: ET.Element | None) -> bool:
    return _text(el).lower() == "true"


# ---------------------------------------------------------------------------
# FilingSummary.xml
# ---------------------------------------------------------------------------

BALANCE_SHEET_KW = ["balance sheet", "financial position", "financial condition"]
INCOME_STMT_KW = ["operations", "income statement", "comprehensive income",
                   "earnings", "income"]


def parse_filing_summary(xml_text: str) -> list[dict]:
    """Return [{short_name, long_name, xml_file, html_file}, ...]."""
    root = _parse_xml(xml_text)
    reports = []
    for rep in root.iter("Report"):
        xml_file = _text(rep.find("XmlFileName"))
        if not xml_file:
            continue
        reports.append({
            "short_name": _text(rep.find("ShortName")),
            "long_name": _text(rep.find("LongName")),
            "xml_file": xml_file,
            "html_file": _text(rep.find("HtmlFileName")),
        })
    return reports


def find_statement_report(
    reports: list[dict], keywords: list[str]
) -> dict | None:
    """Find the first report whose name matches any keyword.

    Prefer reports whose LongName contains "Statement -" (a standard SEC
    viewer convention), then fall back to any name match.
    """
    def _matches(name: str) -> bool:
        name_l = name.lower()
        return any(kw in name_l for kw in keywords)

    # Pass 1: strict — must have "Statement" in LongName
    for r in reports:
        if "statement" in r["long_name"].lower():
            combined = r["short_name"] + " " + r["long_name"]
            if _matches(combined):
                return r

    # Pass 2: relaxed — any name match
    for r in reports:
        combined = r["short_name"] + " " + r["long_name"]
        if _matches(combined):
            return r

    return None


# ---------------------------------------------------------------------------
# R*.xml  (SEC XBRL viewer report)
# ---------------------------------------------------------------------------


def parse_report_xml(xml_text: str) -> dict:
    """Parse an R*.xml file into {columns: [...], rows: [...]}.

    Columns carry period metadata; rows carry line items with per-column
    cell values.
    """
    root = _parse_xml(xml_text)

    # ── columns ──
    columns: list[dict] = []
    for col_el in root.iter("Column"):
        col = {
            "id": _text(col_el.find("Id")),
            "label": _text(col_el.find("SuperHeader")),
            "currency": _text(col_el.find("CurrencyCode")),
            "period_end": "",
            "period_type": "",
            "has_segments": _bool(col_el.find("hasSegments")),
        }
        # Period lives inside MCU/DateRange
        for dr in col_el.iter("DateRange"):
            end = _text(dr.find("EndDate"))
            if end:
                col["period_end"] = end[:10]  # "2023-12-31T00:00:00" -> date
            col["period_type"] = _text(dr.find("PeriodType"))
            break
        if col["period_end"]:
            columns.append(col)

    # ── rows ──
    rows: list[dict] = []
    for row_el in root.iter("Row"):
        element = _text(row_el.find("ElementName"))
        label = _text(row_el.find("Label"))
        if not element and not label:
            continue

        row = {
            "element": element,
            "label": label,
            "level": 0,
            "is_abstract": _bool(row_el.find("IsAbstractGroupTitle")),
            "is_total": _bool(row_el.find("IsTotalLabel")),
            "cells": [],
        }
        try:
            row["level"] = int(_text(row_el.find("Level")) or 0)
        except ValueError:
            pass

        cells_el = row_el.find("Cells")
        if cells_el is not None:
            for cell_el in cells_el:
                is_num = _bool(cell_el.find("IsNumeric"))
                numeric = 0.0
                if is_num:
                    raw = _text(cell_el.find("NumericAmount"))
                    try:
                        numeric = float(raw) if raw else 0.0
                    except ValueError:
                        numeric = 0.0
                row["cells"].append({
                    "is_numeric": is_num,
                    "numeric": numeric,
                    "text": _text(cell_el.find("NonNumbericText"))
                            or _text(cell_el.find("NonNumericText")),
                })

        rows.append(row)

    return {"columns": columns, "rows": rows}


# ---------------------------------------------------------------------------
# High-level: process all cached filings for a CIK
# ---------------------------------------------------------------------------


def process_filings(cache_dir: pathlib.Path, cik_padded: str) -> dict:
    """Walk ``cache/filings/{cik_padded}/*/`` and extract statement data.

    Returns::

        {
            "balance_sheet":    [StatementPeriod, ...],
            "income_statement": [StatementPeriod, ...],
        }

    where each *StatementPeriod* is::

        {
            "accession":  str,
            "filing_date": str,
            "form":       str,
            "period_end": str,
            "statement":  str,   # short_name from FilingSummary
            "currency":   str,
            "rows": [{label, element, level, is_abstract, is_total, value}, ...],
        }
    """
    filings_dir = cache_dir / "filings" / cik_padded
    if not filings_dir.exists():
        return {"balance_sheet": [], "income_statement": []}

    results: dict[str, list] = {"balance_sheet": [], "income_statement": []}

    for acc_dir in sorted(filings_dir.iterdir()):
        if not acc_dir.is_dir():
            continue

        meta_path = acc_dir / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        if meta.get("error"):
            continue

        summary_path = acc_dir / "FilingSummary.xml"
        if not summary_path.exists():
            continue

        try:
            reports = parse_filing_summary(summary_path.read_text())
        except ET.ParseError:
            continue

        for key, keywords in [
            ("balance_sheet", BALANCE_SHEET_KW),
            ("income_statement", INCOME_STMT_KW),
        ]:
            report = find_statement_report(reports, keywords)
            if not report:
                continue
            r_path = acc_dir / report["xml_file"]
            if not r_path.exists():
                continue
            try:
                parsed = parse_report_xml(r_path.read_text())
            except ET.ParseError:
                continue

            for col_idx, col in enumerate(parsed["columns"]):
                row_data = []
                for r in parsed["rows"]:
                    value = None
                    if (
                        col_idx < len(r["cells"])
                        and r["cells"][col_idx]["is_numeric"]
                    ):
                        value = r["cells"][col_idx]["numeric"]
                    row_data.append({
                        "label": r["label"],
                        "element": r["element"],
                        "level": r["level"],
                        "is_abstract": r["is_abstract"],
                        "is_total": r["is_total"],
                        "value": value,
                    })

                results[key].append({
                    "accession": meta["accession"],
                    "filing_date": meta["filingDate"],
                    "form": meta["form"],
                    "period_end": col["period_end"],
                    "statement": report["short_name"],
                    "currency": col.get("currency", "USD"),
                    "rows": row_data,
                })

    return results


# ---------------------------------------------------------------------------
# Pivot builder
# ---------------------------------------------------------------------------


def build_statement_pivot(
    periods: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Convert a list of StatementPeriod dicts into a pivot structure.

    Returns ``(pivot_rows, raw_rows, row_meta)``:

    * **pivot_rows** — ``[{label, element, <period_end>: value, ...}, ...]``
      in presentation order.  Row ordering comes from the most-recently-filed
      period so the layout matches the latest filing.
    * **raw_rows** — long-form ``[{statement, label, element, value,
      currency, period_end, accession, filing_date, form, ...}, ...]``.
    * **row_meta** — ``[{label, element, level, is_abstract, is_total}, ...]``
      matching *pivot_rows* index-for-index.
    """
    if not periods:
        return [], [], []

    # Sort newest-filed first so the first filing sets canonical row order
    # and dedup keeps the freshest value.
    sorted_periods = sorted(
        periods, key=lambda p: p["filing_date"], reverse=True
    )

    # Canonical row order (label, element)
    seen: set[tuple[str, str]] = set()
    row_meta: list[dict] = []
    for period in sorted_periods:
        for r in period["rows"]:
            k = (r["label"], r["element"])
            if k not in seen:
                seen.add(k)
                row_meta.append({
                    "label": r["label"],
                    "element": r["element"],
                    "level": r["level"],
                    "is_abstract": r["is_abstract"],
                    "is_total": r["is_total"],
                })

    # Collect unique period_end dates
    all_periods = sorted({p["period_end"] for p in sorted_periods})

    # Value lookup: (label, element, period_end) → value  (newest filing wins)
    values: dict[tuple, float] = {}
    raw_rows: list[dict] = []

    for period in sorted_periods:
        for r in period["rows"]:
            raw_rows.append({
                "statement": period["statement"],
                "label": r["label"],
                "element": r["element"],
                "value": r["value"],
                "currency": period["currency"],
                "period_end": period["period_end"],
                "accession": period["accession"],
                "filing_date": period["filing_date"],
                "form": period["form"],
                "is_total": r["is_total"],
                "is_abstract": r["is_abstract"],
            })
            key = (r["label"], r["element"], period["period_end"])
            if key not in values and r["value"] is not None:
                values[key] = r["value"]

    # Build pivot rows
    pivot_rows: list[dict] = []
    for rm in row_meta:
        row = {"label": rm["label"], "element": rm["element"]}
        for pe in all_periods:
            row[pe] = values.get((rm["label"], rm["element"], pe))
        pivot_rows.append(row)

    return pivot_rows, raw_rows, row_meta
