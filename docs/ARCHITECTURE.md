# ATLAS MARKETS — Current Architecture

Last reconciled with active development branch: 2026-08-25.

## 1. Purpose and architecture invariants

ATLAS MARKETS is a provider-independent, multi-user, multi-account, multi-market trading platform. It separates market data, analysis, strategy decisioning, risk, provider routing, execution, reconciliation, persistence and presentation.

Core invariants:

1. External broker/exchange accounts are represented by internal `BrokerProfile` UUIDs.
2. Account-scoped data is owned by an authenticated user and must be authorization-filtered.
3. The only application roles are `ADMIN` and `USER`.
4. Provider credentials are stored encrypted and are never intentionally exposed by read APIs.
5. Strategy decisions do not directly execute orders; risk and execution gates remain server-side.
6. Live Money execution is explicitly gated per broker profile and is not certified for unrestricted automation.
7. Paper/Demo/Testnet validation precedes Live Money.
8. Certification instruments are test instruments only; the architecture is multi-instrument.

## 2. Current runtime topology

```text
Browser / Mobile UI
        |
        v
FastAPI / Uvicorn (Docker)
        |
        +-------------------+--------------------+
        |                   |                    |
        v                   v                    v
   PostgreSQL             Redis          ATLAS services
                                                |
                           +--------------------+-------------------+
                           |                    |                   |
                           v                    v                   v
                    Market/History         Strategy/Risk      Provider Routing
                           |                                        |
                           |                 +----------------------+------------------+
                           |                 |                      |                  |
                           v                 v                      v                  v
                     Twelve Data       Fusion MT5 Bridge       IBKR Bridge          Bybit
                     data only          Windows/MT5          Windows/TWS       V5/Testnet API
```

The project currently runs the main application, PostgreSQL and Redis with Docker Compose. MT5 and IBKR require Windows-side bridge connectivity to their native/local trading environments.

## 3. Provider responsibilities

- **Interactive Brokers (IBKR):** stocks and ETFs. Current environment: Paper.
- **Fusion MT5:** FX, metals and commodities. Current environment: Demo.
- **Bybit:** crypto. Current environment: Testnet.
- **Twelve Data:** market/historical data only; never an execution broker.

The older blueprint reference to OANDA is no longer the active provider design. Fusion MT5 is the active FX/metals/commodities execution integration.

## 4. Broker profile implementation

The current `BrokerProfile` model contains the operational provider/account state directly, including:

- `id` UUID / logical profile identifier
- `user_id`
- `provider`
- `account_label`
- `environment`
- `external_account_ref`
- `is_enabled`
- `is_active`
- `live_execution_enabled`
- `live_execution_armed_at`
- encrypted API key/secret/credential blob fields
- `credentials_configured`
- connection/sync status and timestamps
- cached equity/wallet/available balance
- open-position/open-order counts

This is the current implementation and supersedes the original Phase 0 proposal that required a separate one-to-one `broker_credentials` table.

## 5. Execution architecture

Desired execution path:

```text
Market + historical + intelligence inputs
        ↓
Analysis / strategy decision
        ↓
Risk evaluation
        ↓
Position sizing
        ↓
Provider routing
        ↓
Environment/live-money gate
        ↓
Provider client / local bridge
        ↓
Provider acknowledgement
        ↓
Position/order/execution reconciliation
        ↓
Performance/history
```

No AI or strategy component should bypass risk, environment or provider safety gates.

## 6. Current provider certification

| Provider | Connectivity | Execution |
| --- | --- | --- |
| Fusion MT5 Demo | Certified | **Certified** |
| IBKR Paper | Certified | Next certification task |
| Bybit Testnet | Certified | Provider-blocked by Bybit `10024` |
| Twelve Data | Certified | N/A — data only |

Fusion MT5 execution has been proven by opening and closing a controlled 0.01-lot EURUSD Demo position and verifying the exact certification ticket returned to flat state.

