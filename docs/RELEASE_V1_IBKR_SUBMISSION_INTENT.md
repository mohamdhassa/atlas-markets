# IBKR durable submission intent and fresh authorization

## Problem and behavior

Previously an entry POST timeout before an order ID reached the app became a generic
BLOCK result. A later scan could try again after the broker forgot the first order.
The scan also cached engine authorization before slow market-data/preflight reads.

The scheduled and ADMIN-triggered safe scanner now locks the configured BrokerProfile
row, checks owner/profile/symbol-scoped SUBMITTED and EXIT_SUBMITTED audits, re-reads
engine and route controls, and commits one SUBMITTED action before entering IBKR entry
execution. Existing unresolved entries block another attempt. Database write failure
prevents execution. The final result updates that same action, retaining the original
submission intent, rather than inserting a second trade.

A timeout, unknown exception or worker cancellation leaves the committed intent
unresolved. Only the exception class is retained; arbitrary provider URLs/error text
are not copied. An ambiguous response is SUBMITTED, not a proved rejection. Explicit
accepted=false without an order ID is a rejection. Partial or unknown fills with a
cancelled remainder remain SUBMITTED; only a broker-reported zero-fill cancellation
clears the attempt. Exact complete fills still use existing verification.

The app refreshes engine enablement, kill state, simulation execution, profile
readiness/ownership/environment and strategy mode after preflight. The bridge client
also invokes the check after its own position/order reads immediately before POST.
A typed local pre-submission block can close the intent without claiming submission.
There is no atomic transaction between the database and broker, and this cannot
recall a request already sent. No claim of guaranteed exactly-once broker execution.

The row lock/pending guard covers workers using the same BrokerProfile. It does not
certify multiple profiles representing the same broker account; existing deployment
still assumes one automation process and one active configured account route.

## Reconciliation and limits

When a saved broker order ID exists, ordinary exact execution or strict position
fallback reconciliation can include the new unresolved-submission reason. Retained
priced executions continue to be required for initial fill-anchored protection.
Without a saved order ID, empty positions/orders/history never release the intent.
Such a submission needs exact broker evidence and a separately reviewed recovery;
this release does not auto-reset an unknown outcome or fabricate an order mapping.

Partial entries remain blocked for initial full-entry protection and require review.
Existing older BLOCK audits from historical timeouts are not automatically rewritten.
The fresh submission callback applies to this IBKR safe entry path; it does not certify
MT5/Bybit or change their entry lifecycles. Live Money remains disabled/uncertified.
No migration, strategy, bridge server or Gateway change is included.

## Validation and rollout

Local Python 3.12 validation: **790 passed, 4 skipped**, with PostgreSQL/Redis absent.
Shell syntax, CI YAML parsing and whitespace checks passed. These results do not
replace the actual container, clean migration or broker/runtime acceptance checks.

Regressions cover durable intent before execution, database failure, timeout/unknown
failure, cancellation, no subsequent retry, one action per scan attempt, explicit
pre-send blocks, changed engine/route controls, client-side kill changes during reads,
ambiguous acceptance and cancelled partial/unknown fills.

`ops/validate_release_candidate.sh` validates one full Git SHA in disposable containers.
It archives tracked source only, builds the production Dockerfile, creates PostgreSQL
17 and Redis 7 on a private internal Docker network, runs clean migrations and the full
suite, rejects skipped tests, disables automation in the disposable database, and
smokes app health/system policy. It uses generated test credentials and never reads
`.env.oracle`, publishes ports, mounts production data or restarts production services.
Cleanup targets only container IDs and network/image created by that run.

Runner tests use fake Docker/Git commands to exercise successful orchestration,
migration failure cleanup and rejection of an unpinned ref. They do not establish that
the actual image or migrations pass. CI invokes the same runner. An unavailable or
billing-blocked Actions job is not a pass; run it on a Docker host instead.

After the full candidate container check passes and the PR is merged, deploy only app
with the recorded rollback image and existing protection override. Verify pending
audits, exact broker state and one monitored reconciliation. No forced trade, broker
restart or cancellation is part of validation or rollback.
