# Atlas Markets

24/7 FX + Crypto Algorithmic Trading Platform.

## Status
Phase 0 — Architecture + ERD.

Atlas Markets is a completely separate project from Atlas Trader. Atlas Trader is used only as an architectural and UX reference.

## Initial stack
- Python 3.12
- FastAPI + Uvicorn
- PostgreSQL 17 + SQLAlchemy + Alembic
- Redis
- Docker / Docker Compose
- Caddy
- TradingView Lightweight Charts
- Bybit Demo/Testnet first for crypto
- Provider abstraction for FX (OANDA or IBKR after validation)

## Engineering workflow
DESIGN → BUILD → TEST → COMMIT → DEPLOY → LIVE SMOKE TEST → DOCUMENT → RELEASE

See `docs/ARCHITECTURE.md` and `docs/ERD.md`.
