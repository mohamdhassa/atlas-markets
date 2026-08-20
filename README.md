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