IBKR Paper connectivity/account/market/order bridge functionality is available; controlled Paper execution certification is the immediate next task.

Bybit private authentication and order-submission path are operational, but a valid Testnet BTCUSDT request was rejected by Bybit error `10024` due to a regulatory product/service restriction. ATLAS must not bypass that restriction.

## 7. Multi-instrument architecture

The final system is not one-symbol-per-provider. Representative intended universes include stocks/ETFs through IBKR, FX/metals/commodities through MT5 and crypto through Bybit when permitted.

Provider routing must consider asset class, provider/account capability, symbol availability, account state, environment, connection health, market session, risk authorization and buying power/margin.

Provider-supported instrument discovery/validation is preferred over relying only on static symbol lists.

## 8. Analysis and strategy

ATLAS is intended to combine deterministic technical analysis, multi-timeframe information, historical intelligence, market regime/context and financial/news intelligence into explainable BUY/SELL/HOLD decisions.

Strategy methodology must be measurable and testable. Arbitrary unexplained AI scores are not sufficient for production execution.

The repository already contains strategy, signal, historical, news and symbol-strategy persistence/modules. These should be evolved rather than replaced by a disconnected new engine.

## 9. Risk and live-money safety

Risk remains account-scoped and immediately precedes execution. Target controls include position/exposure limits, daily loss, drawdown, maximum open positions, leverage/margin, stop/take-profit policy, spread/slippage, stale signals, duplicate orders, correlated exposure, provider health, market hours and kill-switch behavior.

`BrokerProfile.live_execution_enabled` and `live_execution_armed_at` are part of the current live safety model. Authentication alone never authorizes Live Money execution.

## 10. Authentication and authorization

Exactly two roles exist:

- `ADMIN`: platform-wide administration, users, accounts/providers, strategy/risk, integrations, engine/system controls and aggregate results.
- `USER`: own authorized accounts/data/results.

Every account-scoped route/service must derive or validate authorized broker profile ownership. Client-supplied profile IDs are never trusted by themselves.

## 11. Persistence

Current model modules include authentication, broker profiles, automation, historical intelligence, news, paper trading, reporting, signals, strategy and symbol-strategy state. `docs/ERD.md` describes the implemented model families and distinguishes current tables from longer-term domain targets.

PostgreSQL is durable truth. Redis is used for transient/runtime coordination/cache roles where implemented.

## 12. Testing and certification

Current known automated baseline: **55 passed, 1 warning**.

Connectivity verification:

```powershell
docker compose exec app python -m app.scripts.verify_integrations
```

MT5 execution certification:

```powershell
docker compose exec app python -m app.scripts.certify_mt5_execution
```

Bybit order-path certification:

```powershell
docker compose exec app python -m app.scripts.certify_bybit_execution
```

See `TESTING_AND_CERTIFICATION.md` for evidence and certification rules.

## 13. Frontend direction

The frontend remains under active development. Final navigation should cover Dashboard, Markets, Analysis, Signals, Positions, Orders, Performance, History, Integrations, Strategy, Risk Management, Users, Settings and System Status as permitted by role.

Desktop and phone responsiveness are requirements. Provider setup must ultimately become simpler than the engineering workflow used during integration development.

## 14. Development sequence from current checkpoint

1. Certify IBKR Paper execution.
2. Validate multi-instrument universes/provider capabilities.
3. Validate automatic provider routing.
4. Expand/validate analysis and strategy methodology.
5. Harden risk controls.
6. Certify the automatic scan → analyze → signal → risk → route → execute → monitor → exit → record lifecycle.
7. Expand performance analytics/historical evaluation.
8. Complete frontend/mobile UX.
9. Run extended simulation and operational testing.
10. Only then assess Live Money readiness.

See `CURRENT_STATUS.md`, `PROVIDERS.md`, `ROADMAP.md` and `TESTING_AND_CERTIFICATION.md` for the active development checkpoint.
