# Portfolio single render

Portfolio used a chain of render wrappers and delayed callbacks to add its universe, terminal,
section cleanup, market-monitor table/cards and position-chart upgrades. Intermediate layouts
were visible while these operations completed, with repeated calls for the same provider data.

A final coordinator now bypasses that chain for Portfolio, invokes the existing final components
once in a deterministic order, and shares read-only responses within the assembly. It skips the
superseded market-monitor table and keeps the final cards, terminal, live holdings charts and
activity panel. Existing templates, CSS, responsive rules, controls and data sources are preserved.
A loading status is shown while the composition has visibility hidden (not display none), so
canvas dimensions remain measurable. The finished layout is revealed together.

Per-open data sharing expires when the assembly completes. Mutations are never cached. Navigating
away restores visibility and API ownership immediately; pending base-render writes are ignored.
Other pages retain their renderers. Live chart refresh resumes after initial composition.

Validation covers component order/count, shared reads, subsequent opens, navigation races, error
states, mutation bypass and asset order. Existing portfolio/candle/responsive tests remain applicable.
No backend, provider, trading, budget, schema or stylesheet change is introduced. Deploy only the
application after the full container suite; preserve the previous image for rollback. Verify the
final layout on desktop and phone, symbol/timeframe selection, Performance navigation and live
refresh. IBKR bridge and Gateway do not require restarting for this frontend-only change.
