# IBKR ledger history after bridge restarts

Performance previously depended entirely on `/executions` for IBKR. An empty Gateway execution
response removed previous closed trades from the ledger, despite committed fill-status audits.

The report now reads accessible profile/owner/environment scoped EXECUTED and EXIT_EXECUTED
records and recovers only exact order IDs with full Filled status, positive finite average fill
price, zero remaining quantity and the audited quantity. Status alone, submitted orders, position
average cost and broker What-If commission estimates are not fill/P&L evidence.

Live execution rows take precedence over a saved order aggregate, preventing double counting.
FIFO entry context now includes verified closing fills whose P&L is pending. Saved closed exits
remain visible with P&L pending; they do not contribute zero-valued trades to win rate or net P&L.
Orders are attributed within their profile, preventing same-ID cross-profile attribution.

Recovered timestamps are audit recording times, not exact execution times. Durations from these
rows are approximate. Missing fills, fees and realized P&L are not reconstructed or estimated.
Historical broker statements/Flex data are still needed for complete net P&L recovery. This change
uses existing PostgreSQL audit records at read time and does not write data or change execution,
protection, auth, provider gates, migrations or capital allocations.

Validation covers empty/unavailable bridge history, FIFO long/short closes, ownership and account
mismatches, invalid/partial fills, live-history deduplication and frontend pending display.

Deployment: build and test the app, preserve a rollback image, recreate app with the existing
`ops/docker-compose.ibkr-protection.yml` override, verify health, migration head and the ledger.
Do not restart the IBKR bridge or Gateway for this reporting-only release.
