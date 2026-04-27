"""Pydantic models for order request and response."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class OrderRequest(BaseModel):
    """Incoming order payload used for YES/NO order placement."""

    account_id: str = Field(..., examples=["DU123456"])
    conid: int = Field(..., examples=[12345678])
    quantity: int = Field(..., gt=0)
    order_type: str = Field(default="MKT", examples=["MKT", "LMT"])
    price: float | None = Field(default=None, ge=0)
    tif: str = Field(default="DAY", examples=["DAY", "GTC"])
    auto_confirm: bool = Field(
        default=True,
        description="If True, automatically POST /iserver/reply for IBKR warning prompts.",
    )
    sec_type_suffix: str = Field(
        default="OPT",
        description="Suffix for secType, e.g. conid:OPT for event options.",
    )

    @field_validator("order_type")
    @classmethod
    def normalize_order_type(cls, value: str) -> str:
        """Normalize order type casing."""
        return value.upper()

    @field_validator("tif")
    @classmethod
    def normalize_tif(cls, value: str) -> str:
        """Normalize TIF casing."""
        return value.upper()

    @field_validator("sec_type_suffix")
    @classmethod
    def normalize_sec_type_suffix(cls, value: str) -> str:
        return value.upper()


class GenericOrderRequest(OrderRequest):
    """Place any BUY/SELL on a contract (same fields as OrderRequest plus side)."""

    side: Literal["BUY", "SELL"] = Field(default="BUY")

    @field_validator("side", mode="before")
    @classmethod
    def normalize_side(cls, value: str) -> str:
        if isinstance(value, str):
            return value.upper()
        return value


class OrderReplyRequest(BaseModel):
    """Answer a pending IBKR order prompt when auto_confirm was false."""

    reply_id: str = Field(..., description="The `id` field from the broker's prompt object.")
    confirmed: bool = Field(default=True)


class OrderResponse(BaseModel):
    """Normalized order placement response."""

    status: str
    side: str
    broker_response: Any


class GenericOrderResponse(BaseModel):
    """Response for generic BUY/SELL placement."""

    status: str = "success"
    broker_response: Any


class WhatIfResponse(BaseModel):
    """Broker preview for an order without submitting."""

    status: str = "success"
    broker_response: Any


class CancelOrderResponse(BaseModel):
    """Response after requesting order cancellation."""

    status: str = "success"
    account_id: str
    order_id: str
    broker_response: Any


class LiveOrdersResponse(BaseModel):
    """Normalized response for open/live orders."""

    status: str = "success"
    account_id: str
    broker_response: Any


class HistoricalDataResponse(BaseModel):
    """Historical bars response passthrough."""

    status: str = "success"
    conid: int
    period: str
    bar: str
    broker_response: Any


class OrderbookResponse(BaseModel):
    """Normalized orderbook response with requested statuses."""

    status: str = "success"
    account_id: str
    statuses: list[str]
    total: int
    orders: list[dict[str, Any]]
    broker_response: Any


class NetPositionsResponse(BaseModel):
    """Net positions response for account."""

    status: str = "success"
    account_id: str
    page: int
    broker_response: Any
