"""Auth routes for IBKR session checks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.auth_models import AuthReadyResponse, AuthStatusResponse
from services.ibkr_client import IBKRClient, IBKRClientError

router = APIRouter(prefix="/auth", tags=["auth"])
ibkr_client = IBKRClient()


@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status() -> AuthStatusResponse:
    """
    Check IBKR Client Portal session/auth status.

    Example:
    curl -k http://127.0.0.1:8000/auth/status
    """
    try:
        broker_response = ibkr_client.get_auth_status()
        # Strict: only trust IBKR's authenticated flag.
        authenticated = bool(broker_response.get("authenticated"))
        return AuthStatusResponse(
            status="success",
            authenticated=authenticated,
            broker_response=broker_response,
        )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/ready", response_model=AuthReadyResponse)
def get_auth_ready() -> AuthReadyResponse:
    """
    Check whether brokerage endpoints are actually ready for trading/search.

    Example:
    curl -k http://127.0.0.1:8000/auth/ready
    """
    try:
        auth_response = ibkr_client.get_auth_status()
        authenticated = bool(auth_response.get("authenticated"))

        if not authenticated:
            return AuthReadyResponse(
                status="success",
                authenticated=False,
                brokerage_ready=False,
                message=(
                    "Not authenticated with IBKR gateway. "
                    "Open https://localhost:5000, login, then retry."
                ),
                auth_response=auth_response,
                accounts_response=None,
            )

        try:
            accounts = ibkr_client.get_accounts()
            return AuthReadyResponse(
                status="success",
                authenticated=True,
                brokerage_ready=True,
                message="IBKR session and brokerage bridge are ready.",
                auth_response=auth_response,
                accounts_response=accounts,
            )
        except IBKRClientError as accounts_exc:
            return AuthReadyResponse(
                status="success",
                authenticated=True,
                brokerage_ready=False,
                message=f"Authenticated but brokerage not ready: {accounts_exc}",
                auth_response=auth_response,
                accounts_response=None,
            )
    except IBKRClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
