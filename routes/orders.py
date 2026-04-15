"""Order routes for YES/NO contract buying and live orders."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.order_models import (
    CancelOrderResponse,
    GenericOrderRequest,
    GenericOrderResponse,
    LiveOrdersResponse,
    OrderReplyRequest,
    OrderRequest,
    OrderResponse,
    WhatIfResponse,
)
from services.ibkr_client import IBKRClient, IBKRClientError
from services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])
ibkr_client = IBKRClient()
order_service = OrderService(ibkr_client)


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
