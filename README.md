# ATLAS MARKETS

**Version 1.0.0 — Simulation Release**

ATLAS MARKETS is a multi-market, multi-provider automated trading platform for stocks, ETFs, FX, metals, commodities and crypto.

ATLAS MARKETS is a separate project from ATLAS TRADER. ATLAS TRADER was used only as an architectural/UX reference.

## Release status

The core project is **complete for Paper / Demo / Testnet automated trading**.

Live Money remains intentionally gated and is not part of the v1.0 simulation completion boundary.

## Stack

- Python 3.12
- FastAPI + Uvicorn
- PostgreSQL 17 + SQLAlchemy + Alembic
- Redis
- Docker / Docker Compose
- responsive browser frontend
- local broker bridges for IBKR Paper and Fusion MT5 Demo

## Providers

| Provider | Purpose | Environment | Status |
| --- | --- | --- | --- |
| Fusion Markets MT5 | FX, metals, commodities execution | Demo | Connected and execution certified |
| Interactive Brokers | Stocks and ETFs execution | Paper | Connected and execution certified; max 1 share/order |
| Bybit | Crypto account/testnet integration | Testnet | Connected; execution blocked by provider error 10024 |
| Twelve Data | Market/historical data | Data only | Connected; never used for execution |

ATLAS does not bypass provider restrictions. Bybit automatic execution remains disabled while error `10024` is in force.

## Implemented

- ADMIN / USER authentication and revocable sessions
- per-user external provider profiles
- encrypted provider credentials
- provider connection testing and account synchronization
- multi-market instrument universe
- technical and multi-timeframe analysis
- historical intelligence loop
- financial/news intelligence
- strategy modes: WATCH / SIGNALS / AUTO_TRADE
- BUY / SELL / HOLD decision flow
- portfolio/account risk controls
- duplicate position/order prevention
- kill switch
- scheduled automatic simulation scans
- certified-route-only automatic execution
- MT5 Demo automatic execution
- IBKR Paper automatic execution with broker fill verification
- persistent automation action ledger
- broker-native positions, orders and execution history
- unified trade history and realized P&L
- strategy performance and diagnostics
- conservative broker-verified strategy attribution
- Dashboard and Automation Operations Center
- provider/integration frontend
- mobile-responsive frontend
- release readiness endpoint

## Automatic execution policy

The automatic lifecycle is:

```text
market + historical + news data
→ analysis
→ strategy decision
→ risk/readiness
→ certified provider route
→ broker submission
→ fill verification
→ action audit
→ P&L/performance
→ repeat
```

Certified automatic routes in v1.0:

- **Fusion MT5 Demo**
- **IBKR Paper**, maximum 1 share per automatic order

Blocked/non-execution routes:

- **Bybit Testnet** — provider error `10024`
- **Twelve Data** — data only
- **Live Money** — separately gated

## Local runtime

```powershell
cd "C:\Users\USER\Downloads\altas-markets"

git pull origin main

docker compose stop app
docker compose rm -f app
docker compose build --no-cache app
docker compose up -d app

docker compose exec app python -m pytest -q
docker compose ps
```

Frontend:

```text
http://localhost:8000
```

After frontend changes use `Ctrl+F5`.

## Important APIs

- `GET /health`
- `GET /api/system`
- `GET /release/readiness`
- `GET /accounts`
- `GET /portfolio`
- `GET /strategies/symbols`
- `GET /automation/state`
- `GET /automation/scans`
- `GET /automation/actions`
- `POST /automation/kill`
- `POST /automation/restart`
- `GET /performance/unified?days=30`
- `GET /strategies/performance?days=30`
- `GET /strategies/performance/diagnostics?days=30`
- `GET /strategies/performance/verified?days=30`

## Safety position

A Paper/Demo certification does not automatically certify Live Money. Broker account state is authoritative for actual positions/fills. Historical broker trades are only attributed to an ATLAS strategy when persisted broker-confirmed evidence exists; unverifiable history is intentionally left unverified.

## Documentation

Start with:

- `docs/FINAL_HANDOVER.md` — final release handover and operations runbook
- `docs/CURRENT_STATUS.md` — current operational state
- `docs/PROVIDERS.md` — provider architecture
- `docs/TESTING_AND_CERTIFICATION.md` — testing/certification
- `docs/ARCHITECTURE.md` — architecture
- `docs/ERD.md` — database design
- `docs/AUTHORIZATION.md` — roles and authorization
- `docs/ROADMAP.md` — post-v1 enhancements and Live Money readiness program

## Engineering rule

`DESIGN → BUILD → TEST → COMMIT → DEPLOY → BROKER/APP SMOKE TEST → DOCUMENT`

For a new broker, account environment, or Live Money route, controlled certification must be performed again from scratch.
