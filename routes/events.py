"""Event/contract discovery routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.event_models import (
    AllTopicsResponse,
    ConsoleTopicItem,
    ConsoleTopicListResponse,
    ContractInfoResponse,
    EventChainResponse,
    EventTopicSearchResponse,
    StrikeListResponse,
)
from services.event_service import EventService
from services.ibkr_client import IBKRClient, IBKRClientError

router = APIRouter(prefix="/events", tags=["events"])
event_service = EventService(IBKRClient())


@router.get("/search", response_model=EventTopicSearchResponse)
def search_events(
    symbol: str = Query(..., description="Underlying symbol, e.g. NQ"),
    sec_type: str = Query("IND", description="Security type for search"),
) -> EventTopicSearchResponse:
    """Search event topics/underlyings using IBKR secdef search."""
    try:
        topics = event_service.search_topics(symbol=symbol, sec_type=sec_type)
        return EventTopicSearchResponse(
            status="success",
            symbol=symbol,
            sec_type=sec_type,
            topics=topics,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/topics/all", response_model=AllTopicsResponse)
def get_all_topics(
    exchange: str | None = Query(
        "FORECASTX",
        description="Optional exchange filter, default FORECASTX for prediction markets.",
    ),
) -> AllTopicsResponse:
    """
    Fetch all prediction market topics from IBKR category tree.

    Example:
    curl -k "http://127.0.0.1:8000/events/topics/all?exchange=FORECASTX"
    """
    try:
        topics = event_service.get_all_prediction_topics(exchange_filter=exchange)
        return AllTopicsResponse(status="success", total_topics=len(topics), topics=topics)
    except IBKRClientError as exc:
        if "category tree endpoint is not available" in str(exc).lower():
            return AllTopicsResponse(
                status="success",
                total_topics=0,
                topics=[],
                note=str(exc),
            )
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/topics/console", response_model=ConsoleTopicListResponse)
def get_prediction_topics_console(
    symbols: str | None = Query(
        None,
        description=(
            "Comma-separated topic symbols to probe, e.g. FF,USIP,CPI,GDP. "
            "If omitted, API will try to fetch all topics from category-tree endpoint."
        ),
    ),
    exchange: str = Query("FORECASTX", description="Prediction market exchange filter"),
) -> ConsoleTopicListResponse:
    """
    Return compact prediction-market topic list for console usage.

    Example:
    curl -k "http://127.0.0.1:8000/events/topics/console?symbols=FF,USIP&exchange=FORECASTX"
    """
    try:
        exchange_upper = exchange.upper()
        # If symbols are not provided, attempt full category-tree retrieval.
        if not symbols:
            try:
                all_topics = event_service.get_all_prediction_topics(
                    exchange_filter=exchange_upper
                )
                compact_rows = [
                    ConsoleTopicItem(
                        index=idx,
                        symbol=t.symbol,
                        name=t.name,
                        conid=t.conid,
                        exchange=t.exchange,
                        months=[],
                    )
                    for idx, t in enumerate(all_topics, start=1)
                ]
                return ConsoleTopicListResponse(
                    status="success",
                    total_topics=len(compact_rows),
                    topics=compact_rows,
                )
            except IBKRClientError as exc:
                return ConsoleTopicListResponse(
                    status="success",
                    total_topics=0,
                    topics=[],
                    note=(
                        "All-topics endpoint is unavailable on this gateway build. "
                        "Pass symbols list explicitly, e.g. ?symbols=FF,USIP."
                        f" Details: {exc}"
                    ),
                )

        cleaned_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        seen: set[int] = set()
        compact_rows: list[ConsoleTopicItem] = []

        for sym in cleaned_symbols:
            topics = event_service.search_topics(symbol=sym, sec_type="IND")
            for topic in topics:
                if topic.conid is None:
                    continue

                raw = topic.raw or {}
                topic_exchange = str(topic.description or raw.get("description", "")).upper()
                raw_sections = raw.get("sections", [])
                if not isinstance(raw_sections, list):
                    raw_sections = []
                has_ec_section = any(
                    isinstance(section, dict)
                    and str(section.get("secType", "")).upper() == "EC"
                    for section in raw_sections
                )

                if exchange_upper not in topic_exchange and not has_ec_section:
                    continue
                if topic.conid in seen:
                    continue

                compact_rows.append(
                    ConsoleTopicItem(
                        index=0,  # assigned below after sorting
                        symbol=str(topic.symbol or sym),
                        name=str(raw.get("companyName") or topic.symbol or sym),
                        conid=int(topic.conid),
                        exchange=exchange_upper,
                        months=topic.months,
                    )
                )
                seen.add(topic.conid)

        compact_rows.sort(key=lambda row: (row.symbol, row.name, row.conid))
        for idx, row in enumerate(compact_rows, start=1):
            row.index = idx

        return ConsoleTopicListResponse(
            status="success",
            total_topics=len(compact_rows),
            topics=compact_rows,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/strikes", response_model=StrikeListResponse)
def get_strikes(
    conid: str,
    sectype: str,
    month: str,
    exchange: str,
) -> StrikeListResponse:
    """Return available strikes for selected contract month."""
    try:
        strikes, broker_response = event_service.get_strikes(
            conid=conid, sectype=sectype, month=month, exchange=exchange
        )
        return StrikeListResponse(
            conid=conid,
            sectype=sectype,
            month=month,
            exchange=exchange,
            strikes=strikes,
            broker_response=broker_response,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/contracts", response_model=ContractInfoResponse)
def get_contracts(
    conid: str,
    sectype: str,
    month: str,
    exchange: str,
    strike: float,
) -> ContractInfoResponse:
    """Get raw contract info for a single strike."""
    try:
        contracts = event_service.get_contracts_for_strike(
            conid=conid,
            sectype=sectype,
            month=month,
            exchange=exchange,
            strike=strike,
        )
        return ContractInfoResponse(
            conid=conid,
            sectype=sectype,
            month=month,
            exchange=exchange,
            strike=strike,
            contracts=contracts,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/chain", response_model=EventChainResponse)
def get_chain(
    symbol: str = Query(..., description="Underlying symbol, e.g. NQ"),
    sec_type: str = Query("IND"),
    month: str = Query(..., description="Option month, e.g. 202605"),
    exchange: str = Query(..., description="Exchange code"),
    sectype: str = Query("OPT", description="Contract sec type used for strikes/info"),
    conid: str | None = Query(
        default=None,
        description="Optional known underlying conid to skip search and speed up chain fetch.",
    ),
) -> EventChainResponse:
    """
    Build normalized YES/NO chain.

    Example:
    curl -k "http://127.0.0.1:8000/events/chain?symbol=NQ&sec_type=IND&month=202605&exchange=CME&sectype=OPT"
    """
    try:
        if conid:
            contracts = event_service.build_chain_from_conid(
                conid=conid, month=month, exchange=exchange, sectype=sectype
            )
        else:
            contracts = event_service.build_chain(
                symbol=symbol,
                sec_type=sec_type,
                month=month,
                exchange=exchange,
                sectype=sectype,
            )
        return EventChainResponse(
            status="success",
            topic_symbol=symbol,
            month=month,
            exchange=exchange,
            contracts=contracts,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/discover", response_model=EventTopicSearchResponse)
def discover_underlyings(
    symbol: str = Query(..., description="Event product symbol, e.g. NQ or FF"),
    sec_type: str = Query("IND", description="Usually IND for event underlyings"),
    exchange: str | None = Query(
        default=None, description="Optional exchange filter, e.g. CME or FORECASTX"
    ),
) -> EventTopicSearchResponse:
    """
    Discover underlying records and conids before chain retrieval.

    Example:
    curl -k "http://127.0.0.1:8000/events/discover?symbol=NQ&sec_type=IND&exchange=CME"
    """
    try:
        topics = event_service.search_topics(symbol=symbol, sec_type=sec_type)
        if exchange:
            exchange_upper = exchange.upper()
            topics = [
                t
                for t in topics
                if exchange_upper in str((t.raw or {}).get("description", "")).upper()
                or exchange_upper in str((t.raw or {}).get("exchange", "")).upper()
            ]
        return EventTopicSearchResponse(
            status="success", symbol=symbol, sec_type=sec_type, topics=topics
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
