# ATLAS MARKETS

Multi-market, multi-provider automated trading, analysis, risk and execution platform.

## Current status

ATLAS MARKETS has moved well beyond the original Phase 6 baseline. The active development branch is `feature/phase20-unified-provider-integration` and the current runtime identifies the project at the later unified-provider phase level.

Current verified automated-test baseline: **55 passed, 1 warning**.

ATLAS MARKETS is a separate project from ATLAS Trader. ATLAS Trader may be used as an architectural/UX reference only.

## Product objective

ATLAS MARKETS is not a single-symbol or single-broker bot. The target is a configurable multi-instrument trading platform with a central analysis/strategy engine, mandatory risk controls, provider routing, automatic execution, monitoring and performance analytics.

Execution/provider responsibilities:

- **Interactive Brokers (IBKR)** — stocks and ETFs; Paper first, Live Money gated.
- **Fusion MT5** — FX, metals and commodities; Demo first, Live Money gated.
- **Bybit** — crypto; Testnet first, Live Money gated.
- **Twelve Data** — market/historical data only; never an execution broker.

Certification instruments such as EURUSD or BTCUSDT are test instruments only. They do not define the final trading universe.

## Current provider certification

| Provider | Environment | Connectivity | Execution |
| --- | --- | --- | --- |
| Fusion MT5 | Demo | CERTIFIED | **CERTIFIED** |
| Interactive Brokers | Paper | CERTIFIED | Certification is the next immediate task |
| Bybit | Testnet | CERTIFIED | Provider-blocked by Bybit error `10024` |
| Twelve Data | Market data | CERTIFIED | N/A |

### Fusion MT5

Current verified Demo account: `448261` on `FusionMarkets-Demo`, Algo Trading enabled.

End-to-end execution certification succeeded using a controlled `EURUSD` 0.01-lot test:

- preflight `retcode=0`
- market BUY accepted with `retcode=10009`
- newly created position identified by ticket
- exact certification position closed with `retcode=10009`
- position verified flat
- open and close deal IDs returned

MT5 `/history/deals` can lag behind authoritative execution/position state; certification treats that lag as a warning rather than a false execution failure.

### Interactive Brokers

Current Paper account: `DUR980544`.

Verified connectivity has reported approximately:

- equity: `$1,000,000`
- cash: `$1,000,000`
- buying power: `$4,000,000`
- simulation: `True`

The Windows IBKR bridge exposes account, positions, orders, executions, quote/candle, order-check and Paper-order functionality. End-to-end Paper execution certification is the next development task.

### Bybit

Current connected Testnet AI subaccount: `107068845`.

Wallet/account/private API connectivity is certified and the account has been successfully funded with Testnet assets. The execution certification reached Bybit's signed `/v5/order/create` path, but Bybit rejected the BTCUSDT Testnet order with error `10024` (product/service unavailable due to regulatory restrictions).

This is recorded as a provider/account restriction. ATLAS must not attempt to bypass it.

## Core stack

- Python 3.12
- FastAPI + Uvicorn
- PostgreSQL 17 + SQLAlchemy + Alembic
- Redis
- Docker / Docker Compose
- Windows bridges for MT5 and IBKR where required
- Bybit V5 APIs
- Twelve Data
- provider-independent broker/account architecture

## Role model

Only two application roles are intended:

- **ADMIN / Owner** — system-wide control, user creation, providers/accounts, strategy, risk, integrations, kill/restart controls, system settings and overall results.
- **USER** — own permitted accounts, data and results.

Public self-registration is intentionally disabled unless a future requirement explicitly changes this decision.

## Safety model

Unrestricted Live Money automatic execution is intentionally **not ready**.

Development order is:

1. provider connectivity
2. Paper/Demo execution certification
3. multi-instrument validation
4. provider routing
5. analysis/strategy validation
6. risk-engine hardening
7. automatic trading end-to-end validation
8. extended simulation/performance review
9. explicit consideration of Live Money

Live Money must remain gated and strategy/AI decisions must never bypass risk controls.

## Immediate roadmap

1. Certify IBKR Paper execution end-to-end.
2. Return to the central ATLAS engine rather than continuing provider-by-provider setup.
3. Validate/configure multi-instrument universes and provider capability discovery.
4. Validate automatic provider routing (stocks/ETFs → IBKR; FX/metals/commodities → MT5; crypto → Bybit where execution is permitted).
5. Expand and validate analysis/strategy methodology.
6. Harden risk management and execution safety.
7. Certify the automatic scan → analyze → signal → risk → route → execute → monitor → exit → record loop.
8. Expand performance analytics and historical evaluation.
9. Complete frontend/mobile UX and simplify provider/account setup.
10. Complete deployment, operations and final documentation before release.

## Local Docker verification

```powershell
cd "C:\Users\USER\Downloads\altas-markets"
git pull origin feature/phase20-unified-provider-integration
docker compose up -d --build
docker compose exec app python -m pytest
docker compose exec app python -m app.scripts.verify_integrations
```

## Certification scripts

```powershell
# Bybit Testnet connectivity/order-path certification (execution currently provider-blocked)
docker compose exec app python -m app.scripts.certify_bybit_execution

# Fusion MT5 Demo execution certification
docker compose exec app python -m app.scripts.certify_mt5_execution
```

IBKR Paper execution certification is the next script/task to be added.

## Documentation

See:

- `docs/ARCHITECTURE.md`
- `docs/ERD.md`
- `docs/AUTHORIZATION.md`
- `docs/CURRENT_STATUS.md`
- `docs/PROVIDERS.md`
- `docs/TESTING_AND_CERTIFICATION.md`
- `docs/ROADMAP.md`

Engineering workflow: **DESIGN → BUILD → TEST → COMMIT → DEPLOY → LIVE SMOKE TEST → DOCUMENT → RELEASE**.
