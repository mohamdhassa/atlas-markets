# ATLAS MARKETS

**v1.0.0 canonical production baseline — multi-provider simulation on Oracle Cloud**

ATLAS MARKETS is a multi-market, multi-provider trading analysis, simulation and operations platform for stocks, ETFs, FX, metals, commodities and crypto.

The canonical application, database, frontend, Bybit Testnet integration, IBKR Paper
integration, portfolio/activity/P&L surfaces, shadow analytics, authentication and
administration are pinned by tag `v1.0.0` at commit
`5ef08db6426876be6019541c45c0b3b3851f85eb`. All changes build forward from this baseline.

Live Money remains intentionally gated.

## Provider status

| Provider | Purpose | Environment | Current route |
|---|---|---|---|
| Fusion Markets MT5 | FX, metals, commodities | Demo | Bridge/readiness supported; runtime terminal authorization must be healthy |
| Interactive Brokers | Stocks, ETFs | Paper | Certified simulation route; max 1 share/order |
| Bybit | Crypto Spot | Testnet / Demo | Managed Spot infrastructure with BUY/SELL certification and reconciliation gates |
| Twelve Data | Market/historical data | Data only | Data provider; never an execution route |

Provider status shown in the application must come from runtime account/readiness APIs. Documentation must not hard-code a temporary broker error as permanent platform state.

## Consolidated-core rebuild

The rebuild is removing the old chain of `phaseXX` frontend runtime patches from the application entrypoint. The canonical browser entrypoint loads `app.js` plus `atlas-core.js`; legacy phase files remain temporarily as rollback/reference material while pages are migrated.

Current rebuild goals:

- stable ADMIN / USER navigation and routing;
- responsive desktop/mobile layout;
- real provider/account state instead of phase placeholders;
- Operations control center for automation/readiness/certification visibility;
- unified accounts, positions, orders, performance and strategy views;
- truthful runtime system metadata;
- preserve broker safety gates, kill switch and audit history;
- remove stale `Phase 6`, `COMING NEXT` and obsolete provider-state copy;
- maintain Oracle deployment compatibility.

## Bybit Spot

Bybit TESTNET/DEMO support includes managed Spot inventory, provider fill verification, BUY/SELL certification state and reconciliation. Certification is restricted to simulation environments and ADMIN operations. ATLAS-managed inventory prevents the system from treating unrelated wallet holdings as its own position.

Real-money Bybit execution is not part of this rebuild and remains gated.

## IBKR Paper

IBKR Paper safeguards include:

- Paper bridge only;
- WhatIf preflight;
- maximum 1 share/order;
- position/open-order duplicate guards;
- broker status polling;
- cancelled orders never counted as executed.

Appropriate real-time IBKR API market-data subscriptions are strongly recommended for broad U.S. stock/ETF testing.

## Oracle Cloud target

Oracle hosts the always-on core:

- FastAPI/frontend;
- PostgreSQL 17;
- Redis 7;
- automation/history/reporting loops.

Production configuration lives in `docker-compose.oracle.yml`, `.env.oracle.example`, and `docs/ORACLE_DEPLOYMENT.md`.

The public server should expose only HTTPS. PostgreSQL, Redis, FastAPI's internal port and broker bridges stay private.

## Core functionality

- ADMIN / USER authentication and revocable sessions
- encrypted provider credentials
- external broker account synchronization
- configurable multi-market symbol universe
- WATCH / SIGNALS / AUTO_TRADE strategy modes
- technical, historical and news intelligence
- BUY / SELL / HOLD decision support
- risk/preflight controls and kill switch
- persistent scan/action audit ledger
- broker-native portfolio/order/history views
- unified P&L and strategy diagnostics
- conservative verified attribution
- responsive Dashboard / Operations workspace
- release readiness and operational status

## Local development/runtime

```powershell
cd "C:\Users\USER\Downloads\altas-markets"
git fetch origin
git switch main
git pull --ff-only origin main
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

Do not replace or restart the legacy ATLAS Trader containers while validating ATLAS MARKETS.

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

## Documentation

Start with `docs/DOCUMENTATION_INDEX.md`. It links the architecture, production ERD,
ERP-style operating model, API reference, user/admin guide, provider documentation,
operations, IBKR continuity, security, backup/recovery, testing, status and handover.

## Engineering rule

`DESIGN → BUILD → TEST → COMMIT → REVIEW → DEPLOY → BROKER/APP SMOKE TEST → DOCUMENT → RELEASE`

A provider environment must be validated independently. The `v1.0.0` tag is the canonical
production and rollback checkpoint. Live Money remains separately gated.
