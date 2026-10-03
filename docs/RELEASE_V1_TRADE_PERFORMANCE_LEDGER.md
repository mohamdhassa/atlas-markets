# v1 trade and performance ledger release

This release consolidates duplicate frontend reporting and adds provider-capital and closed-trade
detail to the authenticated Performance workspace.

Delivered:

- one canonical Users & Access page;
- Portfolio limited to current balances and open positions;
- provider starting capital, realized gain/loss, strategy value and return;
- closed-trade entry, exit, duration, invested amount, fees and return;
- conservative strategy, automation and news context with explicit attribution labels;
- regression coverage for FIFO lot matching and frontend ownership boundaries.

No database migration is required. Provider histories and existing PostgreSQL audit records are
combined at read time. Broker-reported P&L remains authoritative.
