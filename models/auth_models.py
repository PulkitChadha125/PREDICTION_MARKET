"""Pydantic models for auth/session related endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AuthStatusResponse(BaseModel):
    """Normalized response for IBKR auth/session status."""

    status: str = Field(..., examples=["success"])
    authenticated: bool = Field(..., description="Whether IBKR session appears active.")
    broker_response: dict[str, Any] = Field(
        ..., description="Raw response from IBKR Client Portal API."
    )


class AuthReadyResponse(BaseModel):
    """Stricter readiness check for brokerage endpoints."""

    status: str = Field(..., examples=["success"])
    authenticated: bool = Field(
        ..., description="True only when IBKR reports authenticated=true."
    )
    brokerage_ready: bool = Field(
        ..., description="True when account endpoints are accessible."
    )
    message: str
    auth_response: dict[str, Any]
    accounts_response: Any | None = None
