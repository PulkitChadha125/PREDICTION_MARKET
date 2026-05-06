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
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Server base URL:
- `http://127.0.0.1:8000`
- `http://<SERVER_IP>:8000` (if firewall/security group allow TCP 8000)

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
4. Get live quote snapshot (LTP/BID/ASK) for one or many conids  
   `GET /events/quotes?conids=...`
5. Get market depth snapshot (bid/ask + open qty at top of book)  
   `GET /events/market-depth?conids=...`
6. Place order  
   `POST /orders/yes` or `POST /orders/no`
7. Track open/live orders  
   `GET /orders/live`
8. Fetch historical bars (optional)  
   `GET /orders/historical?conid=...`
9. Fetch status-wise orderbook (optional)  
   `GET /orders/book?account_id=...&statuses=open,completed,rejected,canceled`
10. Fetch net positions (optional)  
   `GET /orders/netpositions?account_id=...`

## Endpoint Overview

### Auth
- `GET /auth/status`
- `GET /auth/ready`

### Events / Discovery
- `GET /events/search`
- `GET /events/topics/all`
- `GET /events/topics/console`
- `GET /events/discover`
- `GET /events/pairs/symbols` (returns `prediction_market_symbols_from_pairs.xlsx` as JSON)
- `GET /events/strikes`
- `GET /events/contracts`
- `GET /events/chain`
- `GET /events/quotes`
- `GET /events/market-depth`
- `POST /events/chain/check` (Swagger body input for your own values)

### Orders
- `POST /orders/yes`
- `POST /orders/no`
- `POST /orders` (generic BUY/SELL)
- `POST /orders/whatif`
- `POST /orders/reply`
- `DELETE /orders/{order_id}`
- `GET /orders/live`
- `GET /orders/historical` (historical bars by conid)
- `GET /orders/book` (orderbook by status: open/completed/rejected/canceled)
- `GET /orders/netpositions` (portfolio net positions)

## New APIs (Market Depth + Historical + Orderbook + Net Positions)

- `GET /events/market-depth`  
  Fetch top-of-book depth per conid with `bid.price`, `bid.open_qty`, `ask.price`, and `ask.open_qty`.

- `GET /orders/historical`  
  Fetch historical candles from IBKR for a contract (`conid`, `period`, `bar`, etc.).
- `GET /orders/book`  
  Fetch orderbook and filter by status buckets (`open`, `completed`, `rejected`, `canceled`).
- `GET /orders/netpositions`  
  Fetch net positions for an account from IBKR portfolio.

## Windows PowerShell Examples

Use `curl.exe` (not `curl` alias) and single-quoted JSON bodies.

### 1) Check ready + account id

```powershell
curl.exe -s "http://127.0.0.1:8000/auth/ready"
curl.exe -s "http://32.193.90.145:8000/auth/ready"

```

Use one value from `accounts_response.accounts` as `REAL_ACCOUNT_ID`.

### 2) Fetch topic + chain

```powershell
curl.exe -s "http://127.0.0.1:8000/events/topics/console?symbols=FF&exchange=CME"
curl.exe -s "http://32.193.90.145:8000/events/topics/console?symbols=UHLGA&exchange=FORECASTX"

curl.exe -s "http://32.193.90.145:8000/events/chain?symbol=UHLGA&sec_type=IND&month=202605&exchange=FORECASTX&sectype=OPT&conid=853400786"
```
For CME-style event options, pass `sec_type=FOP` (or `FUT`) and exchange `CME`/`CBT`:
```powershell
curl.exe -s "http://127.0.0.1:8000/events/topics/console?symbols=UHSFO&sec_type=FOP&exchange=FORECASTX"

curl.exe -s "http://32.193.90.145:8000/events/topics/console?symbols=UHSFO&sec_type=FOP&exchange=FORECASTX"


```
You can call `/events/chain` in two ways:
- By `symbol` (discovery flow): provide `symbol`, `month`, `exchange`
- By `conid` (direct fast flow): provide `conid`, `month`, `exchange` (symbol optional label)
- Or use Swagger-friendly body endpoint `POST /events/chain/check`

### 2b) Get pairs Excel data as JSON

```powershell
curl.exe -s "http://127.0.0.1:8000/events/pairs/symbols"
curl.exe -s "http://127.0.0.1:8000/events/pairs/symbols?sheet_name=Sheet1"
```
### 2c) Get quote snapshot (LTP/BID/ASK/VOLUME)

Use one or multiple conids.  
Field mapping from IBKR snapshot:
- `31` => LTP (last traded price)
- `84` => Bid
- `86` => Ask
- `87` => Volume

