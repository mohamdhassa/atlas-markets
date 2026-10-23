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

## Layout correction after deployment

The deployed screenshot exposed inline metric text and unstyled date inputs.
Scope explicit stacked metric typography, three equal-width cards, dark date
fields, and a compact Reset button to the profit page. Filters use a five-column
desktop grid and two-column narrow layout; cards stack on phones. Preserve all
data calculations, filter actions and trading settings. Cache version is 72.2.

## Phone sizing correction

Remove the 560px minimum plot width. Draw the SVG using the chart container's
actual width, keep a 300px mobile viewBox height and show only endpoint date
labels on narrow plots. Pointer inspection uses the actual SVG coordinates.
ResizeObserver redraws when width changes without another provider request.
Mobile summaries use one full-width P&L card and two compact supporting cards.
Date fields stack below 400px and use 16px input text; checkboxes remain 18px
inside 44px touch rows. Asset version 72.3. No calculation or trading changes.
Actual phone visual verification remains pending; automated geometry checks cover
260, 288, 326, 366, 650 and 1000 pixel chart containers.

## Safari date field containment

An iPhone screenshot showed the two native date controls overlapping above the
400px breakpoint. Stack both date labels across the entire grid up to 650px,
retain side-by-side action buttons, and constrain native date controls in both
physical and logical dimensions to their container with a 46px height.
Normalize WebKit date editing appearance without replacing the native date
picker or changing filter values. Cache version 72.4. iPhone visual acceptance
still requires the deployed screenshot; Node tests do not emulate Safari.

## Performance identifiers: What changed

Charts now includes a read-only insights section following the same symbol/date
filters, owner scope and available priced records as the graph. Show the highest
daily cumulative realized P&L (including the zero baseline), current distance
below that peak, largest daily closing peak-to-trough drop and worst UTC day.
Do not calculate an account-equity drawdown percentage from realized P&L.

Show up to five negative net symbol contributions after the peak day, plus the
five largest negative P&L records in the selected period with UTC dates and
provider/environment labels. Aggregate partial fills for symbol contributions;
label individual records as records rather than whole trades. Since-peak
attribution begins after the peak UTC day, so intraday giveback is not inferred.
These are outcomes, not evidence of strategy/stop failure. Partial coverage and
unknown values retain existing disclosures. Empty/loading/error states clear
stale insights. No orders, settings, migration or additional provider calls.
Asset version 72.5. Desktop/mobile visual acceptance remains pending deployment.

## Wins alongside loss identifiers

Add a matching Wins section using the same known, dated, filtered realized P&L
records: best net UTC day, count and summed P&L of positive records, largest
positive record, top five net-positive symbol contributors and top five winning
records. Winning-record P&L is explicitly before subtracting losing records,
not total profit or a new fee calculation. Partial fills remain records rather
than trades; no whole-trade win rate is inferred. Symbols are ranked by their
net period outcome, so an individual winner can belong to a net-losing symbol.
Keep provider/environment labels, dates, partial/empty/error disclosures and
the existing mobile grids. No extra provider calls, orders, settings or schema
changes. Asset version 72.6. Container and visual acceptance remain pending.

The final layout combines both outcomes in one Performance breakdown section.
Wins and Losses use matching cards/lists side by side on desktop and stack below
900px. Both symbol lists use net selected-period contributions. Keep after-peak
loss attribution in a disclosure below them. Add count and sum of losing records
so positive-record P&L plus negative-record P&L reconciles with the period total.
