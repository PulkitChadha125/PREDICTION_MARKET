"""Order routes for YES/NO contract buying and live orders."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.order_models import (
    CancelOrderResponse,
    GenericOrderRequest,
    GenericOrderResponse,
    HistoricalDataResponse,
    LiveOrdersResponse,
    NetPositionsResponse,
    OrderReplyRequest,
    OrderbookResponse,
    OrderRequest,
    OrderResponse,
    WhatIfResponse,
)
from services.ibkr_client import IBKRClient, IBKRClientError
from services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])
ibkr_client = IBKRClient()
order_service = OrderService(ibkr_client)


def _extract_order_rows(payload: object) -> list[dict]:
    """Normalize IBKR order payload shape to a flat list of order dicts."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("orders", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _order_status_value(order: dict) -> str:
    """Extract status from variable IBKR order response keys."""
    for key in ("status", "order_status", "orderStatus"):
        value = order.get(key)
        if isinstance(value, str):
            return value.strip().lower()
    return ""


def _normalize_statuses(statuses: str) -> list[str]:
    """Parse and normalize user-provided order status list."""
    allowed = {"open", "completed", "rejected", "canceled"}
    parsed = [chunk.strip().lower() for chunk in statuses.split(",") if chunk.strip()]
    if not parsed:
        return ["open", "completed", "rejected", "canceled"]
    deduped = list(dict.fromkeys(parsed))
    invalid = [item for item in deduped if item not in allowed]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported statuses: {invalid}. Allowed: {sorted(allowed)}",
        )
    return deduped


def _status_matches(raw_status: str, requested_status: str) -> bool:
    """Map normalized API statuses to IBKR status text variants."""
    raw = raw_status.lower()
    if requested_status == "open":
        return raw in {
            "submitted",
            "presubmitted",
            "pending submit",
            "pending_submit",
            "api pending",
            "api_pending",
            "open",
            "working",
            "partially filled",
            "partially_filled",
        }
    if requested_status == "completed":
        return raw in {"filled", "executed", "completed"}
    if requested_status == "rejected":
        return "reject" in raw or raw in {"inactive", "cancelled by system"}
    if requested_status == "canceled":
        return "cancel" in raw
    return False


