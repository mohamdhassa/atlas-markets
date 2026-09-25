# ATLAS MARKETS — API Reference

Last updated: 2026-09-25

The live OpenAPI schema at `/docs` is authoritative for request/response fields. This document groups the operational contract. Except for `/health`, `/api/system`, login and the Bybit OAuth callback, application APIs require an authenticated session or bearer token.

## Authentication and administration

| Method | Path | Purpose | Role |
|---|---|---|---|
| POST | `/auth/login` | Create authenticated session/token | Public |
| GET | `/auth/me` | Current identity | Authenticated |
| POST | `/auth/logout` | Revoke current session | Authenticated |
| GET/POST | `/admin/users` | List/create users | ADMIN |
| PATCH | `/admin/users/{user_id}` | Enable, disable or change role | ADMIN |
| POST | `/admin/users/{user_id}/reset-password` | Reset credential | ADMIN |

Public self-registration is disabled. There are exactly two roles: `ADMIN` and `USER`.

## Accounts and providers

| Method | Path | Purpose |
|---|---|---|
| GET | `/accounts` | User-scoped provider profiles |
| GET | `/accounts/capabilities` | Supported providers/environments/credential fields |
| POST | `/accounts/validate` | Validate configuration without saving |
| POST | `/accounts/connect` | Validate, save and optionally activate profile |
| PUT | `/accounts/{profile_id}/credentials` | Replace encrypted credentials |
| POST | `/accounts/{profile_id}/activate` | Make profile active in its scope |
| POST | `/accounts/{profile_id}/test` | Runtime connectivity test |
| POST | `/accounts/{profile_id}/sync` | Refresh broker-native account state |
| PATCH | `/accounts/{profile_id}/toggle` | Enable/disable profile |
| DELETE | `/accounts/{profile_id}` | Remove eligible profile |
| GET | `/ibkr/readiness` | IBKR runtime readiness |
| GET | `/providers/bybit/{profile_id}/diagnostics` | Bybit permissions/connectivity evidence |

Live execution controls are separately gated; successful connection is not live-money authorization.

## Strategies and automation

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/strategies/symbols` | List/create symbol strategies |
| PATCH/DELETE | `/strategies/symbols/{row_id}` | Update/remove strategy |
| GET | `/strategies/symbols/effective` | Strategy plus inherited effective parameters |
| POST | `/strategies/symbols/route` | Resolve execution provider route |
| POST | `/strategies/symbols/auto-trade/eligible` | ADMIN simulation-only bulk promotion |
| GET/PUT | `/automation/state` | Read/update engine state |
| POST | `/automation/kill` | Engage kill switch |
| POST | `/automation/restart` | Resume after operator review |
| POST | `/automation/scan-now` | Request immediate scan |
| GET | `/automation/scans` | Scan-cycle history |
| GET | `/automation/actions` | Decision/preflight/execution ledger |

Modes are `WATCH`, `SIGNALS`, and `AUTO_TRADE`. Execution still requires all environment, certification, risk and provider gates.

## Shadow intelligence

| Method | Path | Purpose |
|---|---|---|
| POST | `/analysis/shadow/from-candles` | Non-executable decision from supplied candles |
| POST | `/analysis/shadow/backtest` | Cost-aware chronological shadow backtest |
| GET | `/analysis/shadow/observations` | Forward observations and settled outcomes |
| GET | `/analysis/shadow/coverage?days=7` | Provider/symbol scan coverage and skip/error reasons |
| GET | `/analysis/shadow/performance?days=30` | Expectancy, profit factor, drawdown and readiness |

Shadow endpoints never authorize or submit broker orders. `eligible` is analytical evidence only.

## Portfolio, execution and reporting

| Method | Path | Purpose |
|---|---|---|
| GET | `/portfolio` | Unified provider-native portfolio |
| GET | `/broker-orders` | Broker-native orders/fills context |
| GET | `/performance/broker-native` | Broker-native performance |
| GET | `/performance/unified` | Multi-provider P&L overview |
| GET | `/strategies/performance/verified` | Conservatively attributed strategy results |
| GET | `/positions/lifecycle` | Position lifecycle data |
| POST | `/reporting/generate` | Generate account report |
| GET | `/reporting/daily` | Daily report records |
| GET | `/reporting/export.csv` | CSV report export |

## Intelligence and market data

- `/markets/*` — market snapshots and candles.
- `/analysis/*` — technical, adaptive, scenario and multi-timeframe analysis.
- `/historical/*` — history refresh, probability and backtesting.
- `/news` and `/news/context/{symbol}` — news records and symbol context.
- `/universe/*` — validation, monitor, readiness and preflight.

## Operational endpoints

- `GET /health` — application, PostgreSQL and Redis health.
- `GET /api/system` — product/runtime capability metadata.
- `GET /release/readiness` — simulation and live-money gating state.

## Error contract

- `400` invalid request or validation input.
- `401` missing/invalid authentication.
- `403` insufficient role or safety policy denial.
- `404` resource not found in the caller's scope.
- `409` lifecycle conflict or duplicate state.
- `422` schema validation error.
- `502` upstream provider/bridge failure.
- `503` dependency or required configuration unavailable.

Provider failures should identify the provider and preserve other symbols/providers whenever safe isolation is possible.
