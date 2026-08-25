# Atlas Markets — Architecture Blueprint

## 1. Architecture goals

Atlas Markets is designed as a provider-independent, multi-user, multi-account, real-time trading platform for FX and cryptocurrency. The architecture separates market data, analysis, decisioning, risk, execution, monitoring, persistence, and presentation so each subsystem can be tested independently.

Core invariants:

1. Every trading account has a unique internal `profile_id`.
2. User data is isolated at the database and service layer.
3. Broker secrets are encrypted and never returned after storage.
4. Core strategy code never depends directly on Bybit, OANDA, or IBKR APIs.
5. Every signal stores reasons and every order passes through the risk engine.
6. Kill Switch and Safe Mode are enforced server-side.
7. Paper/demo operation precedes any live activation.

## 2. Runtime topology

```text
Internet
   |
   v
Caddy :443
   |
   v
FastAPI / Uvicorn (private Docker network)
   |
   +-------------------+--------------------+------------------+
   |                   |                    |                  |
   v                   v                    v                  v
PostgreSQL           Redis            Worker Set          WebSocket Hub
(private)          (private)          (private)           (private)
                                         |
                      +------------------+------------------+
                      |                  |                  |
                      v                  v                  v
                 Market Data        Analysis          Execution /
                   Workers           Workers          Position Monitor
                      |                  |                  |
                      +------------------+------------------+
                                         |
                                         v
                                BrokerAdapter Layer
                                 /             \
                                v               v
                         Bybit Adapter       FX Adapter
                         Demo/Testnet       OANDA/IBKR
```

Only Caddy is internet-facing. PostgreSQL, Redis, Uvicorn, and workers remain private.

## 3. Logical layers

### API / Web layer
Responsibilities: authentication, RBAC, dashboards, forms, account management, charts, status, admin controls, WebSocket frontend feeds, and visible action feedback.

### Domain layer
Contains provider-independent business objects and services for instruments, market snapshots, signals, decisions, risk approvals, orders, positions, trades, strategy versions, and performance.

### Broker abstraction
`BrokerAdapter` is the only interface the engine uses to communicate with external execution providers.

Initial interface:

```python
class BrokerAdapter(ABC):
    async def connect(self): ...
    async def disconnect(self): ...
    async def test_connection(self): ...
    async def get_account(self): ...
    async def get_balance(self): ...
    async def get_positions(self): ...
    async def get_orders(self): ...
    async def get_instruments(self): ...
    async def get_quote(self, symbol: str): ...
    async def get_candles(self, symbol: str, timeframe: str, limit: int): ...
    async def stream_prices(self, symbols: list[str]): ...
    async def place_order(self, order): ...
    async def cancel_order(self, external_order_id: str): ...
    async def close_position(self, position_id: str): ...
    async def modify_stop(self, position_id: str, price): ...
    async def modify_take_profit(self, position_id: str, price): ...
```

Provider-specific payloads are normalized before entering the domain layer.

## 4. Market-data pipeline

```text
Provider WebSocket
    ↓
Provider parser
    ↓
Canonical Tick model
    ↓
Redis stream / latest-price cache
    ↓
Candle builder
    ↓
1m base candles
    ↓
Timeframe aggregator
    ↓
3m / 5m / 15m / 30m / 1h / 4h / 1d
    ↓
PostgreSQL historical persistence
    ↓
Analysis scheduler / event trigger
```

Rules:
- Timestamps stored in UTC.
- Provider timestamps retained where useful for reconciliation.
- Idempotency keys prevent duplicate candle/tick ingestion.
- Stale-feed detection triggers Safe Mode when configured thresholds are exceeded.

## 5. Technical-analysis engine

Pure deterministic functions consume normalized OHLCV datasets and output structured results.

Modules:
- trend: EMA, SMA, slopes, ADX, higher-timeframe alignment
- momentum: RSI, MACD, stochastic, rate of change
- volatility: ATR, Bollinger Bands, historical volatility, expansion/contraction
- market structure: HH, HL, LH, LL, BOS, breakout, failed breakout
- support/resistance: swings, previous-day levels, session levels, pivots, liquidity zones
- candles: engulfing, hammer, shooting star, pin bar, doji, inside/outside bar
- regime: trend/range plus low/normal/high volatility

All pattern definitions must be mathematical and unit tested.

## 6. Multi-timeframe engine

Default decision hierarchy:

```text
4H  -> macro direction / regime
1H  -> primary trend
15M -> setup
5M  -> entry signal
1M  -> execution refinement
```

The engine produces alignment/conflict metadata rather than forcing agreement. A strategy can explicitly reject conflicting higher-timeframe conditions.

## 7. Signal and decision engine

Each strategy produces independent factor scores. The signal engine aggregates them into a versioned score and classification.

