"""Business logic for prediction-market style event contract workflows."""

from __future__ import annotations

from typing import Any

from core.logger import get_logger
from models.event_models import (
    ContractLeg,
    EventMarketTopic,
    EventTopic,
    StrikeContractPair,
)
from services.ibkr_client import IBKRClient, IBKRClientError

logger = get_logger(__name__)
MAX_DISCOVERY_ATTEMPTS = 2


def map_right_to_label(right: str | None) -> str:
    """Map IBKR option right to frontend-friendly YES/NO label."""
    if right == "C":
        return "YES"
    if right == "P":
        return "NO"
    return "UNKNOWN"


class EventService:
    """Encapsulates event topic search, strike discovery, and chain normalization."""

    def __init__(self, client: IBKRClient) -> None:
        self.client = client

    def search_topics(self, symbol: str, sec_type: str = "IND") -> list[EventTopic]:
        """Search event topics / underlyings."""
        rows = self.client.secdef_search(symbol=symbol, sec_type=sec_type)
        topics: list[EventTopic] = []

        for item in rows:
            topics.append(
                EventTopic(
                    conid=item.get("conid"),
                    symbol=item.get("symbol"),
                    description=item.get("description"),
                    sec_type=item.get("secType"),
                    exchange=item.get("exchange"),
                    months=self._extract_months(item),
                    raw=item,
                )
            )
        return topics

    def get_all_prediction_topics(
        self, exchange_filter: str | None = None
    ) -> list[EventMarketTopic]:
        """
        Return all ForecastEx prediction market topics from category tree.

        IBKR provides this via /trsrv/event/category-tree.
        """
        tree = self.client.get_event_category_tree()
        topics: list[EventMarketTopic] = []
        seen: set[int] = set()
        normalized_exchange_filter = exchange_filter.upper() if exchange_filter else None

        for category_id, node in tree.items():
            if not isinstance(node, dict):
                continue
            raw_markets = node.get("markets", [])
            if not isinstance(raw_markets, list):
                continue

            category_path = self._build_category_path(tree, category_id)
            for market in raw_markets:
                if not isinstance(market, dict):
                    continue

                conid = market.get("conid")
                if not isinstance(conid, int) or conid in seen:
                    continue

                exchange = str(market.get("exchange", "")).upper()
                if normalized_exchange_filter and exchange != normalized_exchange_filter:
                    continue

                topics.append(
                    EventMarketTopic(
                        name=str(market.get("name", "")),
                        symbol=str(market.get("symbol", "")),
                        exchange=exchange,
                        conid=conid,
                        category_id=category_id,
                        category_path=category_path,
                    )
                )
                seen.add(conid)

        topics.sort(key=lambda t: ((t.category_path or ""), t.symbol, t.name))
        return topics

    def _extract_months(self, topic: dict[str, Any]) -> list[str]:
        """Extract months from secdef search payload if available."""
        month_values: list[str] = []

        months = topic.get("months")
        if isinstance(months, list):
            month_values.extend(str(m) for m in months)
        elif isinstance(months, str):
            month_values.extend(m.strip() for m in months.split(";") if m.strip())

        # IBKR often places tradable months under "sections".
        sections = topic.get("sections")
        if isinstance(sections, list):
            for section in sections:
                if not isinstance(section, dict):
                    continue
                section_months = section.get("months")
                if isinstance(section_months, str):
                    month_values.extend(
                        m.strip() for m in section_months.split(";") if m.strip()
                    )

        # Dedupe while preserving order.
        seen: set[str] = set()
        normalized: list[str] = []
        for value in month_values:
            if value not in seen:
                seen.add(value)
                normalized.append(value)
        return normalized

    def _build_category_path(self, tree: dict[str, Any], category_id: str) -> str:
        """Build human-readable category path (root -> ... -> leaf)."""
        path_labels: list[str] = []
        current_id: str | None = category_id
        visited: set[str] = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            node = tree.get(current_id, {})
            if not isinstance(node, dict):
                break
            label = node.get("label")
            if isinstance(label, str) and label.strip():
                path_labels.append(label.strip())
            parent_id = node.get("parentId")
            current_id = str(parent_id) if parent_id else None

        path_labels.reverse()
        return " / ".join(path_labels)

    def get_strikes(
        self, conid: str, sectype: str, month: str, exchange: str
    ) -> tuple[list[float], dict[str, Any]]:
        """Get available strikes and return both normalized and raw data."""
        data = self.client.get_strikes(
            conid=conid,
            sectype=sectype,
            month=month,
            exchange=exchange,
        )
        raw_values: list[Any] = []
        if isinstance(data, dict):
            # IBKR commonly returns {"call":[...], "put":[...]} for options.
            if isinstance(data.get("strikes"), list):
                raw_values.extend(data.get("strikes", []))
            if isinstance(data.get("call"), list):
                raw_values.extend(data.get("call", []))
            if isinstance(data.get("put"), list):
                raw_values.extend(data.get("put", []))

        numeric = [float(x) for x in raw_values if _is_number(x)]
        # Dedupe and sort for stable frontend output.
        strikes = sorted(set(numeric))
        return strikes, data

    def get_contracts_for_strike(
        self,
        conid: str,
        sectype: str,
        month: str,
        exchange: str,
        strike: float,
    ) -> list[dict[str, Any]]:
        """Get contracts for one strike from IBKR secdef info."""
        return self.client.get_contract_info(
            conid=conid,
            sectype=sectype,
            month=month,
            exchange=exchange,
            strike=strike,
        )

    def build_chain(
        self,
        symbol: str,
        sec_type: str,
        month: str,
        exchange: str,
        sectype: str,
    ) -> list[StrikeContractPair]:
        """
        Build normalized YES/NO chain:
        search topic -> get strikes -> map C/P into YES/NO contracts.
        """
        topics = self.search_topics(symbol=symbol, sec_type=sec_type)
        if not topics:
            return []

        conid_candidates = self._pick_conid_candidates(
            topics=topics, exchange=exchange, sectype=sectype
        )[:5]
        month_candidates = self._month_candidates(month)
        sectype_candidates = self._sectype_candidates(sectype)

        selected_conid: str | None = None
        selected_sectype: str | None = None
        selected_month: str | None = None
        strikes: list[float] = []
        last_error: IBKRClientError | None = None
        attempts = 0

        for candidate_conid in conid_candidates:
            for candidate_sectype in sectype_candidates:
                for candidate_month in month_candidates:
                    if attempts >= MAX_DISCOVERY_ATTEMPTS:
                        break
                    attempts += 1
                    try:
                        strike_rows, _ = self.get_strikes(
                            conid=candidate_conid,
                            sectype=candidate_sectype,
                            month=candidate_month,
                            exchange=exchange,
                        )
                        if strike_rows:
                            selected_conid = candidate_conid
                            selected_sectype = candidate_sectype
                            selected_month = candidate_month
                            strikes = strike_rows
                            break
                    except IBKRClientError as exc:
                        last_error = exc
                        continue
                if selected_conid:
                    break
                if attempts >= MAX_DISCOVERY_ATTEMPTS:
                    break
            if selected_conid:
                break
            if attempts >= MAX_DISCOVERY_ATTEMPTS:
                break

        if not selected_conid:
            # Fallback flow for CME/FOP style discovery:
            # secdef/info by month can return the full monthly chain directly.
            for candidate_conid in conid_candidates:
                for candidate_sectype in sectype_candidates:
                    for candidate_month in month_candidates:
                        if attempts >= MAX_DISCOVERY_ATTEMPTS:
                            break
                        attempts += 1
                        try:
                            month_rows = self.client.get_contracts_for_month(
                                conid=candidate_conid,
                                sectype=candidate_sectype,
                                month=candidate_month,
                                exchange=exchange,
                            )
                            filtered_rows = self._filter_event_contract_rows(
                                month_rows, exchange=exchange
                            )
                            if filtered_rows:
                                return self._normalize_contract_rows_by_strike(filtered_rows)
                        except IBKRClientError as exc:
                            last_error = exc
                            continue
                    if attempts >= MAX_DISCOVERY_ATTEMPTS:
                        break
                if attempts >= MAX_DISCOVERY_ATTEMPTS:
                    break

            if last_error:
                raise last_error
            logger.info(
                "No contracts found for symbol=%s month=%s exchange=%s sectype=%s after %s attempts",
                symbol,
                month,
                exchange,
                sectype,
                attempts,
            )
            return []

        pairs: list[StrikeContractPair] = []
        for strike in strikes:
            raw_contracts = self.get_contracts_for_strike(
                conid=selected_conid,
                sectype=selected_sectype or sectype,
                month=selected_month or month,
                exchange=exchange,
                strike=strike,
            )
            pairs.append(self._normalize_strike_contracts(strike, raw_contracts))
        return pairs

    def build_chain_from_conid(
        self,
        conid: str,
        month: str,
        exchange: str,
        sectype: str,
    ) -> list[StrikeContractPair]:
        """
        Build chain directly from known underlying conid.

        This is the fastest and most reliable flow once conid is known,
        matching IBKR Event Contract docs.
        """
        normalized_sectype = sectype.upper()
        if normalized_sectype == "FOP":
            rows = self.client.get_contracts_for_month(
                conid=conid,
                sectype=normalized_sectype,
                month=month,
                exchange=exchange,
            )
            event_rows = self._filter_event_contract_rows(rows, exchange=exchange)
            return self._normalize_contract_rows_by_strike(event_rows)

        strikes, _ = self.get_strikes(
            conid=conid, sectype=normalized_sectype, month=month, exchange=exchange
        )
        pairs: list[StrikeContractPair] = []
        for strike in strikes:
            rows = self.get_contracts_for_strike(
                conid=conid,
                sectype=normalized_sectype,
                month=month,
                exchange=exchange,
                strike=strike,
            )
            pairs.append(self._normalize_strike_contracts(strike, rows))
        return pairs

    def _pick_conid_candidates(
        self, topics: list[EventTopic], exchange: str, sectype: str
    ) -> list[str]:
        """Rank conid candidates by section compatibility before trying strikes."""
        preferred: list[str] = []
        fallback: list[str] = []
        wanted_exchange = exchange.upper()
        wanted_sectype = sectype.upper()

        for topic in topics:
            if topic.conid is None:
                continue
            conid = str(topic.conid)
            raw_sections = topic.raw.get("sections", [])
            if not isinstance(raw_sections, list):
                fallback.append(conid)
                continue

            matched = False
            for section in raw_sections:
                if not isinstance(section, dict):
                    continue
                section_exchange = str(section.get("exchange", "")).upper()
                section_sectype = str(section.get("secType", "")).upper()
                if section_exchange == wanted_exchange and section_sectype == wanted_sectype:
                    matched = True
                    break

            if matched:
                preferred.append(conid)
            else:
                fallback.append(conid)

        ordered = preferred + [c for c in fallback if c not in preferred]
        return ordered

    def _month_candidates(self, month: str) -> list[str]:
        """Generate month variants because IBKR can accept different month formats."""
        candidates = [month]
        if len(month) == 6 and month.isdigit():
            yyyy = month[:4]
            mm = month[4:]
            month_map = {
                "01": "JAN",
                "02": "FEB",
                "03": "MAR",
                "04": "APR",
                "05": "MAY",
                "06": "JUN",
                "07": "JUL",
                "08": "AUG",
                "09": "SEP",
                "10": "OCT",
                "11": "NOV",
                "12": "DEC",
            }
            mon = month_map.get(mm)
            if mon:
                candidates.append(f"{mon}{yyyy[-2:]}")
        return candidates

    def _sectype_candidates(self, sectype: str) -> list[str]:
        """Try requested sec type first, then common alternate for futures options."""
        upper = sectype.upper()
        candidates = [upper]
        if upper == "OPT":
            candidates.append("FOP")
        elif upper == "FOP":
            candidates.append("OPT")
        return candidates

    def _normalize_strike_contracts(
        self, strike: float, rows: list[dict[str, Any]]
    ) -> StrikeContractPair:
        """Normalize IBKR contracts at one strike into YES and NO legs."""
        yes_leg: ContractLeg | None = None
        no_leg: ContractLeg | None = None

        for row in rows:
            right = row.get("right")
            leg = ContractLeg(
                conid=row.get("conid"),
                right=right,
                label=map_right_to_label(right),
                description=row.get("desc2") or row.get("description"),
                maturity_date=row.get("maturityDate"),
                trading_class=row.get("tradingClass"),
            )
            if right == "C":
                yes_leg = leg
            elif right == "P":
                no_leg = leg

        return StrikeContractPair(strike=strike, yes_contract=yes_leg, no_contract=no_leg)

    def _filter_event_contract_rows(
        self, rows: list[dict[str, Any]], exchange: str
    ) -> list[dict[str, Any]]:
        """Filter monthly secdef/info rows to likely event contracts."""
        if exchange.upper() != "CME":
            return rows

        # CME monthly info can include regular futures options too.
        # Event contracts usually have trading class prefixed with "EC".
        filtered = []
        for row in rows:
            trading_class = str(row.get("tradingClass", "")).upper()
            if trading_class.startswith("EC"):
                filtered.append(row)
        return filtered

    def _normalize_contract_rows_by_strike(
        self, rows: list[dict[str, Any]]
    ) -> list[StrikeContractPair]:
        """Group contract rows by strike and normalize into YES/NO pairs."""
        grouped: dict[float, list[dict[str, Any]]] = {}
        for row in rows:
            strike_raw = row.get("strike")
            if not _is_number(strike_raw):
                continue
            strike = float(strike_raw)
            grouped.setdefault(strike, []).append(row)

        pairs: list[StrikeContractPair] = []
        for strike in sorted(grouped.keys()):
            pairs.append(self._normalize_strike_contracts(strike, grouped[strike]))
        return pairs


def _is_number(value: Any) -> bool:
    """Safe check for numeric values that can be converted to float."""
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
