"""Order placement service for YES/NO contracts."""

from __future__ import annotations

from typing import Any

from services.ibkr_client import IBKRClient


class OrderService:
    """Wraps buy flows so frontend uses simple YES/NO actions."""

    def __init__(self, client: IBKRClient) -> None:
        self.client = client

    def place_yes_order(
        self,
        account_id: str,
        conid: int,
        quantity: int,
        order_type: str = "MKT",
        price: float | None = None,
        tif: str = "DAY",
        *,
        auto_confirm: bool = True,
        sec_type_suffix: str = "OPT",
    ) -> dict[str, Any]:
        """Place BUY order for YES (Call) contract."""
        broker_response = self.client.place_order(
            account_id=account_id,
            conid=conid,
            side="BUY",
            quantity=quantity,
            order_type=order_type,
            price=price,
            tif=tif,
            auto_confirm=auto_confirm,
            sec_type_suffix=sec_type_suffix,
        )
        return {"status": "success", "side": "YES", "broker_response": broker_response}

    def place_no_order(
        self,
        account_id: str,
        conid: int,
        quantity: int,
        order_type: str = "MKT",
        price: float | None = None,
        tif: str = "DAY",
        *,
        auto_confirm: bool = True,
        sec_type_suffix: str = "OPT",
    ) -> dict[str, Any]:
        """
        Place BUY order for NO (Put) contract.

        For ForecastEx-like behavior, we do not SELL YES here;
        we BUY the NO contract directly.
        """
        broker_response = self.client.place_order(
            account_id=account_id,
            conid=conid,
            side="BUY",
            quantity=quantity,
            order_type=order_type,
            price=price,
            tif=tif,
            auto_confirm=auto_confirm,
            sec_type_suffix=sec_type_suffix,
        )
        return {"status": "success", "side": "NO", "broker_response": broker_response}

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
    ) -> dict[str, Any]:
        """Place BUY or SELL on the given contract."""
        broker_response = self.client.place_order(
            account_id=account_id,
            conid=conid,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            tif=tif,
            auto_confirm=auto_confirm,
            sec_type_suffix=sec_type_suffix,
        )
        return {"status": "success", "broker_response": broker_response}

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
    ) -> dict[str, Any]:
        """Preview order cost / margin without submitting."""
        broker_response = self.client.whatif_order(
            account_id=account_id,
            conid=conid,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            tif=tif,
            sec_type_suffix=sec_type_suffix,
        )
        return {"status": "success", "broker_response": broker_response}

    def cancel_order(self, account_id: str, order_id: str) -> dict[str, Any]:
        broker_response = self.client.cancel_order(
            account_id=account_id, order_id=order_id
        )
        return {
            "status": "success",
            "account_id": account_id,
            "order_id": order_id,
            "broker_response": broker_response,
        }
