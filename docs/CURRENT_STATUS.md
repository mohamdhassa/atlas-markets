# ATLAS MARKETS — Current Status

Last updated: **2026-08-29**  
Release: **1.0.0 Simulation Release**  
System phase: **40**

## Completion state

ATLAS MARKETS is complete for the v1.0 **Paper / Demo / Testnet automated trading** scope.

The product now includes the full core lifecycle:

`market + historical + news data → analysis → BUY/SELL/HOLD → strategy mode → risk/readiness → provider routing → automatic execution on certified routes → broker verification → action audit → P&L/performance → strategy diagnostics → repeat`

Live Money remains explicitly gated and is a separate readiness program, not unfinished v1.0 simulation work.

## Repository/runtime

- Repository: `mohamdhassa/atlas-markets`
- Branch: `main`
- Local Windows path: `C:\Users\USER\Downloads\altas-markets`
- Runtime: FastAPI + PostgreSQL + Redis + Docker Compose
- Frontend: `http://localhost:8000`

## Provider state

### Fusion Markets MT5 — Demo

- Connectivity: **CERTIFIED**
- Automatic execution: **CERTIFIED**
- Asset classes: FX, metals, commodities
- Existing-position and portfolio exposure guards are active.

### Interactive Brokers — Paper

- Account: `DUR980544`
- Connectivity: **CERTIFIED**
- Automatic execution: **CERTIFIED**
- Hard automatic maximum: **1 share per order**
- Broker order state/fill must be confirmed before ATLAS marks an order EXECUTED.
- Broker cancellations are persisted as CANCELLED rather than false executions.

### Bybit — Testnet

- Connectivity/private API/wallet: **CERTIFIED**
- Automatic execution: **BLOCKED BY PROVIDER**
- Provider error: `10024`
- ATLAS does not bypass regulatory/provider restrictions.

### Twelve Data

- Connectivity: **CERTIFIED**
- Purpose: market/historical data only
- Execution: never applicable

## Multi-market universe

The configured universe spans:

- stocks: AAPL, AMZN, META, MSFT, NVDA, TSLA
- ETFs: IWM, QQQ, SPY
- FX: AUDUSD, EURUSD, GBPUSD, USDCAD, USDCHF, USDJPY
- metals: XAGUSD, XAUUSD
- commodity: XTIUSD
- crypto: BTCUSDT, ETHUSDT, SOLUSDT

Strategy modes are per symbol:

- `WATCH`
- `SIGNALS`
- `AUTO_TRADE`

Not every symbol should be AUTO_TRADE. The mode is intentionally separate from provider certification and risk readiness.

## Automation

Automation policy: **CERTIFIED_ROUTES_ONLY**.

Certified automatic routes:

- MT5 / DEMO
- IBKR / PAPER, max 1 share/order

Blocked route:

- BYBIT / TESTNET — `PROVIDER_EXECUTION_NOT_CERTIFIED` / provider restriction `10024`

The scheduler supports:

- enabled/disabled state;
- kill switch;
- simulation auto-execution state;
- configurable scan interval;
- persistent scan history;
- persistent action history;
- broker fill/cancellation verification.

## Risk/safety controls

Implemented controls include:

- certified-route gate;
- simulation-environment gate;
- provider connection/readiness gate;
- duplicate position prevention;
- duplicate open-order prevention;
- account/portfolio position limits;
- per-symbol strategy mode;
- IBKR certified maximum sizing;
- invalid/sub-share IBKR sizing block;
- MT5 stop-loss/take-profit requirement;
- kill switch;
- explicit Live Money gate.

## Reporting and attribution

Implemented:

- broker-native positions/orders/executions;
- persistent automation action ledger;
- unified broker-derived 30-day P&L/history;
- daily performance;
- strategy-level raw symbol attribution;
- strategy diagnostics including win/loss and profit-factor style metrics;
- broker-verified ATLAS attribution.

Historical broker activity without persisted broker-confirmed ATLAS evidence remains **unverified**. It is not retroactively fabricated or guessed.

## Frontend

Current frontend includes:

- Dashboard
- Markets/Charts/Signals
- Positions/Orders/Performance
- Accounts
- Users
- Strategy
- Risk
- Integrations
- System
- Automation Operations Center

The Dashboard initial-render issue and Automation navigation/rendering issues were addressed in the final frontend hardening pass.

## Release-readiness API

`GET /release/readiness`

The endpoint reports:

- release/version;
- automation state;
- provider connection/certification state;
- strategy-mode counts;
- Live Money gate;
- Bybit provider block;
- completion status for backend/frontend/automation/reporting.

## Known limitations that are intentionally preserved

1. Live Money is not certified by the v1.0 simulation release.
2. Bybit execution is provider-blocked by `10024`.
3. IBKR automatic Paper execution remains capped at one share/order.
4. Old historical broker trades without confirmed ATLAS action evidence remain unverified.
5. Local IBKR/MT5 bridges must be running for their broker routes.

These are controlled release boundaries, not hidden failures.

## Final verification command

```powershell
cd "C:\Users\USER\Downloads\altas-markets"

git pull origin main

docker compose stop app
docker compose rm -f app
docker compose build --no-cache app
docker compose up -d app

docker compose exec app alembic current
docker compose exec app python -m pytest -q
docker compose ps
```

Then verify:

- `http://localhost:8000`
- `/health`
- `/api/system`
- `/release/readiness`
- Dashboard initial load
- Automation Operations Center

See `docs/FINAL_HANDOVER.md` for the final operations/handover document.
