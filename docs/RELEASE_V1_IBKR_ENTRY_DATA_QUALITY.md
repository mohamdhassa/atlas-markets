# IBKR entry data quality and bounded release closeout

## Problem and behavior

A 201-bar five-minute request used a two-calendar-day duration even though
useRTH=1 supplies regular-session bars. Production returned only 140 completed
bars, with roughly 15-minute lag. Quote snapshots did not expose the actual
IBKR market-data type, so delayed prices and historical fallbacks could reach
entry sizing. This release blocks those inputs from opening positions.

Intraday history now estimates 390-minute regular sessions, calendar expansion
and padding. Requests remain single, bounded calls: 1m caps at one day;
3m/5m/15m at seven days; 30m at 31 days; hourly at 365 days. This is a coverage
estimate, not a guarantee across holidays or sparse contracts. Missing coverage
blocks rather than synthesizing candles or retrying indefinitely. The normal
201-bar 5m request now asks for seven days; 3m asks for six days. Charts still
receive up to their requested count, including the forming bar.

The bridge records marketDataType callbacks (1 live, 2 frozen, 3 delayed,
4 delayed-frozen), delayed tick markers, per-price local receipt timestamps and
last-trade timestamps when provided. Quotes expose data_status, including
UNKNOWN and HISTORICAL; invalid/nonpositive price ticks are ignored. These are
provider-reported modes, not exchange-clock synchronization certification.

IBKR new-entry readiness requires 200 completed bars. The last bar's end must
be no older than one interval plus 90 seconds, allowing the normal elapsed
portion of the next bar. This deliberately blocks delayed intraday data and
session gaps; it does not infer exchange opening times. Snapshot mode must be
live with no delayed ticks. The selected ask/last/bid (BUY) or bid/last/ask (SELL)
needs its own receipt within 30 seconds. Last-price fallback additionally needs
a provider last-trade timestamp within 30 seconds (up to two seconds future
clock tolerance). A bid update cannot refresh an old ask. Local receipt time
is never represented as an exchange event time. A last-trade timestamp is not
required for a fresh live bid/ask; its absence stays explicit in audit metadata.

Readiness and preflight retain market_data_quality, including failed count/age/
mode checks. The certified entry executor independently re-fetches candles and
quote before what-if/submission, retaining its own evidence. The legacy IBKR
entry path uses the same checks. Exceptions before submission still submit
nothing. Existing account, risk, ownership, duplicate-position/order and Paper
certification checks remain active.

Native protection, protective-fill reconciliation and opposite-signal position
exits are unchanged. They retain their existing data validation and do not
inherit the new-entry coverage/freshness requirements. Bybit and MT5 behavior
is unchanged. No schema migration, strategy, score, risk-setting or live-route
change is included. Historical strategy evidence is not reconstructed.

## Validation and rollout

Regression tests cover actual/delayed callbacks, invalid prices, unknown/frozen/
delayed/fallback rejection, missing/old/future receipt, last-only source time,
per-side price freshness, insufficient/stale candle windows, block-before-signal,
submission-boundary rechecks and deep-copy persistence across all preflight
outcomes. Existing position-exit and native timeout/duplicate/reconciliation
regressions remain required. Run the full suite in the server container before
merge. Local tests alone do not authorize deployment.

Record fresh production commit/images, bridge bind source, orders, positions
and health; retain versioned app-image and bridge-source rollback artifacts.
Deploy merged bridge and app together with native protection enabled. Restart
the bridge only as needed; do not restart Gateway or recreate protective orders.
An old bridge lacking quote provenance now blocks new entries intentionally.
Verify Paper health, actual timeframe/count, quote mode/receipt fields, app
health and Alembic head, charts, logs and persisted new-scan quality evidence.
If only delayed data is entitled, charts can work while new entries are blocked;
resolve the appropriate API user's real-time feed rather than disabling checks.

Primary API references:
- https://interactivebrokers.github.io/tws-api/historical_bars.html
- https://interactivebrokers.github.io/tws-api/historical_limitations.html
- https://www.interactivebrokers.com/docs/tws-api/doc/md/delayed-data
- https://www.interactivebrokers.com/docs/tws-api/doc/md/streaming-data

## Fixed closeout scope

Freeze this milestone: no new signal families, parameter search, timeframe
optimization or dashboard redesign. Close the engineering milestone once:

1. This combined container suite passes and coordinated deployment verifies.
2. Ten consecutive scheduled scans during a regular session retain quality
   evidence or a specific expected block; no unclassified data/execution error.
3. Broker positions and protective quantities agree, no unknown submission is
   outstanding, and a broker-confirmed close appears exactly once in the ledger.
4. One app restart and a controlled Paper connectivity interruption preserve
   existing orders, block new entries during failure and reconcile on recovery.
   Capture evidence; do not interrupt a live account for this check.

These are operational acceptance checks, not statistical proof of a strategy.
Finish and archive the milestone as a verified Paper release if they pass.
Avoid repeated full-suite runs after a passing unchanged build.

Real-money automation remains a separate go/no-go decision. Current certified
routes are simulation-only; flipping a flag is not a supported live rollout.
It requires a separately reviewed provider execution/certification path and
explicit capital/loss limits, plus independent evidence for one frozen policy
after fees/slippage. Existing Spot comparisons were negative and repeatedly
inspected; they are not fresh validation. There is no strategy profitability
claim or permission to enable real-money execution in this release. Engineering
completion need not wait for finding a profitable strategy.
