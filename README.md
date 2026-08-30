# ATLAS MARKETS

**v1.1 deployment candidate — multi-broker simulation + Oracle Cloud**

ATLAS MARKETS is a multi-market, multi-provider automated trading platform for stocks, ETFs, FX, metals, commodities and crypto.

The v1.0.0 Simulation Release remains the permanent tagged baseline. v1.1 expands the observation deployment: all eligible certified simulation symbols can be promoted to AUTO_TRADE, the core app/database moves to Oracle Cloud, and provider operations/documentation are consolidated.

Live Money remains intentionally gated.

## Provider status

| Provider | Purpose | Environment | Automatic execution |
|---|---|---|---|
| Fusion Markets MT5 | FX, metals, commodities | Demo | CERTIFIED |
| Interactive Brokers | Stocks, ETFs | Paper | CERTIFIED; max 1 share/order |
| Bybit | Crypto | Testnet | BLOCKED by provider error `10024` |
| Twelve Data | Market/historical data | Data only | NEVER execution |

## v1.1 AUTO_TRADE expansion

ADMIN may use:

```text
POST /strategies/symbols/auto-trade/eligible
```

This operation can seed/promote all starter-universe symbols assigned to **ready certified simulation routes**.

Current result by design:

- Fusion MT5 Demo FX/metals/commodities -> eligible for AUTO_TRADE.
- IBKR Paper stocks/ETFs -> eligible for AUTO_TRADE under the certified 1-share cap and broker/risk guards.
- Bybit crypto -> reported as blocked until Bybit resolves `10024` and ATLAS re-certifies execution.
- Live Money -> never bulk-promoted.

## Bybit `10024`

ATLAS private diagnostics and account permissions pass, and the order request reaches Bybit. Bybit returns a regulatory/product-availability restriction. This is provider-side, not an API-signing bug. The valid resolution path is a Bybit support/account-product review followed by controlled ATLAS re-certification. ATLAS will not bypass jurisdiction/KYC/compliance controls.

See `docs/PROVIDERS.md`.

## IBKR Paper

IBKR Paper automatic execution is certified and may be used during the multi-week simulation. Safeguards include:

- Paper bridge only;
- WhatIf preflight;
- maximum 1 share/order;
- position/open-order duplicate guards;
- broker status polling;
- cancelled orders never counted as executed.

For broad unattended U.S. stock/ETF testing, appropriate **real-time IBKR API market-data subscriptions are strongly recommended**. Delayed quotes are not equivalent to real-time execution-quality pricing.

## Oracle Cloud target

Oracle hosts the always-on core:

- FastAPI/frontend;
- PostgreSQL 17;
- Redis 7;
- automation/history/reporting loops.

The Oracle production profile is:

```text
docker-compose.oracle.yml
.env.oracle.example
docs/ORACLE_DEPLOYMENT.md
```

The public server should expose only HTTPS. PostgreSQL, Redis, FastAPI's internal port and broker bridges stay private.

Fusion MT5 remains on a Windows execution node. IBKR TWS/IB Gateway also remains an execution-node dependency unless separately migrated. Oracle reaches broker bridges through a private VPN; do not publish ports 8765/8766 publicly.

## Core functionality

- ADMIN / USER authentication and revocable sessions
- encrypted provider credentials
- external broker account synchronization
- configurable multi-market symbol universe
- WATCH / SIGNALS / AUTO_TRADE modes
- technical, historical and news intelligence
- BUY / SELL / HOLD decision pipeline
- risk/preflight controls and kill switch
- scheduled certified-route-only automation
- persistent scan/action audit ledger
- MT5 Demo execution
- IBKR Paper execution with broker fill verification
- broker-native portfolio/order/history views
- unified P&L and strategy diagnostics
- conservative verified attribution
- responsive Dashboard / Automation Operations Center
- release readiness and operational status

## Local development/runtime

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

Frontend: `http://localhost:8000`

## Oracle runtime

See `docs/ORACLE_DEPLOYMENT.md` before deployment.

```bash
cp .env.oracle.example .env.oracle
chmod 600 .env.oracle
docker compose --env-file .env.oracle -f docker-compose.oracle.yml up -d --build
docker compose --env-file .env.oracle -f docker-compose.oracle.yml ps
```

## Important APIs

- `GET /health`
- `GET /api/system`
- `GET /release/readiness`
- `GET /accounts`
- `GET /portfolio`
- `GET /strategies/symbols`
- `POST /strategies/symbols/auto-trade/eligible`
- `GET /automation/state`
- `GET /automation/scans`
- `GET /automation/actions`
- `POST /automation/kill`
- `POST /automation/restart`
- `GET /performance/unified?days=30`
- `GET /strategies/performance?days=30`
- `GET /strategies/performance/diagnostics?days=30`
- `GET /strategies/performance/verified?days=30`

## Documentation

- `docs/FINAL_HANDOVER.md`
- `docs/CURRENT_STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/ERD.md`
- `docs/AUTHORIZATION.md`
- `docs/PROVIDERS.md`
- `docs/TESTING_AND_CERTIFICATION.md`
- `docs/ORACLE_DEPLOYMENT.md`
- `docs/ROADMAP.md`

## Engineering rule

`DESIGN → BUILD → TEST → COMMIT → DEPLOY → BROKER/APP SMOKE TEST → DOCUMENT`

A new provider environment or Live Money route must be certified independently. The v1.0.0 Git tag remains the rollback/reference checkpoint for the completed simulation foundation.
