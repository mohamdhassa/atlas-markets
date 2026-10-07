# Bybit quantity dust preflight

After slot classification, a SELL signal for XRP quantity dust still reached execution
and failed with SPOT_QUANTITY_BELOW_MINIMUM. Preflight now blocks a SELL whose own symbol
is in readiness's broker-confirmed quantity dust list as BYBIT_MANAGED_QUANTITY_DUST.
It preserves SELL direction, quantity and slot evidence in the audit. No submission
is attempted. Another symbol's dust, unknown metadata or BUY does not trigger this rule;
the other readiness, ownership, certification and duplicate guards still apply.

This uses the bounded metadata evaluation from the same readiness request, not a stale
persisted classification. No inventory deletion, liquidation, top-up, sizing increase,
schema, frontend, budget or bridge changes. Minimum-notional-only dust and exit protection
remain separate checks. Build/test the app, preserve its current image, recreate app only,
and verify a new scan reports the explicit preflight block without EXECUTION_ATTEMPT for
that dust SELL. Roll back to the preserved image if application health fails.
