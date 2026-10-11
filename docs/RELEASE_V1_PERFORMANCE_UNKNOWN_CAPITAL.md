# Performance with unknown starting capital

When any reported provider has no configured starting allocation, the combined starting
capital and strategy value now remain null, displayed as `—` by the existing Performance
renderer. Empty reports and provider read failures also leave these totals unavailable.
A configured zero remains zero. When all allocations are known, combined strategy value
continues to equal starting capital plus verified realized P&L.

Verified realized P&L, broker equity, individual provider values and ledger evidence remain
independent of missing allocations. No page layout, configuration, broker orders or database
migration changes are required. Incomplete historical fees and P&L remain pending until
reviewed broker evidence is supplied; this change does not estimate missing history.

Validation covers missing, mixed, empty, complete, explicit-zero and provider-failure reports.
