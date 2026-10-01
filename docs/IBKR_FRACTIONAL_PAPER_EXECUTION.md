# IBKR fractional Paper execution

ATLAS supports risk-sized fractional US stock and ETF orders on the IBKR **Paper** route. Live-money
IBKR execution remains locked.

## Safety sequence

1. Size against the configured account capital basis (currently USD 100 in production).
2. Round share quantity down to 0.0001 so the risk budget is never exceeded.
3. Require an active, connected IBKR Paper profile and simulation bridge.
4. Reject a symbol with an existing position, open order or concurrent execution reservation.
5. Submit the exact fractional quantity to broker-native What-If.
6. Place only when What-If reports `ok`, `what_if` and `simulation`.
7. Persist the exact quantity and broker order ID, then reconcile the fractional fill.
8. Position exits re-read broker state and close the exact current fractional quantity.

IBKR rejection never causes ATLAS to round up to one whole share.

## Controlled certification

Run only during regular US market hours against Paper:

```bash
IBKR_CERTIFICATION_QUANTITY=0.01 python -m app.scripts.certify_ibkr_execution
```

The command refuses non-Paper sessions, checks account identity, chooses an unused liquid ETF,
performs broker preflight, buys the fractional quantity, confirms order/execution/position state,
then sells the exact quantity and verifies the original position baseline was restored.

## Scaling

The implementation has no one-share application cap. Increasing the account capital override or
eventually using broker equity changes risk sizing without changing order code. Portfolio exposure,
available balance, strategy risk, and broker checks remain the limits.
