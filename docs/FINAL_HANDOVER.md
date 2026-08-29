# ATLAS MARKETS — Final Handover

Release: **1.0.0 Simulation Release**  
Finalization date: **2026-08-29**

## 1. Release scope

ATLAS MARKETS v1.0 is complete for **Paper / Demo / Testnet automated trading and operational monitoring**.

The release includes:

- FastAPI backend, PostgreSQL, Redis and Docker Compose runtime;
- ADMIN / USER authentication and account isolation;
- external broker/provider profiles and encrypted credentials;
- Twelve Data market/historical data integration;
- Fusion Markets MT5 Demo integration and certified automatic execution;
- Interactive Brokers Paper integration and certified automatic execution with a hard maximum of 1 share per order;
- Bybit Testnet private API/account integration with execution correctly blocked while provider error `10024` remains in force;
- multi-market universe across stocks, ETFs, FX, metals, commodities and crypto;
- technical, historical and news intelligence pipelines;
- BUY / SELL / HOLD decision and readiness workflow;
- account/portfolio risk controls, duplicate-position/order guards and kill switch;
- scheduled automatic simulation scanning and execution on certified routes only;
- persistent automation action history;
- broker-native positions, orders and execution history;
- unified trade history and realized P&L;
- strategy performance diagnostics;
- conservative broker-verified strategy attribution;
- responsive frontend including Dashboard, Integrations, Strategies and Automation Operations Center;
- release-readiness API at `GET /release/readiness`.

## 2. Explicitly outside the v1.0 completion boundary

These are not defects in the completed simulation release:

1. **Live Money automatic execution remains gated.** A successful Paper/Demo system is not sufficient evidence for unrestricted live-money operation.
2. **Bybit automatic execution remains disabled** because Bybit returns regulatory/compliance error `10024`. ATLAS must not bypass provider restrictions.
3. **IBKR Paper automatic execution remains capped at one share per order** under the certified route.
4. Historical broker trades that cannot be tied to a persisted broker-confirmed ATLAS action are intentionally excluded from verified strategy attribution. Historical results are never fabricated or guessed.

## 3. Provider status

| Provider | Environment | Connection | Automatic execution |
| --- | --- | --- | --- |
| Fusion Markets MT5 | Demo | Certified | Certified |
| Interactive Brokers | Paper | Certified | Certified, max 1 share/order |
| Bybit | Testnet | Certified | Blocked by provider error 10024 |
| Twelve Data | Data provider | Certified | Not applicable; data only |

## 4. Normal operating model

The normal automatic lifecycle is:

`market / historical / news data → analysis → strategy mode → signal → risk/readiness → certified provider route → broker submission → broker fill verification → action ledger → broker history / P&L → strategy diagnostics → repeat`

No normal automatic operation should require manual Buy/Sell buttons.

## 5. Windows local runtime

Project directory:

```powershell
cd "C:\Users\USER\Downloads\altas-markets"
```

Start/update the core application:

```powershell
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

Use `Ctrl+F5` after frontend updates.

## 6. Local execution bridges

### IBKR Paper bridge

The IBKR desktop/API session and local bridge must remain available for IBKR operations.

```powershell
cd "C:\Users\USER\Downloads\altas-markets"
.\.venv-ibkr\Scripts\python.exe tools/ibkr_bridge.py `
  --port 7497 `
  --account-id DUR980544 `
  --bridge-port 8766
```

Expected bridge endpoint:

```text
http://127.0.0.1:8766
```

### Fusion MT5 Demo bridge

The Fusion Markets MT5 terminal must be logged into the Demo account with Algo Trading enabled, and the configured local MT5 bridge must remain running for MT5 execution.

## 7. Core operational APIs

- `GET /health`
- `GET /api/system`
- `GET /release/readiness`
- `GET /automation/state`
- `GET /automation/scans`
- `GET /automation/actions`
- `POST /automation/scan-now` — ADMIN diagnostic/manual cycle
- `POST /automation/kill` — ADMIN kill switch
- `POST /automation/restart` — ADMIN restart
- `GET /performance/unified?days=30`
- `GET /strategies/performance?days=30`
- `GET /strategies/performance/diagnostics?days=30`
- `GET /strategies/performance/verified?days=30`
- `GET /portfolio`
- `GET /accounts`
- `GET /strategies/symbols`

## 8. Release verification

A release is acceptable when all of the following are true:

- Docker app, PostgreSQL and Redis services are healthy;
- Alembic is at head;
- full pytest suite passes;
- `/health` is OK;
- `/api/system` reports version `1.0.0`, phase `40`, release `SIMULATION_RELEASE`;
- `/release/readiness` reports the correct provider gates;
- Automation Operations Center loads directly;
- simulation automation is enabled and not killed when automatic simulation is desired;
- MT5 Demo and IBKR Paper are connected before their routes are used;
- Bybit remains blocked until the provider restriction is legitimately resolved;
- Live Money remains gated.

## 9. Safety and recovery

If behavior is unexpected:

1. use the Automation kill switch;
2. verify open positions/orders directly at the broker;
3. inspect `/automation/actions` and the latest `/automation/scans`;
4. verify IBKR/MT5 bridge health;
5. do not infer broker state only from an old ATLAS ledger row;
6. rebuild only after source/runtime mismatch is ruled out;
7. never use destructive Git cleanup on the development workstation where bridge environments/backups exist.

A broker is authoritative for actual positions, fills and account balances. ATLAS is authoritative for its persisted decisions, controls and attribution only when those records have broker confirmation.

## 10. Future change process

Use:

`DESIGN → BUILD → TEST → COMMIT → DEPLOY → BROKER/APP SMOKE TEST → DOCUMENT`

For any new provider or Live Money route, repeat controlled certification from scratch. Do not inherit certification from another environment or account.

## 11. Definition of complete

ATLAS MARKETS v1.0 is **complete as a multi-market automated simulation platform**.

Any future work is an enhancement, operational validation period, new provider integration, strategy improvement, or a separately controlled Live Money readiness program—not unfinished core v1.0 development.
