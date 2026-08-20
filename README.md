# Atlas Markets

24/7 FX + Crypto Algorithmic Trading Platform.

## Status
Phase 3 — Authentication + RBAC implemented on `feature/phase3-auth-rbac` and awaiting runtime verification.

Atlas Markets is a completely separate project from Atlas Trader. Atlas Trader is used only as an architectural and UX reference.

## Initial stack
- Python 3.12
- FastAPI + Uvicorn
- PostgreSQL 17 + SQLAlchemy + Alembic
- Redis
- Docker / Docker Compose
- Caddy planned for production edge
- TradingView Lightweight Charts planned for charting
- Bybit Demo/Testnet first for crypto
- Provider abstraction for FX (OANDA or IBKR after validation)

## Implemented foundation
- FastAPI application shell
- `/` bootstrap endpoint
- dependency-aware `/health` endpoint
- environment-based settings
- provider-independent `BrokerAdapter`
- PostgreSQL + Redis Docker infrastructure
- SQLAlchemy + Alembic
- ADMIN / USER authentication and RBAC
- server-side revocable sessions
- authentication audit log
- tests for core infrastructure and authentication

## Local development

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
python -m pytest
uvicorn app.main:app --reload
```

## Docker verification

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
docker compose exec app alembic current
docker compose exec app python -m pytest
```

## Phase 3 authentication

After migrations are current, create the first administrator:

```powershell
docker compose exec app python -m app.scripts.create_admin --username admin
```

Then use:

- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`
- `GET /admin/users` — ADMIN only
- `POST /admin/users` — ADMIN only
- `GET /admin/ping` — ADMIN only

See `docs/AUTHORIZATION.md` for the security model.

## Engineering workflow
DESIGN → BUILD → TEST → COMMIT → DEPLOY → LIVE SMOKE TEST → DOCUMENT → RELEASE

See `docs/ARCHITECTURE.md`, `docs/ERD.md`, and `docs/AUTHORIZATION.md`.
