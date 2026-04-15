"""
README (quick start)
====================

This backend uses IBKR Client Portal Web API.
Gateway must already be running and logged in at https://localhost:5000.
This is session-based and mainly suitable for local testing / prototyping.

1) Install dependencies
   pip install -r requirements.txt

2) Run FastAPI server
   uvicorn main:app --reload

3) Example endpoints
   - GET  /                       -> health/root message
   - GET  /auth/status            -> check IBKR session
   - GET  /events/search          -> search underlyings/topics
   - GET  /events/chain           -> get normalized YES/NO chain
   - POST /orders/yes             -> place BUY YES order
   - POST /orders/no              -> place BUY NO order
   - POST /orders                 -> place BUY or SELL by conid
   - POST /orders/whatif          -> preview order (no submit)
   - POST /orders/reply           -> answer IBKR prompt if auto_confirm=false
   - DELETE /orders/{order_id}    -> cancel one order (account_id query param)
   - GET  /orders/live            -> list live orders

   Small UI (after uvicorn is up): http://127.0.0.1:8000/static/index.html

Example curl usage:
  # auth status
  curl -k http://127.0.0.1:8000/auth/status

  # list valid account ids (use one of accounts_response.accounts)
  curl -k http://127.0.0.1:8000/auth/ready

  # event chain search
  curl -k "http://127.0.0.1:8000/events/chain?symbol=NQ&sec_type=IND&month=202605&exchange=CME&sectype=OPT"

  # place YES order (PowerShell-safe: use curl.exe and single-quoted JSON)
  curl.exe -s -X POST "http://127.0.0.1:8000/orders/yes" -H "Content-Type: application/json" -d '{"account_id":"REAL_ACCOUNT_ID","conid":123456,"quantity":1,"order_type":"MKT","price":null,"tif":"DAY","auto_confirm":true}'

  # place NO order
  curl.exe -s -X POST "http://127.0.0.1:8000/orders/no" -H "Content-Type: application/json" -d '{"account_id":"REAL_ACCOUNT_ID","conid":654321,"quantity":1,"order_type":"MKT","price":null,"tif":"DAY","auto_confirm":true}'

  # generic BUY/SELL
  curl.exe -s -X POST "http://127.0.0.1:8000/orders" -H "Content-Type: application/json" -d '{"account_id":"REAL_ACCOUNT_ID","conid":123456,"side":"SELL","quantity":1,"order_type":"MKT","price":null,"tif":"DAY"}'

  # what-if preview
  curl.exe -s -X POST "http://127.0.0.1:8000/orders/whatif" -H "Content-Type: application/json" -d '{"account_id":"REAL_ACCOUNT_ID","conid":123456,"side":"BUY","quantity":1,"order_type":"LMT","price":0.45,"tif":"DAY"}'

  # cancel order
  curl -k -X DELETE "http://127.0.0.1:8000/orders/12345?account_id=REAL_ACCOUNT_ID"
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.logger import setup_logging
from routes.auth import router as auth_router
from routes.events import router as events_router
from routes.orders import router as orders_router

setup_logging()

app = FastAPI(
    title="Prediction Market Backend (IBKR Client Portal)",
    description="Small modular FastAPI backend for YES/NO style contract workflows.",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(orders_router)

_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", tags=["root"])
def root() -> dict[str, str | bool | None]:
    """Simple root endpoint for quick service checks."""
    return {
        "message": "Prediction Market backend is running.",
        "ibkr_base_url": settings.base_url,
        "ssl_verify": settings.verify_ssl,
        "default_account_id": settings.default_account_id,
        "console_ui": "/static/index.html",
    }
