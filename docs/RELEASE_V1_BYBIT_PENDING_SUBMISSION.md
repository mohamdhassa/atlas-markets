# Bybit unresolved submission guard

A Spot order accepted by the broker can remain SUBMITTED when its fill is not
confirmed. Repeated scans formerly generated another random order link when no
managed inventory had yet been credited. Execution now blocks either direction
as BYBIT_SUBMISSION_RECONCILIATION_REQUIRED if a persisted SUBMITTED action exists
for the same user, broker profile, BYBIT environment and canonical symbol.
The outcome records the pending action ID and broker order ID when available.
No age-based expiry or missing-ID exception clears this guard.

If an accepted order's fill-history read raises, retain SUBMITTED, its accepted
broker response and order link/order ID, and record only the exception class.
Do not retry placement or credit inventory without broker evidence. Existing
inventory, actions, budgets, certification and Live Money gates are unchanged.

Tests use a real SQLAlchemy session to verify both directions, account/user/
environment/symbol isolation, resolved statuses, old and missing-ID records,
repeat scans, accepted-read failures and a new session after persistence.
Run the full production container suite before activating the app.

No schema, bridge or frontend changes. Preserve the current app image; build,
test and recreate app only. Verify health, Alembic head, logs and a monitored
scan. Existing unresolved submissions should block rather than create another
order. Roll back using the preserved image if app health fails.

## Reconciliation and limits

An absent open order does not prove a fill or cancellation. Reconcile each pending
order by its exact broker order/link ID and executions before changing its status
or managed inventory. This release does not automatically resolve old records.
Another symbol/profile can continue through existing safety gates.

This guard covers persisted submissions. It does not serialize simultaneous workers
or close the crash window between broker acceptance and action persistence. An
ambiguous placement timeout still requires durable intent/idempotency work; never
blindly retry. Partial-fill lifecycle, protective stops and IBKR exit protection
remain separate acceptance work. Do not infer full unattended or live readiness.
