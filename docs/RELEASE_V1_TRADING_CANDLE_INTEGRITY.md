# Trading candle integrity

Certified Bybit/IBKR readiness now evaluates timestamped completed bars only.
The IBKR opposite-signal position manager applies the same policy when native
protection is disabled. Its native protective lifecycle remains unchanged.
The legacy Bybit/IBKR scan also applies the completion boundary. MT5 inputs,
scoring, router rules, sizing and broker execution/certification gates are not
changed by this release.

Trading requests 201 bars, removes bars whose end is later than decision time,
then retains the most recent 200. At least 30 completed bars are required by
the existing engine. Missing/non-integer timestamps, duplicate/reordered rows,
mismatched intervals, invalid end times or OHLC values block the decision.
No candle is synthesized and market-session gaps remain permitted. Intraday
end is start plus interval; completion uses UTC epoch milliseconds. This is
not a provider freshness or exchange-clock synchronization certification.

IBKR candle requests explicitly map 3m to `3 mins`, including duration sizing.
Unknown intervals return 400; there is no silent 5m fallback. Intraday requests
use IBKR `formatDate=2` for epoch seconds; responses add timestamp_ms,
bar_end_ms, interval and actual_timeframe. Human-readable UTC `time` and raw
source_time remain available to chart consumers. Daily US-dollar stock bars
use their date in the America/New_York calendar and complete at the following
local midnight, conservatively after the session; DST spans 23/25 hours.
Other daily contract calendars are explicitly unsupported rather than guessed.

IBKR trading rejects an old bridge without verified actual_timeframe metadata.
Bridge/app rollout must therefore be coordinated. A failed candle check blocks
new decisions; it does not cancel existing orders or alter native protection.
Readiness includes candle_integrity with policy, timeframe, count and final
start/end timestamps for post-deployment verification.

Public chart endpoints continue receiving forming candles. The filtering is at
the trading decision boundary, not the shared chart feed. Preserve the existing
portfolio chart and quote workflows when verifying deployment.

Primary API references:
- https://interactivebrokers.github.io/tws-api/classIBApi_1_1EClient.html
- https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars

## Validation and rollout

Tests cover completion at exact UTC boundaries, retention of 200 after removing
forming bars, missing/duplicate/reversed/mismatched inputs, OHLC/end validation,
metadata requirements, true 3m requests, invalid intervals, epoch conversion,
readable chart timestamps, daily DST and block-before-signal behavior.
Existing sizing/position-exit fixtures now provide timestamped candle evidence.
Run full production-equivalent container tests with tools mounted before merge.

Before rollout record current app and bridge source/image and versioned rollback
artifacts. Deploy the merged bridge code and app together without changing the
Gateway or database. Verify connected Paper health, request TSLA 3m candles and
check actual_timeframe/three-minute timestamps, app health/migration, preserved
native protection, current broker orders/positions, chart response and a new
readiness candle_integrity record. Never recreate protective orders merely
because the application was restarted. The change does not establish profits
or live-money readiness.

## Evidence persistence correction

The first deployment produced candle_integrity in readiness but the preflight
attribution allowlist omitted it, so automation_actions did not retain that
field. The completion filter was active; absence of this field alone did not
prove an unfiltered decision. Preflight now deep-copies candle_integrity into
every PASS/SKIP/BLOCK/error outcome before action persistence. Regression checks
cover all four outcomes and mutation isolation. Old audit rows remain unchanged
and are not backfilled from current data. No broker or execution behavior changes.
