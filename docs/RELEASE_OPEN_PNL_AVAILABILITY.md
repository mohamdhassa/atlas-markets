# Preserve unknown open P&L

The portfolio endpoint previously emitted zero open P&L for Bybit managed Spot
inventory and IBKR positions even though position-level P&L and marks were
unavailable. Dashboard then displayed an unsupported $0.00.

Accounts with these holdings now return null open P&L. Confirmed flat accounts
return zero. MT5 position P&L must be present and finite for every position before
its account total is reported. Combined open P&L is null whenever any provider
read fails or any included account lacks complete P&L. The totals object exposes
`unrealized_pnl_complete`; equity and buying-power availability remain independent.
No known provider subtotal is presented as a complete open P&L total.

Dashboard already renders null as an em dash. Its holdings caption now explicitly
labels unavailable P&L, and otherwise notes that holdings may include residual
balances. A holdings count is not a count of sellable positions or risk slots.
This change retains all inventory and quantities. It does not classify every small
balance as quantity dust without broker metadata, liquidate it, or alter execution.
Portfolio's separate market-mark estimate remains an estimate and is unchanged.
Realized P&L and win-rate calculations are unchanged and require separate review.

Regression coverage includes unknown versus true zero, mixed known/unknown values,
nonfinite values, provider outages, and actual JavaScript rendering. Full isolated
container validation is required before merge/deployment. No migration or bridge
change is needed. Deploy app only with a rollback image; keep automation paused
and Live disabled. Verify Dashboard/Portfolio, mobile/desktop, navigation and the
read-only portfolio totals after deployment. Do not infer strategy profitability
from this reporting correction.