Example output:

```json
{
  "profile_id": 4,
  "instrument": "BTCUSDT",
  "timeframe": "5m",
  "decision": "LONG",
  "score": 84,
  "classification": "STRONG_SIGNAL",
  "reasons": [
    "bullish_market_structure",
    "higher_timeframe_alignment",
    "support_held",
    "ema_confirmation",
    "breakout_confirmed"
  ]
}
```

No signal is executable until risk approval is recorded.

## 8. Risk engine

Risk is account-scoped and runs immediately before execution.

Inputs include:
- equity and available margin
- risk per trade
- daily/weekly loss
- drawdown
- current open positions
- FX and crypto exposure
- leverage
- spread and slippage estimates
- signal score
- cooldown / consecutive-loss rules
- stop distance and instrument precision

Output is an immutable approval/rejection event with reasons.

## 9. Position sizing

Separate sizing implementations exist for FX and crypto behind a common domain API. Position size uses equity, risk %, entry, stop distance, instrument precision, minimum quantity, contract size, leverage, and currency conversion.

Fixed arbitrary order quantities are prohibited in automated strategy execution.

## 10. Execution and reconciliation

Execution flow:

```text
Decision
  ↓
Risk Approval
  ↓
Position Size
  ↓
Execution Request
  ↓
BrokerAdapter
  ↓
Provider
  ↓
Provider acknowledgement
  ↓
Order event reconciliation
  ↓
Position reconciliation
```

Client order IDs / idempotency keys prevent duplicate submissions. Reconciliation workers periodically compare local orders/positions with provider truth.

## 11. Exit engine

Supports hard stop, take profit, trailing stop, break-even, partial take-profit, signal reversal, time exit, volatility exit, risk exit, and emergency exit. Provider-native protective orders are preferred when supported, with server-side monitoring as a complementary layer.

## 12. Safe Mode and Kill Switch

Kill Switch: immediately blocks all new order execution server-side.

Safe Mode: automatically blocks new positions when configured operational/risk conditions fail, including stale prices, provider disconnects, DB/Redis failures, abnormal spread/slippage, reconciliation failures, and loss/drawdown limits.

Existing-position policy is explicit and versioned; Safe Mode must never ambiguously abandon open risk.

## 13. Backtesting architecture

Backtester reuses strategy and analysis logic while replacing live market/broker services with historical feeds and a simulated execution model.

Pipeline:

```text
Historical candles
   ↓
Strategy/Analysis
   ↓
Signal
   ↓
Risk
   ↓
Simulated fills
   ↓
Portfolio state
   ↓
Metrics
```

Simulation includes spread, commission, slippage, funding and configurable latency assumptions. Validation supports training, validation, out-of-sample, and walk-forward segments.

## 14. Authentication and authorization

Only two roles: ADMIN and USER.

ADMIN: platform-wide users, accounts, strategy, risk, integrations, engine state, system health and aggregate performance.

USER: own account connection, balances, equity, P&L, positions, orders, signals, decisions, charts and performance.

Every account-scoped API obtains allowed `profile_id` values from the authenticated identity; client-supplied IDs are never trusted without authorization checks.

## 15. Credential security

Credentials are stored in `broker_credentials.encrypted_json` using a server-held `ATLAS_MARKETS_MASTER_KEY`. A deterministic credential fingerprint supports duplicate-account prevention without revealing secrets.

API keys/secrets are never logged, returned after persistence, or stored in readable columns.

## 16. Frontend page map

ADMIN:
- Dashboard
- Markets
- Charts
- Signals
- Positions
- Orders
- Performance
- Users
- Accounts
- Strategy
- Risk
- Integrations
- System

USER:
- Dashboard
- Markets
- Charts
- Signals
- Positions
- Orders
- Performance
- Accounts

Every mutation uses processing → backend response → success/error → refresh behavior. No silent buttons.

## 17. Proposed Python structure

```text
atlas-markets/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── routes_auth.py
│   │   ├── routes_admin.py
│   │   ├── routes_accounts.py
│   │   ├── routes_markets.py
│   │   ├── routes_signals.py
│   │   ├── routes_orders.py
│   │   ├── routes_positions.py
│   │   └── routes_performance.py
│   ├── auth/
│   ├── brokers/
│   │   ├── base.py
│   │   ├── mock.py
│   │   ├── bybit.py
│   │   ├── oanda.py
│   │   └── ibkr.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models/
│   ├── market_data/
│   ├── analysis/
│   │   ├── trend.py
│   │   ├── momentum.py
│   │   ├── volatility.py
│   │   ├── structure.py
│   │   ├── support_resistance.py
│   │   ├── candles.py
│   │   └── regime.py
│   ├── strategies/
│   ├── signals/
│   ├── risk/
│   ├── execution/
│   ├── positions/
│   ├── backtesting/
│   ├── workers/
│   ├── services/
│   ├── schemas/
│   ├── templates/
│   └── static/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
├── docs/
├── ops/
│   └── oracle/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
└── README.md
```

