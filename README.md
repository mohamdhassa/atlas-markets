# Atlas Markets

24/7 FX + Crypto Algorithmic Trading Platform.

## Status
Phase 1 — project scaffold implemented locally and ready for repository commit.

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

## Current Phase 1 contents
- FastAPI application shell
- `/` bootstrap endpoint
- `/health` health endpoint
- environment-based settings
- provider-independent `BrokerAdapter`
- PostgreSQL + Redis Docker foundation
- unit tests for health, settings, and broker contract
- project package structure for later engines

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

## Engineering workflow
DESIGN → BUILD → TEST → COMMIT → DEPLOY → LIVE SMOKE TEST → DOCUMENT → RELEASE

See `docs/ARCHITECTURE.md` and `docs/ERD.md`.
