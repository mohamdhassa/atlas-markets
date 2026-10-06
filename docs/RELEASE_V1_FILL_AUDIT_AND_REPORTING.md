# IBKR fill audit and reporting isolation

## Problem and behavior

An accepted IBKR Paper order could lose its returned order ID from the scan audit
when a subsequent status read failed: the outer execution handler labelled it BLOCK.
Entry verification now returns SUBMITTED / BROKER_FILL_NOT_CONFIRMED on read failure,
retaining the accepted broker response and order ID for existing reconciliation.
Exit verification likewise leaves EXIT_SUBMITTED intact. Only the exception class is
recorded in verification_error, never a connection URL or raw exception text.
No order submission is retried by this change.

A full fill requires finite positive quantity exactly matching the requested quantity,
with finite nonnegative remaining quantity equal to zero. A Filled label alone,
partial fill, overfill or malformed quantities cannot mark an order EXECUTED.
Persist each execution outcome before continuing to another instrument/provider,
so a later scan rollback cannot erase an already recorded order.

Daily reporting formerly called synchronous database work directly on the ASGI event
loop. It now runs in a thread, with its own existing session. Web requests remain
responsive while that report is blocked. The report loop waits for completion before
starting another report; existing schedule and calculation behavior are unchanged.

## Verification

Regression tests cover exact whole/fractional quantities, partial/overfilled/malformed
broker status, failed status reads, accepted-entry identity retention, later scan
failure preserving a committed order, and a real ASGI request during blocked reporting.
Run the full production-equivalent suite before activation.

No migration, bridge, frontend, capital, certification or Live Money changes.
Preserve the current app image, build/test and recreate app only. Verify health,
Alembic, logs, and one Paper scan/reconciliation after activation. Roll back by retagging
the preserved image as atlas-markets-app:latest and recreating app.

## Limits and remaining acceptance work

This does not resolve every possible application stall or prevent IBKR outages.
Other background jobs still mix synchronous database work with asynchronous requests;
inspect them and collect evidence from any renewed watchdog restart loop.
There remains a process-crash window between broker submission and audit persistence.
An ambiguous placement timeout also needs a durable intent and broker identity workflow;
never blindly retry such an order. Exit submission reconciliation and protective
stop/take-profit behavior require a separate review and controlled Paper certification.
Do not describe the project or real-money readiness as complete based on this patch.

Closeout still requires: provider disconnect/recovery observation; duplicate-entry and
exit protection across restarts; capital/reset-aware performance reconciliation;
Logs pause/history usability; complete desktop/phone route review; backup restore and
rollback drills; and repeated broker-native entry/exit verification on both providers.