## 18. Docker architecture

Initial services:
- `atlas-markets-app`
- `atlas-markets-worker-market`
- `atlas-markets-worker-analysis`
- `atlas-markets-worker-execution`
- `atlas-markets-worker-position`
- `atlas-markets-postgres`
- `atlas-markets-redis`
- `atlas-markets-caddy`

Workers may initially share one Python image but run distinct commands. This keeps deployment simple while preserving process isolation.

## 19. Testing strategy

Unit tests cover deterministic logic: indicators, candle patterns, structure, scoring, risk, sizing, encryption helpers, authorization helpers.

Integration tests cover PostgreSQL, Redis, migrations, API endpoints, BrokerAdapter contracts, demo adapters, account isolation, duplicate-account rejection, Safe Mode and Kill Switch.

Smoke tests cover the deployed system through Caddy: health, login, role access, pages, account connection tests, market feeds, charts, signals, risk, order paths, engine controls and user isolation.

Tests are developed with each phase rather than deferred to release.

## 20. Oracle deployment architecture

Atlas Markets uses separate resources from Atlas Trader:
- repository
- Docker network
- containers
- PostgreSQL database/volume
- Redis volume
- environment file
- backup directory
- Caddy site configuration

Suggested private network: `atlas-markets-private`.

Suggested env path: `~/atlas-markets/.env.oracle` with restrictive permissions.

Database and Redis ports are never published publicly. Uvicorn binds only inside the private Docker network; Caddy terminates HTTPS.

## 21. Phase 0 architecture decisions

Approved design direction:
- modular monolith + isolated worker processes rather than microservices initially
- shared PostgreSQL as durable truth
- Redis for transient/latest market state and worker coordination
- asynchronous broker adapters
- event-oriented pipelines with persisted audit records
- provider-neutral domain models
- one account = one `profile_id`
- immutable strategy/risk decision history
- paper/demo-first release path

This architecture is intentionally scalable without adding distributed-system complexity before it is needed.

---

# Current Implementation Addendum — 2026-08-25

The blueprint above is preserved as the original architecture reference. The current implementation extends it rather than replacing it.

## Provider expansion

The active provider design now includes:

- **Interactive Brokers (IBKR)** for stocks and ETFs through a Windows TWS/IB Gateway bridge;
- **Fusion MT5** for FX, metals and commodities through a Windows MT5 bridge;
- **Bybit** for crypto through Testnet/V5 private APIs;
- **Twelve Data** for market/historical data only.

The earlier OANDA reference remains part of the original blueprint/history, but Fusion MT5 is the active FX/metals/commodities execution integration in the current implementation.

## Current runtime implementation

The local development/runtime stack currently uses Docker Compose for the FastAPI application, PostgreSQL and Redis. MT5 and IBKR bridges run on Windows because they depend on local/native broker terminals or socket APIs.

## Current BrokerProfile implementation

The current ORM stores provider/account operational state directly on `BrokerProfile`, including environment, enabled/active state, Live Money gates, encrypted API fields or credential blob, connection/sync state, and cached account metrics. This differs from the original separate `broker_credentials` proposal; the original design remains documented above for history, while the ORM/migrations remain authoritative for deployed schema.

## Multi-instrument requirement

The project is now explicitly multi-market and multi-instrument. Certification uses representative symbols only. The intended routing is broadly:

```text
stocks + ETFs                → IBKR
FX + metals + commodities    → Fusion MT5
crypto                       → Bybit (where permitted)
market/historical data       → Twelve Data and provider feeds
```

Routing must later validate symbol availability, account state, environment, provider health, market session, buying power/margin and risk approval.

## Current certification state

| Provider | Connectivity | Execution |
| --- | --- | --- |
| Fusion MT5 Demo | Certified | **Certified** |
| IBKR Paper | Certified | Next certification task |
| Bybit Testnet | Certified | Provider-blocked by `10024` |
| Twelve Data | Certified | Data only |

Fusion MT5 has completed an end-to-end controlled Demo open/close certification. Bybit private authentication and the signed order path work, but Bybit rejected execution with regulatory error `10024`. IBKR Paper execution certification is the immediate next provider task.

## Central-engine direction

After IBKR execution certification, priority returns to the original central architecture goals: multi-instrument discovery, analysis, strategy, risk, routing, automatic execution, monitoring, performance analytics and historical evaluation.

See `CURRENT_STATUS.md`, `PROVIDERS.md`, `TESTING_AND_CERTIFICATION.md`, and `ROADMAP.md` for the current checkpoint.
