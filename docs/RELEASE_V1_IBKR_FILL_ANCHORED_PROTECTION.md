# IBKR Paper protection anchored to verified fills

NVDA entry 457 filled 197 shares at 224.68. Its original preflight stop/target
225.10205/235.3859 were based on planned reference 228.53 (saved 2R settings).
The stop was above the filled entry and broker average cost 224.68507915.
The bridge returned 400 PROTECTION_LEVELS_DO_NOT_BRACKET_ENTRY before mutation;
the original saved intent remained SUBMITTING. This failure predates the
completed-candle deployment. Delayed market-data warnings were observed, but
this audit does not prove what caused the price difference.

## Prevention

Preflight now preserves reference_price with the immutable planned levels.
Before a first native pair submission, the manager requires persisted exact
full-fill status/order identity/quantity and a positive average fill price.
It carries planned absolute stop and target distances to that fill. Neither
quantity nor intended risk distance increases; the existing conservative
tick rounding still applies at the bridge. The original request is retained.
Computed levels and their inputs are saved separately as
native_protection_levels before SUBMITTING is committed.

Historical references may be reconstructed only from the original stop/target
and saved positive target-RR snapshot. Current configuration is never used.
Missing evidence blocks protection rather than inventing a fill/reference.
Existing protected, pending and unknown intents do not automatically re-anchor
or gain permission to submit new orders. Known bridge rejection codes become
visible in saved outcomes without copying arbitrary error payloads.

## Explicit recovery of rejected original geometry

`recover_rejected_levels(db, entry, apply=False)` is a preview-only default.
It locks and rechecks the current Paper entry/profile and requires:

- Exact full-fill evidence and original levels invalid against that fill.
- SUBMITTING with the exact entry group, no known pair IDs/orders or revised levels.
- The latest saved entry, no pending exit, and a connected simulation bridge.
- Exact live USD-stock position quantity/direction and average cost within
  max(0.01, 0.01% of fill) of the execution price, allowing a small commission difference.
- Original geometry invalid against that broker cost as well; no active symbol orders.
- No other executions since the entry; ambiguous execution times or non-UTC
  execution configuration block recovery.
- Exact 400 rejection of an allow_submit=False check using the original levels.

The proof relies on the bridge's bracket validation occurring before any order
submission, and unchanged full-fill/position geometry. It is not a generic
timeout recovery: otherwise valid original levels, known IDs, partial fills,
changed positions or conflicting executions must be reconciled separately.
It never clears an arbitrary unresolved order or resets the bridge duplicate set.

With explicit apply=True, the original intent is archived, derived levels are
saved and a pre-submission-blocked state permits the normal guarded protection
path. Existing broker checks, same entry/OCA key, what-if validation, position
rechecks, duplicate protection and post-submission reconciliation remain active.
If the outcome is pending, stop and verify that same pair; do not reset/reapply.
NVDA's modeled levels are 221.25205/231.5359, rounded toward entry to 221.26/231.53.

## Validation and rollout

Tests cover exact NVDA distances, short positions, invalid fill/order/quantity/
reference evidence, pre-send persistence, preview without DB/order mutation,
explicit recovery audit preservation, and refusal of existing orders/IDs,
changed costs/positions, later or ambiguous executions and non-current entries.
Existing timeout/pair-ID/native lifecycle regressions remain authoritative.
Full production-equivalent tests precede merge. Deploy only app with a versioned
rollback image; this change requires no bridge, Gateway or schema update.
Run the live read-only preview before applying the specifically reviewed Paper
recovery, then verify both broker-held legs against the current position.
The candle-evidence persistence correction is included in this branch.
