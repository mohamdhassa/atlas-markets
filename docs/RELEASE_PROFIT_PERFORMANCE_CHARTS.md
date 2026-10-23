# Profit performance on Charts

Charts now displays cumulative recorded realized P&L instead of the single-symbol
market-price workspace. Portfolio instrument charts and the Markets page remain
available for market prices. Default filters are empty: one Overall curve over
all available recorded history. No implicit 30-day window or symbol is selected.

The symbol picker supports multiple instruments. Applying a selection draws
one curve per instrument plus their selected total on a shared timeline, with
provider/environment labels distinguishing the same ticker in different routes.
Start and end dates are optional, inclusive UTC calendar days. A selected period
starts at zero and accumulates only outcomes inside it. Reset clears symbols
and both dates, restoring overall/all-time. Pointer inspection and a keyboard-
accessible date slider show exact daily cumulative values. The layout preserves
phone filter controls and a horizontally scrollable graph when needed.

## Data and interpretation

`GET /performance/profit-chart` accepts repeated `symbols` keys (at most 50),
optional `start` and optional `end` dates. Invalid dates/ranges fail before broker
requests. User authentication and existing ADMIN/USER profile scope remain in
force. Live IBKR execution callbacks must additionally match the profile's
configured broker account. Saved IBKR fill/statement reconciliation uses the
existing ownership/account validation.

The chart consumes the existing broker-native ledger before its 200-row display
limit and before editorial/news context queries. Daily values include known
recorded P&L only. Unknown/nonfinite P&L, undated records and provider failures
are explicit exclusions. No priced records produces an empty state, not invented
zero profit. A symbol without priced records in the chosen period is identified.
Confirmed zero P&L remains a valid flat curve. Same-day outcomes are summed;
all comparison curves share the same date grid. Deposit/withdrawal, broker account
equity, paper reset balances and unrealized positions are not plotted as profit.

“All available” means the available broker response plus retained ledger evidence,
not a claim to recover missing broker history. Broker APIs retain their existing
limits (including finite execution/history windows); saved actions/evidence are
not clipped by a new chart time window. The UI discloses history limitations.
The endpoint uses up to 366 requested broker-history days while retaining all
saved reconciled evidence. Filters apply after execution-lot pairing.

Fee treatment follows the existing ledger, including existing provider-specific
limitations; no new net-after-fees computation is asserted. USD/USDT use the
existing reporting units without FX conversion. The title explicitly identifies
recorded realized P&L. Existing Performance reports and their calculations are
unchanged. This release changes no orders, strategy or account settings.

## Validation and deployment

Tests cover full-record accumulation beyond 200 rows, multiple-symbol totals,
UTC boundaries and period rebasing, unknown versus zero, missing dates, scope,
foreign-account callback exclusion, query validation, frontend filters/reset,
empty/error states, tooltip/slider values, escaping and stale navigation responses.
Run the full isolated production-equivalent suite before merge. Deploy app only
with a rollback image, preserving both IBKR native-protection and delayed-data
compose overlays. No migration or Gateway/bridge restart is needed.

After deployment, verify desktop/phone layout, all-time initial render, two-symbol
comparison, date filtering/reset and navigation alongside Portfolio, Performance
and Markets. Browser visual checks remain pending until the app candidate is
available; local interaction tests do not claim production visual verification.
