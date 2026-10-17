# Bybit Spot re-entry after quantity dust

## Defect and correction

The broker-metadata slot classifier already excluded confirmed quantity dust
from the position-capacity count, but readiness and execution separately treated
every positive managed quantity as an existing same-symbol position. A nearly
fully sold position could therefore block new BUY signals indefinitely while
remaining too small to SELL. This can obscure strategy evaluation: an operational
entry block is not evidence that the signal engine missed a price move.

Readiness now uses the same confirmed-dust classification for its same-symbol
BUY gate. The executor independently rechecks broker quantity step/minimum before
allowing one new entry over a residual. Positive sellable inventory still blocks
another BUY. Missing/invalid metadata and contradictory/unverified classification
stay blocked. Existing unresolved submission guards run before classification.

The residual balance is retained. A verified new fill adds only its actual quantity
and uses weighted average cost including that residual. The proposal is not enlarged,
and there is no automatic liquidation, top-up, balance deletion or broker order from
classification. Gross exposure and all portfolio/risk checks remain intact.
Minimum-notional-only dust is not a bypass: only confirmed quantity dust qualifies.
After a new sellable position fills, subsequent BUY attempts are blocked normally.

No strategy parameters, indicator thresholds, timeframe, SELL ownership rule,
broker environment or Live execution permissions change. Automation remains paused
until the operator deliberately resumes it after the remaining checks.

## Evidence boundary

The production audit that motivated this change showed an ETH Spot buy followed
by a sell and a tiny remaining quantity, with many later position/dust blocks.
It also contained historical execution errors requiring a separate dated audit.
Their complete causes and correspondence to a specific chart interval are not
established by this patch. Current settings are not reconstructed historical
decision settings. A 4-hour display does not change a configured 5-minute strategy.

This patch does not establish profitable signals, net expectancy, protection,
or successful re-entry on the actual broker. Investigate the dated error groups
and compare frozen-rule signals, readiness blocks and actual fills before making
strategy changes. Do not run the existing fixed-horizon historical scenario
score as if it were a fee/slippage-aware Spot execution backtest.

## Validation and rollout

Regression tests cover confirmed residual re-entry, preserved residual cost and
quantity, unchanged proposal size, blocking the next BUY, real/unverified position
blocks and pending-submission precedence. Existing slot, dust SELL preflight,
cancelled-outcome and pending-order tests remain required.

Run the full isolated production-equivalent Docker validator before merge.
No migration, bridge or frontend change is required. Preserve the current image
as a rollback tag, recreate app only, keep Live disabled and inspect a read-only
readiness result before any separately authorized simulation execution.
