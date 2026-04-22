"""Probe IBKR gateway with symbols extracted from CME event CSV.

This script talks directly to Client Portal Gateway (default port 5000) and
tries multiple secType values per symbol to discover conids that can be used
for downstream chain/order flows.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import urllib3


@dataclass
class SearchHit:
    source_symbol: str
    sec_type_used: str
    conid: int | None
    symbol: str | None
    sec_type: str | None
    exchange: str | None
    description: str | None
    company_name: str | None
    sections: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover CME event contract conids from CSV symbols via IBKR gateway."
    )
    parser.add_argument(
        "--csv",
        default="CME.EventContracts.20260421.csv",
        help="Input CSV file that contains event contract rows.",
    )
    parser.add_argument(
        "--base-url",
        default="https://localhost:5000/v1/api",
        help="IBKR Client Portal base URL.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="HTTP timeout (seconds).",
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Enable TLS certificate verification for HTTPS requests.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=0,
        help="Optional cap on number of symbols to query (0 = all).",
    )
    parser.add_argument(
        "--out-json",
        default="cme_event_symbol_discovery.json",
        help="Output JSON file.",
    )
    parser.add_argument(
        "--out-csv",
        default="cme_event_symbol_discovery.csv",
        help="Output CSV file.",
    )
    return parser.parse_args()


def _itc_prefix(value: str) -> str:
    """Extract product code from ITCCode like 'ECD10J622 C5000' -> 'ECD10'."""
    token = (value or "").strip().split(" ", 1)[0].upper()
    if not token:
        return ""
    prefix = []
    for char in token:
        if char.isalpha() or char.isdigit():
            prefix.append(char)
            continue
        break
    text = "".join(prefix)
    # Drop trailing expiry chunk after first month code letter if present.
    # Example ECD10J622 -> ECD10
    for idx, char in enumerate(text):
        if idx >= 3 and char in "FGHJKMNQUVXZ":
            return text[:idx]
    return text


def extract_symbols(csv_path: Path) -> list[str]:
    """Build ordered unique symbol list from CSV columns."""
    ordered: OrderedDict[str, None] = OrderedDict()
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for key in ("UndCode", "PFCode"):
                value = str(row.get(key) or "").strip().upper()
                if value:
                    ordered.setdefault(value, None)
            itc_symbol = _itc_prefix(str(row.get("ITCCode") or ""))
            if itc_symbol:
                ordered.setdefault(itc_symbol, None)
    return list(ordered.keys())


def fetch_search(
    session: requests.Session,
    base_url: str,
    symbol: str,
    sec_type: str,
    timeout: float,
    verify_ssl: bool,
) -> list[dict[str, Any]]:
    endpoint = f"{base_url.rstrip('/')}/iserver/secdef/search"
    resp = session.get(
        endpoint,
        params={"symbol": symbol, "secType": sec_type},
        timeout=timeout,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload if isinstance(payload, list) else []


def map_hit(source_symbol: str, sec_type_used: str, row: dict[str, Any]) -> SearchHit:
    sections = row.get("sections")
    normalized_sections = sections if isinstance(sections, list) else []
    return SearchHit(
        source_symbol=source_symbol,
        sec_type_used=sec_type_used,
        conid=row.get("conid"),
        symbol=row.get("symbol"),
        sec_type=row.get("secType"),
        exchange=row.get("exchange"),
        description=row.get("description"),
        company_name=row.get("companyName"),
        sections=[s for s in normalized_sections if isinstance(s, dict)],
    )


def write_csv(path: Path, hits: list[SearchHit]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "source_symbol",
                "sec_type_used",
                "conid",
                "symbol",
                "sec_type",
                "exchange",
                "description",
                "company_name",
                "sections_json",
            ]
        )
        for hit in hits:
            writer.writerow(
                [
                    hit.source_symbol,
                    hit.sec_type_used,
                    hit.conid,
                    hit.symbol,
                    hit.sec_type,
                    hit.exchange,
                    hit.description,
                    hit.company_name,
                    json.dumps(hit.sections, ensure_ascii=True),
                ]
            )


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    if not args.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()

    symbols = extract_symbols(csv_path)
    if args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]

    sec_types = ("FOP", "FUT", "IND", "OPT")
    all_hits: list[SearchHit] = []
    seen_keys: set[tuple[str, str, int | None]] = set()
    scanned = 0

    for symbol in symbols:
        scanned += 1
        if scanned % 50 == 1:
            print(f"[{scanned}/{len(symbols)}] searching symbol={symbol}")
        for sec_type in sec_types:
            try:
                rows = fetch_search(
                    session=session,
                    base_url=args.base_url,
                    symbol=symbol,
                    sec_type=sec_type,
                    timeout=args.timeout,
                    verify_ssl=args.verify_ssl,
                )
            except requests.RequestException as exc:
                print(f"[WARN] {symbol}/{sec_type} request failed: {exc}")
                continue
            except ValueError as exc:
                print(f"[WARN] {symbol}/{sec_type} invalid JSON: {exc}")
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue
                mapped = map_hit(symbol, sec_type, row)
                key = (mapped.source_symbol, mapped.sec_type_used, mapped.conid)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_hits.append(mapped)

    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)

    payload = {
        "input_csv": str(csv_path),
        "base_url": args.base_url,
        "verify_ssl": args.verify_ssl,
        "symbols_scanned": len(symbols),
        "hits": [
            {
                "source_symbol": h.source_symbol,
                "sec_type_used": h.sec_type_used,
                "conid": h.conid,
                "symbol": h.symbol,
                "sec_type": h.sec_type,
                "exchange": h.exchange,
                "description": h.description,
                "company_name": h.company_name,
                "sections": h.sections,
            }
            for h in all_hits
        ],
    }
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    write_csv(out_csv, all_hits)

    unique_conids = {h.conid for h in all_hits if h.conid is not None}
    print(f"Done. symbols_scanned={len(symbols)} hits={len(all_hits)} conids={len(unique_conids)}")
    print(f"JSON: {out_json}")
    print(f"CSV : {out_csv}")


if __name__ == "__main__":
    main()
