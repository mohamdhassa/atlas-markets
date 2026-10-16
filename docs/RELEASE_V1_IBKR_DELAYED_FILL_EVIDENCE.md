# Durable delayed-entry fill evidence

## Problem and resulting behavior

An entry could be marked EXECUTED by delayed execution reconciliation or an exact
current-position fallback while its original result still correctly said SUBMITTED.
Fill-anchored protection and durable ledger recovery only understood the original
Filled status response. A delayed entry therefore lacked a usable fill price even
when the manager had received the actual broker executions.

The manager now saves `entry_execution_evidence` separately from the immutable
submission response. Full execution reconciliation requires priced stock callbacks,
exact account/order/symbol/direction, positive finite quantities and prices, unique
execution IDs and exact aggregate entry quantity. Duplicate identical callbacks count
once; contradictory identities block. Execution times must fall between five minutes
before the saved entry and five minutes after the current clock, using the declared
Gateway execution timezone. This guards against old reused order IDs; it is not a
substitute for broker identity/position checks.

Protection revalidates these saved callbacks before preserving the planned absolute
stop/target distances at their quantity-weighted execution price. The regular
broker-held protection guards and persisted pair intent remain unchanged. Existing
position-reconciled entries can acquire this evidence when the manager can still read
their full executions. Empty or invalid later history never erases retained proof.

The ledger can recover the priced entry after a bridge restart, using the latest
constituent execution time and explicit provenance. It does not invent commissions,
realized P&L or a Filled status response. Reviewed statement evidence retains precedence.
The manager also ignores current positions belonging to another or unknown account.

## Limits

The TSLA order 491 output alone does not prove the actual fill. If the bridge no longer
returns its executions and no verified full-fill response was saved, this release
cannot reconstruct the price. Position average cost is not substituted. Such entries
remain explicitly blocked for initial fill-anchored protection and require separately
verified broker evidence. No production row is manually relabelled by this release.

Partial entries do not gain new protection-submission authority. Existing pending,
protected or uncertain protective pairs are not replaced or re-anchored. No live
execution route, risk policy, data entitlement, strategy or database migration changes.
Source migration head remains `20261010_0023`; the deployed head must be checked.

## Verification and rollout

Regression coverage includes a delayed 128-share TSLA entry with two fills, retained
protection and ledger recovery, repeated protection verification without resubmission,
position-only refusal, partial/duplicate/overfilled/conflicting evidence, invalid
prices, stale/future timestamps, wrong accounts, short/fractional quantities and
other-account lifecycle isolation.

The local Python 3.12 suite passed: **761 passed, 4 skipped**. The skipped checks need
PostgreSQL/Redis. Local execution is not production-equivalent container acceptance.

CI now invokes `ops/validate_release_candidate.sh`: it builds the production Dockerfile,
upgrades isolated PostgreSQL to Alembic head, runs the full suite with bridge source and
integration settings, rejects skipped tests and smokes the isolated app. CI and runtime
acceptance are pending until their actual results are recorded.

Before merge, run that candidate container suite. After merge, record the current
production commit/image and retain a versioned rollback image. Deploy only `app`,
retaining the existing native-protection compose override. This change needs no bridge
or Gateway restart. Verify app health, deployed Alembic head, persisted evidence,
actual position and both protective quantities/statuses after one manager cycle.
Do not force another entry or recreate outstanding orders to obtain a passing check.
Rollback restores the recorded app image while retaining broker orders and audit JSON.
