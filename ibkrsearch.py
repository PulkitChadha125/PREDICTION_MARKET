"""Fetch ForecastX topics for symbols derived from pairs CSV and export to Excel.

Reads `pairs_20260414.csv`, extracts symbols from `event_contract` (example:
`UHCLT_041326_79` -> `UHCLT`), calls:
`/events/topics/console?symbols=<SYMBOL>&exchange=FORECASTX`
and writes output rows to an Excel file with response preview.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import requests
from openpyxl import Workbook


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export ForecastX topic lookups to Excel.")
    parser.add_argument(
        "--csv",
        default="pairs_20260414.csv",
        help="Input CSV path containing event_contract column.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="PredictionMarket API base URL.",
    )
    parser.add_argument(
        "--exchange",
        default="FORECASTX",
        help="Exchange passed to /events/topics/console.",
    )
    parser.add_argument(
        "--excel-output",
        default="prediction_market_symbols_from_pairs.xlsx",
        help="Output Excel path.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def extract_symbol(event_contract: str) -> str:
    """Normalize event contract prefix.

    Example:
      UHCLT_041326_79 -> UHCLT
    """
    prefix = (event_contract or "").strip().upper().split("_", 1)[0]
    return "".join(re.findall(r"[A-Z]+", prefix))


def iter_symbols_from_csv(csv_path: Path) -> Iterator[tuple[int, str, str]]:
    """Yield one extracted symbol per CSV row (lazy loading, no dedupe)."""
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for csv_row_number, row in enumerate(reader, start=2):
            event_contract = str(row.get("event_contract") or "")
            symbol = extract_symbol(event_contract)
            if symbol:
                yield csv_row_number, symbol, event_contract


def response_preview(payload: Any, limit: int = 280) -> str:
    text = json.dumps(payload, ensure_ascii=True)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def fetch_symbol_topics(
    base_url: str, symbol: str, exchange: str, timeout: float
) -> tuple[dict[str, Any] | None, str | None]:
    url = f"{base_url.rstrip('/')}/events/topics/console"
    try:
        resp = requests.get(
            url,
            params={"symbols": symbol, "exchange": exchange},
            timeout=timeout,
        )
        if not resp.ok:
            return None, f"HTTP {resp.status_code}: {resp.text[:180]}"
        payload = resp.json()
        if not isinstance(payload, dict):
            return None, "Response is not a JSON object"
        return payload, None
    except requests.RequestException as exc:
        return None, str(exc)
    except ValueError as exc:
        return None, f"Invalid JSON response: {exc}"


def iter_result_rows(
    csv_path: Path, base_url: str, exchange: str, timeout: float
) -> Iterator[dict[str, Any]]:
    """Yield output rows lazily while reading CSV and calling API per symbol."""
    for processed_count, (csv_row_number, symbol, event_contract) in enumerate(
        iter_symbols_from_csv(csv_path), start=1
    ):
        if processed_count % 100 == 1:
            print(f"[{processed_count}] fetching symbol={symbol}")
        payload, error = fetch_symbol_topics(base_url, symbol, exchange, timeout)

        if error:
            yield {
                "csv_row_number": csv_row_number,
                "event_contract": event_contract,
                "lookup_symbol": symbol,
                "index": None,
                "symbol": None,
                "name": None,
                "conid": None,
                "exchange": exchange,
                "months": None,
                "note": None,
                "response_preview": error,
            }
            continue

        topics = payload.get("topics", [])
        note = payload.get("note")

        # Keep one row even when no topic is found, so every symbol has traceability.
        if not isinstance(topics, list) or not topics:
            yield {
                "csv_row_number": csv_row_number,
                "event_contract": event_contract,
                "lookup_symbol": symbol,
                "index": None,
                "symbol": None,
                "name": None,
                "conid": None,
                "exchange": exchange,
                "months": None,
                "note": note,
                "response_preview": response_preview(payload),
            }
            continue

        for topic in topics:
            if not isinstance(topic, dict):
                continue
            months = topic.get("months")
            months_value = ";".join(str(m) for m in months) if isinstance(months, list) else ""
            yield {
                "csv_row_number": csv_row_number,
                "event_contract": event_contract,
                "lookup_symbol": symbol,
                "index": topic.get("index"),
                "symbol": topic.get("symbol"),
                "name": topic.get("name"),
                "conid": topic.get("conid"),
                "exchange": topic.get("exchange"),
                "months": months_value,
                "note": note,
                "response_preview": response_preview(payload),
            }


def write_excel(
    rows: Iterator[dict[str, Any]], output_path: Path, source_csv: Path
) -> tuple[int, int]:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "topics_from_csv"

    sheet.append(
        [
            "generated_at_utc",
            "source_csv",
            "csv_row_number",
            "event_contract",
            "lookup_symbol",
            "index",
            "symbol",
            "name",
            "conid",
            "exchange",
            "months",
            "note",
            "response_preview",
        ]
    )

    generated_at = datetime.now(UTC).isoformat()
    rows_written = 0
    matched_rows = 0
    for row in rows:
        rows_written += 1
        if row.get("conid") is not None:
            matched_rows += 1
        sheet.append(
            [
                generated_at,
                str(source_csv),
                row.get("csv_row_number"),
                row.get("event_contract"),
                row.get("lookup_symbol"),
                row.get("index"),
                row.get("symbol"),
                row.get("name"),
                row.get("conid"),
                row.get("exchange"),
                row.get("months"),
                row.get("note"),
                row.get("response_preview"),
            ]
        )

    # Basic widths for readability.
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 24
    sheet.column_dimensions["C"].width = 12
    sheet.column_dimensions["D"].width = 18
    sheet.column_dimensions["E"].width = 14
    sheet.column_dimensions["F"].width = 8
    sheet.column_dimensions["G"].width = 12
    sheet.column_dimensions["H"].width = 52
    sheet.column_dimensions["I"].width = 14
    sheet.column_dimensions["J"].width = 14
    sheet.column_dimensions["K"].width = 24
    sheet.column_dimensions["L"].width = 22
    sheet.column_dimensions["M"].width = 90

    workbook.save(output_path)
    return rows_written, matched_rows


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    excel_path = Path(args.excel_output)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows = iter_result_rows(
        csv_path=csv_path,
        base_url=args.base_url,
        exchange=args.exchange,
        timeout=args.timeout,
    )
    rows_written, matched = write_excel(rows, excel_path, csv_path)

    print("Done. Processed all symbols from CSV with lazy row-by-row fetching.")
    print(f"Rows written: {rows_written} | matched topic rows: {matched}")
    print(f"Excel output: {excel_path}")


if __name__ == "__main__":
    main()