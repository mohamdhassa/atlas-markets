# IBKR fractional Paper execution

ATLAS supports risk-sized fractional US stock and ETF orders only when the IBKR **Paper** API route
has been explicitly certified and `IBKR_FRACTIONAL_API_ENABLED=true`. The production flag defaults
to `false`. Live-money IBKR execution remains locked.

The Oracle Paper bridge returned IBKR error `10243` for fractional API orders on 2026-10-03. ATLAS
therefore sizes new entries down to whole shares when fractional capability is disabled. Stale
fractional requests are blocked locally as `IBKR_FRACTIONAL_API_UNSUPPORTED`. Whole-share orders remain eligible when they fit all
capital, portfolio and risk limits. ATLAS never rounds a fractional request up to one share.

## Safety sequence

1. Size against broker equity or the optional configured simulation capital override.
2. Round down to whole shares when fractional capability is disabled, or 0.0001 shares when enabled.
   A result below one whole share remains blocked; never round up.
3. Require an active, connected IBKR Paper profile and simulation bridge.
4. Reject a symbol with an existing position, open order or concurrent execution reservation.
5. Reject any stale fractional request when capability is disabled; preserve exact approved quantity.
6. Submit an eligible quantity to broker-native What-If.
7. Place only when What-If reports `ok`, `what_if` and `simulation`.
8. Persist the exact quantity and broker order ID, then reconcile the fill.
9. Position exits re-read broker state and close the exact current quantity.

IBKR rejection never causes ATLAS to round up to one whole share.

## Controlled certification

Enable the flag only after this command passes during regular US market hours against Paper:

```bash
IBKR_CERTIFICATION_QUANTITY=0.01 python -m app.scripts.certify_ibkr_execution
```

The command refuses non-Paper sessions, checks account identity, chooses an unused liquid ETF,
performs broker preflight, buys the fractional quantity, confirms order/execution/position state,
then sells the exact quantity and verifies the original position baseline was restored.

## Scaling

With the capability flag disabled, whole-share orders may still execute, but only when one whole
share fits the configured capital and per-trade risk budget. A USD 100 allocation cannot trade
high-priced symbols through this IBKR route unless fractional API capability is later certified.
