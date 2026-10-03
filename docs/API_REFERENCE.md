# ATLAS MARKETS v1 — API Reference

The live OpenAPI schema at `/docs` is authoritative for exact fields. `/health`, `/api/system`
and login are public operational entry points; business routes require authentication.

## Identity and administration

| Method | Path | Purpose | Authority |
|---|---|---|---|
| POST | `/auth/login` | Create an authenticated session | Public |
| GET | `/auth/me` | Return current identity | Authenticated |
| POST | `/auth/logout` | Revoke current session | Authenticated |
| GET/POST | `/admin/users` | List or create users | ADMIN |
| PATCH | `/admin/users/{user_id}` | Change role or active state | ADMIN |

## Provider accounts

- `/accounts*` — owned broker profiles, credentials, connection tests, activation and sync.
- `/ibkr*` — IBKR readiness and external bridge operations.
- `/providers/bybit*` — Bybit environment, diagnostics and certification evidence.
- `/broker-native*` — provider-native positions, orders, fills and performance context.

Connection success does not grant execution. Environment, certification, strategy, risk,
kill-switch and live-money policies remain independent.

## Strategy, intelligence and automation

- `/strategies/symbols*` — per-symbol provider route, mode and parameter overrides.
- `/analysis*` — technical, adaptive, multi-timeframe and shadow analysis.
- `/historical*` — stored candles, probability and backtest services.
- `/news*` — stored news and symbol context.
- `/universe*` — instrument validation and readiness.
- `/automation/state` — engine and kill-switch state.
- `/automation/scans` and `/automation/actions` — durable cycle and action history.
- `/automation/scan-now`, `/automation/kill`, `/automation/restart` — operator controls.

Modes are `WATCH`, `SIGNALS` and `AUTO_TRADE`. `AUTO_TRADE` only makes a symbol eligible for
preflight; it never guarantees execution.

## Portfolio and reporting

- `/portfolio*` — unified provider-native exposure.
- `/positions/lifecycle*` — tracked position lifecycle.
- `/performance/broker-native` — provider starting capital, broker equity, realized P&L,
  strategy value, FIFO entry/duration matching, exact-order attribution and contextual news.
- `/performance*` — other broker-native and unified performance views.
- `/strategies/performance*` — conservative strategy attribution.
- `/reporting*` — daily records and exports.

## Operational endpoints

- `GET /health` — application, PostgreSQL and Redis health.
- `GET /api/system` — stable capability metadata.
- `GET /release/readiness` — execution and release gates.

## Error interpretation

| Status | Meaning |
|---|---|
| 400/422 | Invalid input or schema validation |
| 401 | Missing or expired authentication |
| 403 | Role or safety-policy denial |
| 404 | Resource absent from caller scope |
| 409 | Duplicate or lifecycle conflict |
| 502 | Provider or bridge failure |
| 503 | Required dependency/configuration unavailable |
