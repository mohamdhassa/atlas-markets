# Strategy evaluation report

Performance now includes a read-only strategy evaluation table backed by
`strategy_evaluation` in the authenticated `/performance/broker-native` response.
It reuses the existing provider read rather than adding another broker request.
The report evaluates IBKR broker-confirmed net P&L. Bybit Spot's current
reconstructed finance is excluded from these metrics; provider balances and the
existing trade ledger remain available separately.

Entry attribution requires an exact scoped entry-action link from complete FIFO
lots or native-protective evidence, a matching closing action, the same owner,
profile, provider, environment, market and asset, opposite entry/exit sides, and
the entry's recorded schema-1 strategy snapshot and route. A closing action's
current route, a nearby audit timestamp or today's symbol configuration cannot
replace missing entry evidence. Multiple entry lots remain strategy unknown.

Cohorts separate account, environment, asset, entry side and recorded snapshot.
Partial callbacks count once per closing order. Duplicate execution identities
are deduplicated; conflicting executions, aggregate/fragment mixtures, incomplete
audited closing quantities and pending finance are excluded. Known closing
orders report net P&L, expectancy, average win/loss, win rate, profit factor and
maximum cumulative realized-P&L drawdown in dollars. Net P&L is not reduced by
commissions again. No-loss profit factor and equity drawdown percentage remain
unknown rather than displaying artificial values.

Historical closed orders without entry snapshots appear as `STRATEGY_UNKNOWN`.
New attributed cohorts stay `VALIDATING`, even when profitable. This report has
no live-eligibility assessment and does not replace walk-forward tests, forward
observation, equity drawdown measurement or operational promotion checks.

The evaluation window applies to closing timestamps before display truncation.
Provider errors and exclusions are shown as coverage limitations. The existing
closed ledger, news context, navigation and trade policies are preserved. The
table uses the existing horizontal-scroll container on mobile.

No schema migration, provider execution change, Gateway restart or backfill is
required. Deployment requires the full container suite and app-only rollout
with rollback and native-protection checks. Refresh Performance after deployment;
unknown cohorts are expected until entries with saved route evidence close.

## Account environment correction

Every execution row now retains the environment from its accessible broker
profile, even when no matching closing audit or entry snapshot exists. Missing
strategy evidence must not split one Paper account into PAPER and UNKNOWN
environment cohorts. An audit with a conflicting environment cannot override
the profile scope. This correction changes grouping only, not broker P&L.
