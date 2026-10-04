# Provider request isolation and IBKR account-summary cleanup

## Incident and change

On 2026-10-04 IBKR returned error 322 (too many account-summary subscriptions).
The bridge cancelled subscriptions only after a successful wait; timeout paths
left them active. Account requests now cancel in `finally`, discard per-request
values/events, reject incomplete summaries, and wake promptly on broker errors.
Only one summary can be in progress. Overlapping requests receive a retryable
503 instead of creating more subscriptions. Successful results are reused for
at most two seconds; expired or failed results are never served as fresh data.
Reconnection clears that cache. Authentication still runs before every read.

Caddy also recorded long pending requests, followed by resets/refused connections
at watchdog restarts. Portfolio, orders, broker performance and market-monitor
handlers mixed synchronous database operations with awaited broker calls on the
ASGI loop. These read-only views now run in a dedicated four-worker pool with
their own coroutine loops. Excess views receive a retryable 503 promptly; they
cannot queue unbounded work or consume the shared health/auth worker pool.
Cancellation waits for worker completion before dependency session cleanup.
Execution handlers, guards, certification and background trading remain unchanged.
This removes identified blocking paths; production observation is still required
to establish whether other handlers/background jobs cause stalls.

## Validation and deployment

Regression tests cover successful/failed summary cleanup, subscription overlap,
broker rejection, and responsive health/homepage during a blocked page read.
The production-equivalent Docker suite must pass before activation. No migration
is added; Alembic head remains `20261001_0022`.

Deploy the app using the standard rollback-image procedure. The bridge is a
separate deployment: first inspect its mounts and command to determine whether
`tools/ibkr_bridge.py` is bind-mounted or baked into an image. A restart alone
updates only a bind-mounted implementation. Preserve the previous bridge file
or image, activate the new code, then verify `/health`, `/account`, repeated
reads, Paper `simulation=true`, and provider-native positions/orders. Do not
restart Gateway/PostgreSQL/Redis for this change. Preserve watchdog recovery.

Acceptance: authenticated page reads and public health remain responsive during
broker failure, account reads do not accumulate error 322, and watchdog logs
show no restart loop across multiple complete automation scans. Busy-view 503s
are explicit capacity signals, not successful or fabricated broker data.
