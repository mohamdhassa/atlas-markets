# IBKR live execution timestamp and side reporting

Performance now accepts IBKR execution timestamps such as `20261012  13:30:18`,
normalizing whitespace and using an explicit timezone instead of the host timezone.
`IBKR_EXECUTION_TIMEZONE` declares the Gateway timezone for callbacks without a zone;
it defaults to `Etc/UTC`, matching the production IBC configuration. Operators using another
Gateway timezone must set this reporting option to the matching IANA zone. Explicit ISO
or IBKR timezone suffixes take precedence; the hyphen UTC format remains UTC.
Unknown, ambiguous and nonexistent local timestamps remain unavailable.

Live IBKR sides BOT/SLD display as BUY/SELL. The normalized timestamps allow chronological
entry matching, close timestamps, durations and daily P&L for protective split fills.
Execution IDs and separate fills are retained; broker P&L and commissions are unchanged.
This reporting-only change does not alter orders, protection, strategy, authentication,
statement evidence, database migration head or frontend layout.

Validation covers the observed two META protective fills, explicit/non-UTC timezone formats,
invalid/DST times, side normalization, chronological lot context and unchanged net P&L.
Deploy only app with the existing native-protection overlay; do not restart Gateway or bridge.

Remaining historical evidence: September 3–9 Activity Flex execution detail is needed for
three older closes. October 1 bookkeeping adjustments remain unsupported and require
separate broker execution evidence; no synthetic P&L or fill audit correction is applied.
