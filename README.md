# PredictionMarket Backend

FastAPI backend for IBKR ForecastTrader / Event Contracts workflows:
- discover topics and YES/NO contract pairs
- place YES/NO (or generic BUY/SELL) orders
- preview orders and manage live orders

This project talks to the local IBKR Client Portal Gateway API (`https://localhost:5000/v1/api` by default).

## Prerequisites

- Python 3.10+
- IBKR Client Portal Gateway running locally
- Active IBKR login session in the gateway

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload
```

Server base URL:
- `http://127.0.0.1:8000`

Useful pages:
- Swagger docs: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Simple UI: `http://127.0.0.1:8000/static/index.html`

## Environment Variables

- `IBKR_BASE_URL` (default: `https://localhost:5000/v1/api`)
- `IBKR_VERIFY_SSL` (default: `false`)
- `IBKR_ACCOUNT_ID` (optional default account id)
- `IBKR_TIMEOUT` (default: `8`)

## Core API Flow (ForecastTrader)

1. Get session/account readiness  
   `GET /auth/ready`
2. Find topic by symbol  
   `GET /events/topics/console?symbols=UHSFO&exchange=FORECASTX`
3. Get YES/NO contract conids  
   `GET /events/chain?...`
4. Place order  
   `POST /orders/yes` or `POST /orders/no`
5. Track orders  
   `GET /orders/live`

## Endpoint Overview

### Auth
- `GET /auth/status`
- `GET /auth/ready`

### Events / Discovery
- `GET /events/search`
- `GET /events/topics/all`
- `GET /events/topics/console`
- `GET /events/discover`
- `GET /events/strikes`
- `GET /events/contracts`
- `GET /events/chain`

### Orders
- `POST /orders/yes`
- `POST /orders/no`
- `POST /orders` (generic BUY/SELL)
- `POST /orders/whatif`
- `POST /orders/reply`
- `DELETE /orders/{order_id}`
- `GET /orders/live`

## Windows PowerShell Examples

Use `curl.exe` (not `curl` alias) and single-quoted JSON bodies.

### 1) Check ready + account id

```powershell
curl.exe -s "http://127.0.0.1:8000/auth/ready"
```

Use one value from `accounts_response.accounts` as `REAL_ACCOUNT_ID`.

### 2) Fetch topic + chain

```powershell
curl.exe -s "http://127.0.0.1:8000/events/topics/console?symbols=UHSFO&exchange=FORECASTX"
curl.exe -s "http://127.0.0.1:8000/events/chain?symbol=UHSFO&sec_type=IND&month=202604&exchange=FORECASTX&sectype=OPT&conid=853400816"
```

### 3) Place YES / NO

```powershell
curl.exe -s -X POST "http://127.0.0.1:8000/orders/yes" -H "Content-Type: application/json" -d '{"account_id":"REAL_ACCOUNT_ID","conid":873489344,"quantity":1,"order_type":"MKT","price":null,"tif":"DAY","auto_confirm":true}'
curl.exe -s -X POST "http://127.0.0.1:8000/orders/no"  -H "Content-Type: application/json" -d '{"account_id":"REAL_ACCOUNT_ID","conid":873489349,"quantity":1,"order_type":"MKT","price":null,"tif":"DAY","auto_confirm":true}'
```

### 4) Check live orders

```powershell
curl.exe -s "http://127.0.0.1:8000/orders/live?account_id=REAL_ACCOUNT_ID"
```

## Utility Scripts

- `discover_prediction_markets.py`  
  Broad discovery/permutation scan and JSON/Excel report output.
- `ibkrsearch.py`  
  Reads `pairs_20260414.csv`, extracts symbols from `event_contract`, calls `/events/topics/console` for each row, exports Excel output.

---

For a larger curl collection, see `command.txt`.