@router.post("/yes", response_model=OrderResponse)
def place_yes_order(order: OrderRequest) -> OrderResponse:
    """
    Place BUY order for YES contract.

    Example:
    curl -k -X POST http://127.0.0.1:8000/orders/yes -H "Content-Type: application/json" -d "{\"account_id\":\"DU123456\",\"conid\":123456,\"quantity\":1,\"order_type\":\"MKT\",\"price\":null,\"tif\":\"DAY\"}"
    """
    try:
        result = order_service.place_yes_order(
            account_id=order.account_id,
            conid=order.conid,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price,
            tif=order.tif,
            auto_confirm=order.auto_confirm,
            sec_type_suffix=order.sec_type_suffix,
        )
        return OrderResponse(**result)
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/no", response_model=OrderResponse)
def place_no_order(order: OrderRequest) -> OrderResponse:
    """
    Place BUY order for NO contract.

    Example:
    curl -k -X POST http://127.0.0.1:8000/orders/no -H "Content-Type: application/json" -d "{\"account_id\":\"DU123456\",\"conid\":654321,\"quantity\":1,\"order_type\":\"MKT\",\"price\":null,\"tif\":\"DAY\"}"
    """
    try:
        result = order_service.place_no_order(
            account_id=order.account_id,
            conid=order.conid,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price,
            tif=order.tif,
            auto_confirm=order.auto_confirm,
            sec_type_suffix=order.sec_type_suffix,
        )
        return OrderResponse(**result)
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("", response_model=GenericOrderResponse)
def place_order(order: GenericOrderRequest) -> GenericOrderResponse:
    """Place BUY or SELL on a contract by conid (same IBKR payload as YES/NO routes)."""
    try:
        result = order_service.place_order(
            account_id=order.account_id,
            conid=order.conid,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price,
            tif=order.tif,
            auto_confirm=order.auto_confirm,
            sec_type_suffix=order.sec_type_suffix,
        )
        return GenericOrderResponse(**result)
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/whatif", response_model=WhatIfResponse)
def whatif_order(order: GenericOrderRequest) -> WhatIfResponse:
    """Preview commission / margin without submitting an order."""
    try:
        result = order_service.whatif_order(
            account_id=order.account_id,
            conid=order.conid,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price,
            tif=order.tif,
            sec_type_suffix=order.sec_type_suffix,
        )
        return WhatIfResponse(**result)
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/reply", response_model=GenericOrderResponse)
def reply_to_order_prompt(body: OrderReplyRequest) -> GenericOrderResponse:
    """
    Confirm or reject a broker prompt when an order was placed with auto_confirm=false.
    Use the `id` from the list item that contains `message`.
    """
    try:
        broker_response = ibkr_client.reply_to_order_prompt(
            reply_id=body.reply_id, confirmed=body.confirmed
        )
        return GenericOrderResponse(broker_response=broker_response)
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/{order_id}", response_model=CancelOrderResponse)
def cancel_order(
    order_id: str,
    account_id: str = Query(..., description="Account that owns the order."),
) -> CancelOrderResponse:
    """Cancel one open order. Per IBKR, order_id=-1 cancels all open orders for the account."""
    try:
        result = order_service.cancel_order(account_id=account_id, order_id=order_id)
        return CancelOrderResponse(**result)
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/live", response_model=LiveOrdersResponse)
def get_live_orders(account_id: str = Query(...)) -> LiveOrdersResponse:
    """Get live/open orders from IBKR for the given account."""
    try:
        broker_response = ibkr_client.get_live_orders(account_id=account_id)
        return LiveOrdersResponse(account_id=account_id, broker_response=broker_response)
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/historical", response_model=HistoricalDataResponse)
def get_historical_data(
    conid: int = Query(..., description="Contract ID to fetch historical bars for."),
    period: str = Query("1d", description="IBKR period, e.g. 1d, 1w, 1m."),
    bar: str = Query("1min", description="IBKR bar size, e.g. 1min, 5min, 1h."),
    exchange: str | None = Query(None, description="Optional exchange code."),
    outside_rth: bool = Query(
        True, description="Include outside regular trading hours bars."
    ),
    start_time: str | None = Query(
        None,
        description="Optional start time in IBKR format, e.g. 20260427-00:00:00.",
    ),
) -> HistoricalDataResponse:
    """Fetch historical market data bars from IBKR."""
    try:
        broker_response = ibkr_client.get_historical_data(
            conid=conid,
            period=period,
            bar=bar,
            exchange=exchange,
            outside_rth=outside_rth,
            start_time=start_time,
        )
        return HistoricalDataResponse(
            conid=conid,
            period=period,
            bar=bar,
            broker_response=broker_response,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/book", response_model=OrderbookResponse)
def get_orderbook(
    account_id: str = Query(..., description="Account ID whose orderbook is requested."),
    statuses: str = Query(
        "open,completed,rejected,canceled",
        description="Comma-separated statuses: open,completed,rejected,canceled",
    ),
) -> OrderbookResponse:
    """Fetch orderbook filtered by status buckets."""
    normalized_statuses = _normalize_statuses(statuses)
    ibkr_filters = [status for status in normalized_statuses if status != "completed"]
    try:
        broker_response = ibkr_client.get_orderbook(
            account_id=account_id, statuses=ibkr_filters or None
        )
        order_rows = _extract_order_rows(broker_response)
        filtered_orders = [
            order
            for order in order_rows
            if any(
                _status_matches(_order_status_value(order), requested)
                for requested in normalized_statuses
            )
        ]
        return OrderbookResponse(
            account_id=account_id,
            statuses=normalized_statuses,
            total=len(filtered_orders),
            orders=filtered_orders,
            broker_response=broker_response,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/netpositions", response_model=NetPositionsResponse)
def get_net_positions(
    account_id: str = Query(..., description="Account ID to fetch net positions for."),
    page: int = Query(0, ge=0, description="Portfolio page index."),
) -> NetPositionsResponse:
    """Fetch account net positions."""
    try:
        broker_response = ibkr_client.get_net_positions(account_id=account_id, page=page)
        return NetPositionsResponse(
            account_id=account_id,
            page=page,
            broker_response=broker_response,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
