# Live system logs

## Purpose and access

The **Logs** navigation page is available to ADMIN accounts only. `GET /logs`
enforces that role on the server. It refreshes every three seconds while visible,
with filters for source, severity, provider, BUY/SELL/HOLD, outcome, time window
and search. Pause, older-event pagination, expanded details and JSON export of
the loaded events are provided. Cards and wrapping controls support phones.
The export contains exactly the events loaded in the browser, not full history.

## Recorded coverage

- Server: startup/shutdown, worker starts/unhandled exits, HTTP starts/completions,
  status, duration, request ID and safe Python logger/error-class metadata.
- Automation: scan/readiness/preflight starts and returns, per-symbol checks and
  persisted scan summaries. Scan IDs link broker reads, strategy and trade events.
- Providers: IBKR, Bybit private/public, MT5 and Twelve Data request starts,
  responses, cancellations and failures; news feed reads and parsed article counts.
- Strategy: actual router evaluation, market regime, advisory strategy, confidence,
  eligible strategy names, reasons, signal direction and risk outcome. Eligibility
  is not an individual backtest or execution of every named candidate.
- Trading: readiness/preflight outcomes, approvals, execution-workflow attempts,
  observed engine outcomes and committed automation action audit records.
- Security/safety/configuration: authentication audit outcomes, live-execution
  events and strategy revision history, without raw configuration or free text.
- Frontend: page openings and metadata-only JS/resource/API failures reported by
  signed-in clients. `/logs/browser` rejects arbitrary messages, stacks, URLs,
  request bodies and extra fields; limits are 60 events/user/minute on the server
  and 30/client/minute in the browser.

`ENGINE_OUTCOME` explicitly says its audit commit is pending. A committed audit
record uses `origin=PERSISTED_AUDIT`. `EXECUTION_ATTEMPT` does not prove submission
or fill. `SUBMITTED` is not `EXECUTED`; existing broker verification determines
the latter. Router mode remains advisory/SHADOW, with no change to trading rules.
Broker-native positions, orders, fills and P&L remain authoritative.

## Limits and privacy

This is structured application telemetry, not an unlimited raw system console.
External Docker daemon, Caddy, systemd, operating-system and Gateway raw logs
are **not collected**. Python log text/arguments and exception messages are
omitted, since they can contain secrets. Provider payloads, credentials, headers,
account identifiers, query strings and raw audit JSON are not exported. Runtime
events begin after activation; earlier detailed reads cannot be reconstructed.
Existing database audit outcomes are available within the selected time window.

Application emitters only append to a bounded memory buffer and a non-blocking
queue. A separate daemon thread writes to Redis; trading does not wait for Redis.
Redis holds the latest 20,000 runtime events; the key expires after seven days
without writes. Memory holds up to 20,000 events per process. Queues are bounded
at 2,000; outages/overflow/shutdown may lose persistence. The page reports storage
mode and persistence drops. Redis is best-effort telemetry, not the financial
audit ledger or a guarantee of complete collection.

The API limits each database source to its newest 2,000 records in the requested
1–168 hour window and reports a capped window. Each response has at most 500
events; the browser retains at most 3,000. Equal-time pagination includes the
event ID. Closed tabs, browser crashes before reporting and abrupt process exits
can leave gaps. Logs-page polls do not log themselves or call providers.

## Validation and release

Regression tests cover ADMIN/USER/anonymous access, strict browser events and
rate limits, actual database outcomes, malformed audit JSON, filters, tie-safe
pagination, task-local correlation, provider exceptions without order retries,
credential omission, bounded queue overflow, offline Redis fallback, advisory
strategy semantics, asset order, navigation, escaping, pause and scroll retention.
Run the full production-equivalent container suite before deployment. Node tests
run where Node is installed; its absence is reported as a skip in Python images.

No database migration is added; Alembic head remains `20261001_0022`. Deploy only
the merged app image after preserving a rollback image. No bridge, Gateway,
PostgreSQL, Redis or trading/budget settings need changing. Verify health and
authenticated Logs on desktop and phone, observe one full scan, and verify that
provider failures do not prevent page or health responses. Rollback by restoring
the saved app image; database audit and broker positions remain intact.
