"""Reusable HTTP client wrapper for IBKR Client Portal Web API."""

from __future__ import annotations
from typing import Any

import requests
import urllib3

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class IBKRClientError(Exception):
    """Raised when IBKR API request fails with a clean readable message."""


class IBKRClient:
    """
    Thin reusable client for Client Portal gateway calls.

    Notes:
    - This backend uses IBKR Client Portal Web API.
    - Gateway must already be running and logged in at https://localhost:5000.
    - The API is session-based and best for local testing/prototyping.
    """

    def __init__(self) -> None:
        self.base_url = settings.base_url.rstrip("/")
        self.verify_ssl = settings.verify_ssl
        self.timeout = settings.request_timeout_seconds
        self.session = requests.Session()

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """Centralized HTTP request with consistent error handling and logging."""
        try:
            response = self._raw_request(method=method, endpoint=endpoint, **kwargs)
            response.raise_for_status()
            if response.text.strip():
                return response.json()
            return {}
        except requests.exceptions.HTTPError as exc:
            text = exc.response.text if exc.response is not None else str(exc)
            if self._should_retry_for_unauthorized(exc.response, endpoint):
                logger.warning(
                    "Detected unauthorized session for %s %s. Reauthenticating and retrying once.",
                    method,
                    endpoint,
                )
                self.initialize_brokerage_session()
                try:
                    retry_response = self._raw_request(
                        method=method, endpoint=endpoint, **kwargs
                    )
                    retry_response.raise_for_status()
                    if retry_response.text.strip():
                        return retry_response.json()
                    return {}
                except requests.exceptions.HTTPError as retry_exc:
                    detail = self._format_http_error_message(
                        retry_exc.response, fallback=str(retry_exc)
                    )
                    logger.error(
                        "IBKR HTTP retry error on %s %s: %s", method, endpoint, detail
                    )
                    raise IBKRClientError(f"IBKR HTTP error: {detail}") from retry_exc
            # Common IBKR session issue: bridge is not initialized.
            if self._should_retry_for_no_bridge(exc.response, endpoint):
                logger.warning(
                    "Detected 'no bridge' for %s %s. Initializing session and retrying once.",
                    method,
                    endpoint,
                )
                self.initialize_brokerage_session()
                try:
                    retry_response = self._raw_request(
                        method=method, endpoint=endpoint, **kwargs
                    )
                    retry_response.raise_for_status()
                    if retry_response.text.strip():
                        return retry_response.json()
                    return {}
                except requests.exceptions.HTTPError as retry_exc:
                    detail = self._format_http_error_message(
                        retry_exc.response, fallback=str(retry_exc)
                    )
                    logger.error(
                        "IBKR HTTP retry error on %s %s: %s", method, endpoint, detail
                    )
                    raise IBKRClientError(f"IBKR HTTP error: {detail}") from retry_exc
            detail = self._format_http_error_message(exc.response, fallback=text)
            logger.error("IBKR HTTP error on %s %s: %s", method, endpoint, detail)
            raise IBKRClientError(f"IBKR HTTP error: {detail}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("IBKR request failed on %s %s: %s", method, endpoint, exc)
            raise IBKRClientError(f"Could not reach IBKR gateway: {exc}") from exc
        except ValueError as exc:
            logger.error("IBKR returned non-JSON response for %s %s", method, endpoint)
            raise IBKRClientError("IBKR returned invalid JSON response.") from exc

    @staticmethod
    def _format_http_error_message(
        response: requests.Response | None, fallback: str
    ) -> str:
        """Build readable HTTP error details even when response body is empty."""
        if response is None:
            return fallback or "Unknown HTTP error"

        status = response.status_code
        reason = (response.reason or "").strip()
        body = response.text.strip()

        if body:
            return f"HTTP {status} {reason} - {body}".strip()
        if reason:
            return f"HTTP {status} {reason}"
        return f"HTTP {status}"

    def _raw_request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        """Send an HTTP request to IBKR without parsing response."""
        url = f"{self.base_url}{endpoint}"
        params = kwargs.get("params")
        json_body = kwargs.get("json")
        data_body = kwargs.get("data")

        debug_parts: list[str] = [f"{method.upper()} {url}"]
        if params is not None:
            debug_parts.append(f"params={params}")
        if json_body is not None:
            debug_parts.append(f"json={json_body}")
        if data_body is not None:
            debug_parts.append(f"data={data_body}")

        debug_line = " | ".join(debug_parts)
        # Keep explicit print so requests are always visible in terminal console.
        print(f"[IBKR REQUEST] {debug_line}")
        logger.info("IBKR request: %s", debug_line)

        return self.session.request(
            method=method,
            url=url,
            verify=self.verify_ssl,
            timeout=self.timeout,
            **kwargs,
        )

    def _should_retry_for_no_bridge(
        self, response: requests.Response | None, endpoint: str
    ) -> bool:
        """Check whether IBKR returned the known 'no bridge' session error."""
        if response is None:
            return False
        if not endpoint.startswith("/iserver/"):
            return False
        message = response.text.lower()
        return "no bridge" in message

    def _should_retry_for_unauthorized(
        self, response: requests.Response | None, endpoint: str
    ) -> bool:
        """Retry iServer endpoints once when gateway session returns 401."""
        if response is None:
            return False
        if not endpoint.startswith("/iserver/"):
            return False
        return response.status_code == 401

    def initialize_brokerage_session(self) -> None:
        """
        Best-effort bridge/session warm-up for IBKR.

        Steps are intentionally simple:
        1) Tickle gateway
        2) Re-authenticate iServer
        3) Touch account list endpoint
        """
        try:
            self._raw_request("POST", "/tickle").raise_for_status()
            self._raw_request("POST", "/iserver/reauthenticate").raise_for_status()
            self._raw_request("GET", "/iserver/accounts").raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to initialize IBKR brokerage session: %s", exc)
            raise IBKRClientError(
                "IBKR gateway is up but brokerage bridge is not ready. "
                "Open https://localhost:5000 in browser, complete login, then retry."
            ) from exc

    def get_auth_status(self) -> dict[str, Any]:
        """Check current Client Portal auth/session status."""
        return self._request("GET", "/iserver/auth/status")

    def secdef_search(self, symbol: str, sec_type: str = "IND") -> list[dict[str, Any]]:
        """Search underlyings/topics that can be used for event contracts."""
        params = {"symbol": symbol, "secType": sec_type}
        data = self._request("GET", "/iserver/secdef/search", params=params)
        return data if isinstance(data, list) else []

    def get_strikes(
        self, conid: str, sectype: str, month: str, exchange: str
    ) -> dict[str, Any]:
        """Fetch available strikes for an underlying/month."""
        params = {
            "conid": conid,
            "sectype": sectype,
            "month": month,
            "exchange": exchange,
        }
        return self._request("GET", "/iserver/secdef/strikes", params=params)

    def get_contract_info(
        self,
        conid: str,
        sectype: str,
        month: str,
        exchange: str,
        strike: float,
        right: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch contract metadata for a strike (and optional right side C/P)."""
        params: dict[str, Any] = {
            "conid": conid,
            "sectype": sectype,
            "month": month,
            "exchange": exchange,
            "strike": strike,
        }
        if right:
            params["right"] = right

        data = self._request("GET", "/iserver/secdef/info", params=params)
        return data if isinstance(data, list) else []

    def get_market_snapshot(
        self, conids: list[int], fields: str = "31,84,85,86,88,7059"
    ) -> list[dict[str, Any]]:
        """Get latest market snapshot for one or many contract IDs."""
        params = {"conids": ",".join(str(cid) for cid in conids), "fields": fields}
        data = self._request("GET", "/iserver/marketdata/snapshot", params=params)
        return data if isinstance(data, list) else []

    def _build_single_order_body(
        self,
        account_id: str,
        conid: int,
        side: str,
        quantity: int,
        order_type: str,
        price: float | None,
        tif: str,
        sec_type_suffix: str = "OPT",
    ) -> dict[str, Any]:
        """Single order object for /orders and /orders/whatif (Client Portal shape)."""
        order: dict[str, Any] = {
            "acctId": account_id,
            "conid": conid,
            "secType": f"{conid}:{sec_type_suffix}",
            "orderType": order_type,
            "side": side.upper(),
            "quantity": quantity,
            "tif": tif.upper(),
        }
        if price is not None:
            order["price"] = price
        return order

    def _resolve_order_replies(
        self,
        data: Any,
        *,
        auto_confirm: bool = True,
        max_rounds: int = 15,
    ) -> Any:
        """
        IBKR often returns a list whose first element includes `message` + `id`
        (reply id). Each prompt must be answered via POST /iserver/reply/{id}.
        """
        for _ in range(max_rounds):
            if isinstance(data, dict) and data.get("error"):
                raise IBKRClientError(f"IBKR order error: {data.get('error')}")

            if not isinstance(data, list) or not data:
                return data

            first = data[0]
            if not isinstance(first, dict):
                return data

            if "message" not in first:
                return data[0] if len(data) == 1 else data

            if not auto_confirm:
                return data

            reply_id = first.get("id")
            if reply_id is None:
                return data

            data = self._request(
                "POST",
                f"/iserver/reply/{reply_id}",
                json={"confirmed": True},
            )

        raise IBKRClientError(
            f"Order submission exceeded {max_rounds} IBKR confirmation rounds; last: {data!r}"
        )

    def place_order(
        self,
        account_id: str,
        conid: int,
        side: str,
        quantity: int,
        order_type: str = "MKT",
        price: float | None = None,
        tif: str = "DAY",
        *,
        auto_confirm: bool = True,
        sec_type_suffix: str = "OPT",
    ) -> Any:
        """Place an order; follows IBKR reply prompts when auto_confirm is True."""
        payload = {
            "orders": [
                self._build_single_order_body(
                    account_id=account_id,
                    conid=conid,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    price=price,
                    tif=tif,
                    sec_type_suffix=sec_type_suffix,
                )
            ]
        }
        initial = self._request(
            "POST", f"/iserver/account/{account_id}/orders", json=payload
        )
        return self._resolve_order_replies(initial, auto_confirm=auto_confirm)

    def reply_to_order_prompt(self, reply_id: str, confirmed: bool) -> Any:
        """Answer a single IBKR order warning (used if place_order was called with auto_confirm=False)."""
        return self._request(
            "POST",
            f"/iserver/reply/{reply_id}",
            json={"confirmed": confirmed},
        )

    def whatif_order(
        self,
        account_id: str,
        conid: int,
        side: str,
        quantity: int,
        order_type: str = "MKT",
        price: float | None = None,
        tif: str = "DAY",
        sec_type_suffix: str = "OPT",
    ) -> Any:
        """Preview commission / margin without submitting (same body shape as place_order)."""
        payload = {
            "orders": [
                self._build_single_order_body(
                    account_id=account_id,
                    conid=conid,
                    side=side,
                    quantity=quantity,
                    order_type=order_type,
                    price=price,
                    tif=tif,
                    sec_type_suffix=sec_type_suffix,
                )
            ]
        }
        return self._request(
            "POST",
            f"/iserver/account/{account_id}/orders/whatif",
            json=payload,
        )

    def cancel_order(self, account_id: str, order_id: str) -> Any:
        """Cancel one open order by id (use '-1' to cancel all open orders per IBKR)."""
        return self._request(
            "DELETE",
            f"/iserver/account/{account_id}/order/{order_id}",
        )

    def get_live_orders(self, account_id: str) -> Any:
        """Fetch live/open orders for an account."""
        params = {"accountId": account_id}
        return self._request("GET", "/iserver/account/orders", params=params)

    def get_historical_data(
        self,
        conid: int,
        period: str = "1d",
        bar: str = "1min",
        exchange: str | None = None,
        outside_rth: bool = True,
        start_time: str | None = None,
    ) -> Any:
        """Fetch historical OHLCV bars from IBKR marketdata history endpoint."""
        params: dict[str, Any] = {
            "conid": conid,
            "period": period,
            "bar": bar,
            "outsideRth": str(outside_rth).lower(),
        }
        if exchange:
            params["exchange"] = exchange
        if start_time:
            params["startTime"] = start_time
        return self._request("GET", "/iserver/marketdata/history", params=params)

    def get_orderbook(self, account_id: str, statuses: list[str] | None = None) -> Any:
        """
        Fetch account orders and optionally request IBKR-side status filtering.

        IBKR gateway behavior can vary by build, so callers should still apply
        local filtering as needed.
        """
        params: dict[str, Any] = {"accountId": account_id}
        if statuses:
            params["filters"] = ",".join(statuses)
        return self._request("GET", "/iserver/account/orders", params=params)

    def get_net_positions(self, account_id: str, page: int = 0) -> Any:
        """Fetch account net positions from IBKR portfolio endpoint."""
        return self._request("GET", f"/portfolio/{account_id}/positions/{page}")

    def get_accounts(self) -> Any:
        """Fetch accessible account list (useful as readiness check)."""
        return self._request("GET", "/iserver/accounts")

    def get_event_category_tree(self) -> dict[str, Any]:
        """
        Fetch ForecastEx category tree with all market topics.

        Some local Client Portal Gateway builds do not expose this endpoint.
        We try a few known variants and report a clean error if unavailable.
        """
        candidate_endpoints = [
            "/trsrv/event/category-tree",
            "/trsrv/event/categorytree",
            "/trsrv/events/category-tree",
        ]

        for endpoint in candidate_endpoints:
            try:
                response = self._raw_request("GET", endpoint)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                if not response.text.strip():
                    continue
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
            except ValueError:
                # Non-JSON payload; try next endpoint variant.
                continue
            except requests.exceptions.RequestException as exc:
                raise IBKRClientError(f"IBKR HTTP error: {exc}") from exc

        raise IBKRClientError(
            "Event category tree endpoint is not available on this IBKR gateway build."
        )

    def get_contracts_for_month(
        self, conid: str, sectype: str, month: str, exchange: str
    ) -> list[dict[str, Any]]:
        """Fetch all contracts for a month (without strike filter)."""
        params = {
            "conid": conid,
            "sectype": sectype,
            "month": month,
            "exchange": exchange,
        }
        data = self._request("GET", "/iserver/secdef/info", params=params)
        return data if isinstance(data, list) else []
