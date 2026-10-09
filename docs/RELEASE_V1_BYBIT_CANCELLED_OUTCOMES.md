# Bybit zero-fill cancellation outcomes

Broker evidence showed four BNB Spot market IOC orders cancelled with cumExecQty=0
and rejectReason=EC_NoImmediateQtyToFill. The fill reader formerly ignored terminal
cancellations and left them SUBMITTED. New accepted orders now become CANCELLED /
BROKER_ZERO_FILL_CANCELLED only after exact order/link, symbol and side agreement
and a finite zero filled quantity. Inventory is neither created nor changed by
that outcome. The broker terminal row and cancellation reason remain in the audit.

Before another order attempt for a symbol with a persisted broker order ID,
re-read pending submissions for that user/profile/environment/symbol. Resolve only
exact broker-confirmed zero-fill cancellations. Preserve original preflight/result
JSON and append cancellation_reconciliation evidence and check time. Missing records,
read errors, malformed audits, partial fills and identity mismatches stay SUBMITTED.
An unresolved older action still blocks placement after newer cancellations resolve.
No automatic placement retry, status expiry, inventory deletion or capital change.

The application function reconcile_cancelled_submissions can also be invoked using
its own SessionLocal session and committed to reconcile without a strategy signal
or submitting an order. It accepts a Bybit TESTNET/DEMO profile, its owning user ID
and symbol; it examines at most 50 matching pending actions per call. Caller owns the
transaction. Database failures propagate for rollback. Exact history queries use
submission time +/- one day and a limit of 50; a missing historical cancellation
can be outside broker retention and is not proof of zero fill.

Tests cover new BUY/SELL cancellation without inventory changes, exact identity,
finite zero quantities, partial/malformed outcomes, failed reads, isolated ownership,
preserved audit, repeat reconciliation, cancellation before the existing position
guard and a missing old order continuing to block. Full container tests are required
before activation. No migration, bridge, frontend, budget or Live Money change.

Preserve the current image; build/test and recreate app only. Verify health, Alembic
head and logs. Run reconciliation without placement for pending BNB, then inspect
the ledger: verified October records should be CANCELLED; the missing September
record must remain SUBMITTED. Verify inventory unchanged. Roll back using the saved
image if health fails; committed broker evidence remains in the ledger.

Remaining limits: partial-fill accounting, old missing-order evidence, worker crash
windows/idempotency and IBKR protective exits require separate acceptance work.
This patch fixes truthful status handling; it cannot supply Testnet liquidity.
