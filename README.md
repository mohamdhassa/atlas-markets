# Atlas Markets

24/7 FX + Crypto Algorithmic Trading Platform.

## Status
Phase 6 — responsive frontend, broker-profile management, and technical-analysis engine implemented on `feature/phase6-analysis-accounts-responsive` and awaiting local runtime verification.

Atlas Markets is a separate project from Atlas Trader. Atlas Trader is used only as an architectural and UX reference.

## Stack
- Python 3.12
- FastAPI + Uvicorn
- PostgreSQL 17 + SQLAlchemy + Alembic
- Redis
- Docker / Docker Compose
- Bybit V5 public market data
- provider-independent broker abstraction

## Implemented
- FastAPI application + dependency-aware health checks
- PostgreSQL + Redis Docker infrastructure
- SQLAlchemy + Alembic migrations
- ADMIN / USER authentication and revocable sessions
- authentication audit log
- responsive browser frontend for desktop, tablet and phone
- role-specific ADMIN and USER dashboards/navigation
- ADMIN Create User workflow
- broker-profile create/list/enable-disable workflow with per-user ownership
- live Bybit Markets page and candle Charts page
- deterministic technical analysis: SMA, EMA, RSI, MACD, ATR, Bollinger Bands
- market-structure and support/resistance calculations
- trend/volatility regime labels and normalized signal score/bias
- multi-timeframe 4H/1H/15M/5M alignment API
- unit/integration coverage for infrastructure, auth, market data, analysis and broker profiles

## Role model
- **ADMIN**: system-wide control, user creation, all broker profiles, strategy/risk/integration administration.
- **USER**: personal workspace; only their own broker profiles and account-scoped trading records.

Public self-registration is intentionally disabled. Administrators create application users from the **Users** page.

## Local Docker verification

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
docker compose exec app alembic current
docker compose exec app python -m pytest
```

Create the first administrator when needed:

```powershell
docker compose exec app python -m app.scripts.create_admin --username admin
```

## Key APIs
- `POST /auth/login`
- `GET /auth/me`
- `GET|POST /admin/users` — ADMIN only
- `GET|POST /accounts`
- `PATCH /accounts/{profile_id}/toggle`
- `GET /markets/tickers`
- `GET /markets/candles/{symbol}`
- `GET /analysis/{symbol}`
- `GET /analysis/{symbol}/multi`

## Engineering workflow
DESIGN → BUILD → TEST → COMMIT → DEPLOY → LIVE SMOKE TEST → DOCUMENT → RELEASE

See `docs/ARCHITECTURE.md`, `docs/ERD.md`, and `docs/AUTHORIZATION.md`.

---

# Current Development Update — 2026-08-25

The original project above remains the foundation. Development has since expanded ATLAS MARKETS into a **multi-market, multi-provider automated trading platform**. The newer work is additive and does not replace the original Phase 0–19 design/history.

## Expanded provider architecture

- **Interactive Brokers (IBKR)** — stocks and ETFs; current environment: Paper.
- **Fusion MT5** — FX, metals and commodities; current environment: Demo.
- **Bybit** — crypto; current environment: Testnet.
- **Twelve Data** — market/historical data only; not an execution broker.

The final system is intended to support many instruments per provider. Symbols used in certification are only controlled test instruments.

## Current verification baseline

- automated tests: **55 passed, 1 warning**
- Fusion MT5 connectivity: **CERTIFIED**
- Fusion MT5 Demo execution: **CERTIFIED**
- IBKR Paper connectivity: **CERTIFIED**
- IBKR Paper execution: **NEXT CERTIFICATION TASK**
- Bybit Testnet connectivity/private API: **CERTIFIED**
- Bybit Testnet execution: request path reached, but provider-blocked by Bybit error `10024`
- Twelve Data: **CONNECTED / market-data-only**

### Fusion MT5 certification evidence

A controlled `EURUSD` 0.01-lot Demo order was opened and closed successfully. MT5 returned success retcodes for both operations and the exact certification position was verified flat afterward. `/history/deals` may lag, so delayed history is treated as a warning when order/deal/position state already proves execution.

### Bybit current state

The connected Testnet AI subaccount is `107068845`. Wallet/private API access is working and funded. A valid BTCUSDT Testnet market-order request reached Bybit, which rejected execution with `10024` because the product/service is unavailable to the account due to regulatory restrictions. ATLAS must not bypass this provider restriction.

## Expanded product objective

The intended automatic lifecycle is:

```text
market + historical + financial/news data
→ analysis
→ BUY / SELL / HOLD decision
→ risk approval
→ provider routing
→ execution
→ position monitoring
→ exit management
→ P&L/performance recording
→ historical evaluation
→ repeat
```

Live Money remains explicitly gated and is not considered ready merely because Paper/Demo integrations work.

## Current next steps

1. Certify IBKR Paper execution end-to-end.
2. Validate multi-instrument universe and provider capabilities.
3. Validate automatic provider routing.
4. Expand/validate strategy and financial/news intelligence.
5. Harden the risk engine.
6. Certify the full automatic trading loop.
7. Expand performance analytics and historical evaluation.
8. Complete frontend/mobile UX and provider setup.
9. Run extended simulation before any Live Money decision.

## Current operational commands

```powershell
cd "C:\Users\USER\Downloads\altas-markets"
git pull origin main
docker compose up -d --build
docker compose exec app python -m pytest
docker compose exec app python -m app.scripts.verify_integrations
```

Certification utilities currently include:

```powershell
docker compose exec app python -m app.scripts.certify_mt5_execution
docker compose exec app python -m app.scripts.certify_bybit_execution
```

See also the additive current-state documents:

- `docs/CURRENT_STATUS.md`
- `docs/PROVIDERS.md`
- `docs/TESTING_AND_CERTIFICATION.md`
- `docs/ROADMAP.md`
