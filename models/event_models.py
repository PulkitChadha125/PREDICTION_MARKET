"""Pydantic models for event search and chain responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class EventTopic(BaseModel):
    """A single event topic/underlying candidate from secdef search."""

    conid: int | None = None
    symbol: str | None = None
    description: str | None = None
    sec_type: str | None = None
    exchange: str | None = None
    months: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class EventTopicSearchResponse(BaseModel):
    """Response for topic search endpoint."""

    status: str = "success"
    symbol: str
    sec_type: str
    topics: list[EventTopic]


class EventMarketTopic(BaseModel):
    """ForecastEx market topic extracted from category tree."""

    name: str
    symbol: str
    exchange: str
    conid: int
    category_id: str | None = None
    category_path: str | None = None


class AllTopicsResponse(BaseModel):
    """Response for listing all available prediction market topics."""

    status: str = "success"
    total_topics: int
    topics: list[EventMarketTopic]
    note: str | None = None


class ConsoleTopicItem(BaseModel):
    """Compact topic item designed for terminal/console readability."""

    index: int
    symbol: str
    name: str
    conid: int
    exchange: str
    months: list[str] = Field(default_factory=list)


class ConsoleTopicListResponse(BaseModel):
    """Compact list response for prediction market topics."""

    status: str = "success"
    total_topics: int
    topics: list[ConsoleTopicItem]
    note: str | None = None


class StrikeListResponse(BaseModel):
    """Response for available strike list endpoint."""

    status: str = "success"
    conid: str
    sectype: str
    month: str
    exchange: str
    strikes: list[float]
    broker_response: dict[str, Any]


class ContractLeg(BaseModel):
    """Represents YES or NO contract leg for one strike."""

    conid: int | None = None
    right: str | None = None
    label: str
    description: str | None = None
    maturity_date: str | None = None
    trading_class: str | None = None


class StrikeContractPair(BaseModel):
    """YES and NO pair grouped by strike."""

    strike: float
    yes_contract: ContractLeg | None = None
    no_contract: ContractLeg | None = None


class EventChainResponse(BaseModel):
    """Normalized chain response for frontend rendering."""

    status: str = "success"
    topic_symbol: str
    month: str
    exchange: str
    contracts: list[StrikeContractPair]


class EventChainRequest(BaseModel):
    """Input model for chain building from Swagger request body."""

    symbol: str | None = Field(
        default=None,
        description="Optional underlying symbol, e.g. UHSFO or FF.",
        examples=["UHSFO"],
    )
    conid: str | None = Field(
        default=None,
        description="Optional known topic conid for direct chain lookup.",
        examples=["845634818"],
    )
    month: str = Field(
        ...,
        description="Contract month in YYYYMM format.",
        examples=["202604"],
    )
    exchange: str = Field(
        ...,
        description="Exchange code, usually FORECASTX for prediction markets.",
        examples=["FORECASTX"],
    )
    sec_type: str = Field(
        default="IND",
        description="Security type for symbol discovery path.",
        examples=["IND"],
    )
    sectype: str = Field(
        default="OPT",
        description="Contract sec type used for strikes and contract info.",
        examples=["OPT"],
    )

    @model_validator(mode="after")
    def validate_symbol_or_conid(self) -> "EventChainRequest":
        if not self.symbol and not self.conid:
            raise ValueError("Provide at least one of 'symbol' or 'conid'.")
        return self


class ContractInfoResponse(BaseModel):
    """Response for fetching contract info at one strike."""

    status: str = "success"
    conid: str
    sectype: str
    month: str
    exchange: str
    strike: float
    contracts: list[dict[str, Any]]


class MarketQuoteItem(BaseModel):
    """Normalized market quote fields for one contract conid."""

    conid: int
    ltp: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class MarketQuoteResponse(BaseModel):
    """Quote snapshot response for one or multiple conids."""

    status: str = "success"
    total: int
    quotes: list[MarketQuoteItem]
