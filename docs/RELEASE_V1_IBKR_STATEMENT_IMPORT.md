# IBKR Paper Activity Flex import

Add an ADMIN-only preview/apply endpoint and server operator CLI for downloaded Activity Flex
XML execution reports. Explicit reviewed mappings store normalized evidence independently alongside verified saved
ATLAS fills; complete quantity, price, identity, account, environment and execution-time checks
prevent unmatched imports. Repeat imports deduplicate and conflicting evidence stops for review.

Performance replaces same-order live fragments/fallback rows with verified statement aggregates,
showing actual execution times, closing-order commissions and broker FIFO realized P&L without
subtracting commissions twice. Missing P&L stays pending, and opening trades are excluded from
closed-trade win/loss calculations. Dates read without a timezone from UTC audit storage now
explicitly use UTC, independent of server local timezone.

Read [IBKR statement import](IBKR_STATEMENT_IMPORT.md) for export fields, preview/mapping/apply,
unsupported cases, privacy, ownership, database backup/rollback and deployment guidance.
Migration `20261010_0023` adds an isolated evidence table; no bridge change; native protection activation remains explicit and retained.
This release has fixture-based validation; a real Paper export is required for final reconciliation.