```powershell
# single conid
curl.exe -s "http://32.193.90.145:8000/events/quotes?conids=878744229"

# multiple conids
curl.exe -s "http://127.0.0.1:8000/events/quotes?conids=877309547,877309550,875861841,875861844"

# optional custom IBKR fields (default already includes 31,84,86,87)
curl.exe -s "http://127.0.0.1:8000/events/quotes?conids=877309547,877309550&fields=31,84,86,87,88"
```

### 2d) Get market depth (BID/ASK + OPEN QTY)

For top-of-book depth, this API returns:
- `bid.price`, `bid.open_qty`
- `ask.price`, `ask.open_qty`

```powershell
# single conid
curl.exe -s "http://127.0.0.1:8000/events/market-depth?conids=853400786"

# multiple conids
curl.exe -s "http://127.0.0.1:8000/events/market-depth?conids=877309547,877309550"

# optional custom fields (default uses 84,85,86,88)
curl.exe -s "http://127.0.0.1:8000/events/market-depth?conids=877309547&fields=84,85,86,88"
```

Quote API example response:

```json
{
  "status": "success",
  "total": 2,
  "quotes": [
    {
      "conid": 877309547,
      "ltp": null,
      "bid": null,
      "ask": 0.03,
      "raw": {
        "conid": 877309547,
        "86": "0.03"
      }
    },
    {
      "conid": 877309550,
      "ltp": null,
      "bid": 0.98,
      "ask": null,
      "raw": {
        "conid": 877309550,
        "84": "0.98"
      }
    }
  ]
}
```

Market depth API example response:

```json
{
  "status": "success",
  "total": 2,
  "depths": [
    {
      "conid": 877309547,
      "bid": { "price": 0.98, "open_qty": 12.0 },
      "ask": { "price": 0.99, "open_qty": 7.0 },
      "raw": {
        "conid": 877309547,
        "84": "0.98",
        "88": "12",
        "86": "0.99",
        "85": "7"
      }
    },
    {
      "conid": 877309550,
      "bid": { "price": null, "open_qty": null },
      "ask": { "price": 0.04, "open_qty": 5.0 },
      "raw": {
        "conid": 877309550,
        "86": "0.04",
        "85": "5"
      }
    }
  ]
}
```

### 3) Place YES / NO

```powershell
curl.exe -s -X POST "http://32.193.90.145:8000/orders/yes" -H "Content-Type: application/json" -d '{"account_id":"DUP766324","conid":"877789111","quantity":1,"order_type":"MKT","price":null,"tif":"DAY","auto_confirm":true}'
curl.exe -s -X POST "http://127.0.0.1:8000/orders/no"  -H "Content-Type: application/json" -d '{"account_id":"873489349","conid":873489349,"quantity":1,"order_type":"MKT","price":null,"tif":"DAY","auto_confirm":true}'
```

other ex: curl.exe -s -X POST "http://127.0.0.1:8000/orders/yes" -H "Content-Type: application/json" -d '{"account_id":"DUP766324","conid":873489344,"quantity":1,"order_type":"MKT","price":null,"tif":"DAY","auto_confirm":true}'

### 4) Check live orders

```powershell
curl.exe -s "http://127.0.0.1:8000/orders/live?account_id=REAL_ACCOUNT_ID"
```

### 5) Historical bars

```powershell
curl.exe -s "http://127.0.0.1:8000/orders/historical?conid=877789100&period=1d&bar=1min&outside_rth=true"
```

### 6) Orderbook by status

```powershell
curl.exe -s "http://127.0.0.1:8000/orders/book?account_id=REAL_ACCOUNT_ID&statuses=open,completed,rejected,canceled"
```

### 7) Net positions

```powershell
curl.exe -s "http://127.0.0.1:8000/orders/netpositions?account_id=REAL_ACCOUNT_ID&page=0"
```

## Swagger Docs Update

After restarting the FastAPI server, the latest endpoints are available in Swagger:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- `GET /events/quotes`
- `GET /events/market-depth`
- `GET /orders/historical`
- `GET /orders/book`
- `GET /orders/netpositions`

## Utility Scripts

- `discover_prediction_markets.py`  
  Broad discovery/permutation scan and JSON/Excel report output.
- `ibkrsearch.py`  
  Reads `pairs_20260414.csv`, extracts symbols from `event_contract`, calls `/events/topics/console` for each row, exports Excel output.
- `discover_cme_conids_from_csv.py`  
  Reads CME event contract CSV symbols and probes IBKR Client Portal directly (`https://localhost:5000/v1/api/iserver/secdef/search`) to produce symbol-to-conid discovery outputs (`.json` and `.csv`).

---

For a larger curl collection, see `command.txt`.
curl.exe -k "https://localhost:5000/v1/api/iserver/secdef/info?conid=42755852&sectype=FOP&month=202606&exchange=CME"
curl.exe -k "https://localhost:5000/v1/api/iserver/secdef/info?conid=42755852&sectype=FOP&month=202606&exchange=CBOT"
