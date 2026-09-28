# ATLAS MARKETS v1 — Current Status

Last verified: 2026-09-28

## Canonical baseline

- Git branch: `main`
- Git tag: `v1.0.0`
- Commit: `5ef08db6426876be6019541c45c0b3b3851f85eb`
- Environment: production application with simulation/paper/testnet providers
- Database: PostgreSQL at Alembic head `20260925_0019`
- Live Money: explicitly gated

Older experimental and reverted release lines are historical Git data, not production
baselines. New work must preserve this application's data, frontend, authentication,
administration, provider integrations, portfolio/activity/P&L and analytics.

## Runtime

- FastAPI application, PostgreSQL 17 and Redis 7 are healthy on Oracle Cloud.
- Production app is bound to localhost port `8100`.
- Bybit Testnet Spot is integrated with managed-inventory safeguards.
- The configured IBKR Paper account is connected through Gateway port `4002` and bridge port
  `8766`.
- The IBKR watchdog checks every minute and restarts a stale bridge.
- IB Gateway daily Auto Restart is enabled for both stored profiles; periodic IBKR security
  authentication may still require VNC/mobile approval.
- MT5 remains a separate execution-node workstream and must not be represented as ready unless
  runtime authorization passes.

## Product capabilities

- ADMIN/USER authentication and revocable sessions.
- encrypted external-provider profiles and account synchronization.
- WATCH, SIGNALS and AUTO_TRADE per-symbol modes.
- technical, historical, news and forward shadow intelligence.
- independent provider, environment, certification, risk and kill-switch gates.
- provider-native portfolio, order/fill context and performance.
- durable scan/action/risk/audit evidence and conservative attribution.

## Known boundaries

- Broker-native state is authoritative for positions, orders, fills, balances and P&L.
- Delayed IBKR data is not equivalent to subscribed real-time execution-quality data.
- Shadow results are analytical and never broker P&L.
- Provider availability is independent from core application health.
- No claim of guaranteed profit or continuous provider authentication is made.

## Documentation baseline

The v1 documentation package is indexed by `DOCUMENTATION_INDEX.md` and includes the
architecture, ERD, ERP-style operating model, API, user/admin, operations, IBKR continuity,
security, backup/recovery, provider, testing, handover and roadmap documents.
