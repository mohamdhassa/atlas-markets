# Strategy execution evidence

Readiness already selected an advisory strategy route, but preflight discarded
it before the automation action was saved. New scans now carry that exact route,
signal decision, strength, classification and resolved settings into the existing
`automation_actions.raw_json.preflight` audit for passing and blocked outcomes.

`strategy_snapshot` records the configuration/profile IDs, market, symbol, mode,
shared signal engine, router role (`ENTRY_FILTER`) and effective timeframe,
minimum strength, risk percentage, ATR stop multiplier, target risk/reward and
position-notional percentage. These are values used during the scan, including
global risk caps and symbol overrides, rather than the later current settings.
The snapshot schema is version 1; it is not a code revision or strategy revision.

The route describes an entry filter around the common signal engine. It does not
establish that independent trend, Darvas or mean-reversion executors ran, that a
confidence score is a calibrated probability, or that news influenced a trade.

Historical entries without this evidence remain unattributed to a route; no
backfill from current configuration is performed. Closed-trade evaluations must
link to the entry action, group partial fills by closing order/entry, separate
providers and environments, and retain broker-authoritative net P&L. Snapshot
coverage alone is not a performance evaluation or live-money eligibility test.

No schema migration or trading-policy change is required. Existing certification,
ownership, risk, live-money, duplicate-order and native-protection checks remain
in force. Validate in the full production-equivalent container suite before merge.
After deployment, inspect new actions for both `preflight.strategy_route` and
`preflight.strategy_snapshot`; older rows are expected to have neither.
