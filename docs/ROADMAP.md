# ATLAS MARKETS — Consolidated Core Roadmap

Last updated: 2026-09-23

## Baseline

v1.0.0 remains the rollback/reference Simulation Release. The active work is the `feature/frontend-core-rebuild` branch and PR #34.

Production main is now at the v77 operational checkpoint. The objective remains one maintainable application core with provider integrations, analysis, strategy/risk, portfolio/reporting, administration and a responsive frontend using stable APIs.

## 1. Frontend consolidation

- [x] Remove phase-script chain from `index.html` runtime.
- [x] Add canonical `atlas-core.js` navigation/routing layer.
- [x] Add responsive Operations workspace and Bybit state/certification visibility.
- [x] Fix lexical `buildNav` / `renderPage` integration with legacy `app.js`.
- [ ] Migrate remaining useful page implementations out of legacy phase patches.
- [ ] Replace stale Phase/COMING NEXT copy with runtime state.
- [ ] Verify Dashboard, Markets, Charts, Signals, Positions, Orders, Performance, Accounts, Operations, Users, Strategy, Risk, Integrations and System on desktop and mobile.
- [ ] Remove legacy phase assets only after equivalent behavior is covered by tests.

## 2. Backend consolidation

- [x] Remove missing-router registration workaround from the rebuild core.
- [x] Replace hard-coded temporary provider status in `/api/system` with stable platform metadata.
- [ ] Review route ownership and eliminate duplicate/obsolete route definitions.
- [ ] Keep provider readiness/status sourced from runtime APIs.
- [ ] Validate auth/RBAC isolation for ADMIN and USER.
- [ ] Validate migrations at current Alembic head against a clean database and production-shaped database.

## 3. Provider integration

### Bybit Testnet / Demo

- [x] Private account connectivity infrastructure.
- [x] Spot wallet/holdings/open-order/history support.
- [x] Persistent ATLAS-managed Spot inventory.
- [x] Controlled BUY/SELL certification endpoint.
- [x] Certification reconciliation.
- [x] Provider fill verification.
- [x] Simulation-environment and certification gates.
- [ ] Run controlled certification against the currently configured Testnet account.
- [ ] Verify broker order history and wallet movement against ATLAS state.
- [ ] Verify managed inventory reconciliation after restart.
- [x] Surface clear provider errors/readiness in Operations.
- [x] Add managed Spot balance reconciliation before Bybit Testnet SELL.
- [ ] Verify the next natural ETH/SOL SELL after v76 reconciliation.

### Interactive Brokers

- [x] Paper bridge and account route.
- [x] WhatIf preflight.
- [x] Certified 1-share/order cap.
- [x] broker fill/cancel verification.
- [x] Preserve current working route through rebuild regression testing.
- [x] Distinguish IBKR provider-unavailable state from strategy/risk BLOCK.
- [ ] Observe the next scheduled Gateway restart and verify authenticated-session behavior.
- [ ] Validate configured stock/ETF symbols during market hours.

### Fusion Markets / MT5

- [x] Bridge integration exists.
- [ ] Resolve/validate external terminal authorization on the execution node.
- [ ] Show terminal/bridge authorization failure distinctly from application failure.
- [ ] Regression-test Demo route after terminal connectivity is healthy.

### Twelve Data

- [x] Data-provider integration exists.
- [ ] Regression-test market/historical data ingestion through rebuild.
- [ ] Keep provider data-only; never expose it as an execution account.

## 4. Intelligence and strategy visibility

- [x] Technical analysis foundation.
- [x] Historical candle/backtest persistence.
- [x] News persistence with sentiment/relevance fields.
- [ ] Present technical, historical and news evidence together in the Signals/Strategy UI.
- [ ] Make decision reasons and risk blockers visible and auditable.
- [ ] Add performance diagnostics by provider, symbol and strategy.
- [ ] Avoid representing unverified attribution as broker truth.

## 5. Portfolio, orders and performance

- [ ] Verify broker-native positions and orders pages for every connected provider.
- [ ] Verify unified realized/unrealized P&L.
- [ ] Add usable daily/monthly performance views.
- [ ] Add provider/symbol/strategy filters.
- [ ] Ensure empty/error/loading states are useful on mobile.

## 6. Testing

GitHub Actions is currently unable to start because of the account billing lock; that is infrastructure state, not a test result.

Until Actions is restored:

- [ ] Run full pytest suite in an isolated local/Oracle rebuild container.
- [ ] Run clean-database migration test.
- [ ] Run API smoke tests.
- [ ] Run ADMIN/USER frontend smoke tests.
- [ ] Run provider-specific smoke tests without changing the legacy ATLAS Trader deployment.
- [ ] Fix all regressions before merge.

## 7. Oracle deployment

- [x] Oracle compose profile and environment template exist.
- [x] PostgreSQL/Redis/application production topology exists.
- [ ] Build rebuild image separately from current production image.
- [ ] Run migrations and tests against the rebuild stack.
- [ ] Smoke-test on a non-conflicting port/container name.
- [ ] Back up production database before cutover.
- [ ] Cut over only after acceptance checks pass.
- [ ] Keep v1.0.0/previous production image available for rollback.

## 8. Observation

After the consolidated rebuild is stable, run a multi-week simulation observation without constant strategy changes. Measure P&L, drawdown, win rate, profit factor, average winner/loser, provider/symbol performance, cancellations/rejections, risk blocks, automation uptime and broker/ATLAS state consistency.

## Live Money

Live Money is outside this rebuild. It requires a separate provider-specific release/certification process, smaller initial limits, monitoring, backup/recovery validation, legal/provider eligibility checks and explicit rollback/kill procedures.
