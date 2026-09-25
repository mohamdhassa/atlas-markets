# ATLAS MARKETS — User and Administrator Guide

## Roles

- `ADMIN`: user management, integrations, automation controls, strategy configuration, certification/readiness and all permitted operational views.
- `USER`: only owned profiles, strategies, portfolio, reports and analysis.

## Daily operator flow

1. Check Dashboard health and dependency state.
2. Open Integrations and confirm required provider profiles are connected and active.
3. Check Operations for kill-switch state, last scan, next scan and provider blockers.
4. Review Portfolio positions, orders/fills, realized P&L and unrealized P&L.
5. Review Strategy shadow coverage and settled performance.
6. Investigate skips/errors before changing parameters.
7. Use broker-native portals as the final source of truth.

## Strategy workspace

Each symbol is configured independently with provider account, market, mode, timeframe and optional parameter overrides. Defaults remain visible when no override is set.

The Shadow Intelligence panel shows:

- configured and active strategies by provider;
- observed, skipped and error counts;
- last action, confidence and regime;
- settled sample size and win rate;
- net expectancy, profit factor and drawdown;
- validation blockers and skipped-symbol reasons.

`VALIDATING` is normal until at least 30 directional observations settle and all statistical gates pass. `ELIGIBLE` does not automatically enable execution.

## Portfolio interpretation

- Open Positions: current broker-native exposure.
- Orders/fills: broker activity and ATLAS lineage when available.
- Realized P&L: closed broker results after available fees/commissions.
- Unrealized P&L: current mark-to-market result.
- Shadow result: hypothetical forward observation; never mix it with broker P&L.

## Integration administration

Credentials are entered or replaced but never displayed again. After changes, use Test Connection, Sync and readiness diagnostics. Activate only one intended profile per relevant provider/environment scope.

## Automation controls

- Kill stops new automated submissions; it does not automatically liquidate positions.
- Restart resumes only after operator review.
- Scan Now requests analysis; safety gates remain active.
- AUTO_TRADE means eligible for preflight, not guaranteed execution.

## Frontend troubleshooting

- Use `Ctrl+F5` after deployment to refresh versioned browser assets.
- Confirm `/health` before treating a page failure as a backend outage.
- A `401` indicates an expired/missing session; sign in again.
- Use the expandable provider diagnostics in Strategy before assuming Bybit or IBKR was omitted.
- Mobile tables scroll horizontally; sticky headers retain column context.
