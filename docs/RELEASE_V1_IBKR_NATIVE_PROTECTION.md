# IBKR Paper broker-held position protection

## Scope and activation

`IBKR_NATIVE_PROTECTION_ENABLED` defaults to false. When explicitly enabled, a filled,
committed IBKR Paper entry is immediately offered broker-held protection. The position
manager also checks existing, verified ATLAS-owned positions using their original saved
preflight stop-loss and take-profit values. It does not derive fresh levels from delayed
quotes or historical bars. The frontend, budgets, provider certification and Live Money
gates are unchanged. Migration head remains `20261001_0022`.

An updated bridge advertises `native_protection_available=true`. With the flag enabled,
new IBKR entries require that capability, valid risk levels, and confirmed native coverage
of existing broker positions. Failure to protect a filled position blocks further entries
while that position lacks coverage; a filled entry is never relabelled unfilled.

## Broker execution

The bridge accepts `/protection` only on its configured Paper account. It re-reads exact
account/symbol/side/quantity, resolves the USD stock contract, and rounds levels toward
the entry using the reported minimum tick. Levels must still bracket broker average cost.
The close direction is SELL for LONG and BUY for SHORT. A broker What-If close must pass,
then positions and all clients' open orders are re-read before submission.

Two GTC orders, STP and LMT, share a deterministic entry UUID reference and OCA group.
OCA type 2 reduces remaining orders proportionately with broker overfill blocking when
one partially fills. The stop is staged with transmit=false, then the limit is submitted
with transmit=true to transmit the group. Both use outsideRth=false: this release provides
regular-session protection, not an overnight stop guarantee. Stop execution prices are
not guaranteed. A stop can reject or slip; Paper fills do not certify Live behavior.

See the primary IBKR references:
- https://interactivebrokers.github.io/tws-api/oca.html
- https://ibkrcampus.com/docs/tws-api/ref/order

Only an exact broker-reported pair in Submitted/PreSubmitted state is called PROTECTED.
A generic accepted result, PendingSubmit, a missing leg, conflicting manual/other-client
order, wrong account, price or quantity stays pending/blocked. API order IDs are allocated
under a bridge mutation lock shared by preflight, entries, protection and cancellation.
All-client open-order reads include ownership and OCA metadata and exclude What-If rows.

## Retries, exits and audit

The entry audit stores SUBMITTING intent before the broker request. Subsequent checks
verify the same group and cannot resubmit an unknown outcome. Exact pre-submission busy,
cooldown or disconnected 503 responses may be retried; generic failures and timeouts do
not clear intent. If one submission fails, the bridge preserves the identities and never
cancels a surviving stop or silently creates a replacement pair. A process crash, missing
leg or unconfirmed result requires broker reconciliation before another submission.

While native protection is enabled, the manager does not perform opposite-signal market
closes. This avoids racing the OCA orders and reopening a reversed position. Existing
EXIT_SUBMITTED actions also block protection until reconciled. Do not manually flatten
positions without coordinating their outstanding orders: OCA orders are not universal
reduce-only orders. Disabling the flag does not cancel broker-held orders; the old close
client still refuses to race open orders.
Pausing automation or setting the kill switch stops application mutations; it does not
cancel already armed broker-held GTC orders, which may still execute at the broker.

Partial fills are verified against remaining broker order quantities; there is no automatic
top-up or replacement. Exact protective executions plus a flat broker position produce
an EXIT_EXECUTED audit with a deterministic ID, deduplicated execution IDs and broker
evidence. Wrong identity, partial quantity, unknown executions or a remaining position
do not prove a complete exit. Historical execution availability can limit reconciliation;
missing evidence never creates a fabricated exit or P&L record.

Protection attachment is after a confirmed fill, not an atomic entry bracket. There is a
window before attachment and failures can leave a position unprotected. Existing positions
are only protected after the enabled manager checks them. Never treat app health or a
successful deployment as evidence that every position is protected; inspect broker orders.

## Verification and deployment

Regression coverage includes LONG/SHORT levels, conservative rounding, exact scope,
all-client conflicts, What-If rejection, changed positions, partial coverage, duplicate
checks, timeouts and persistent intent, pre-submission busy recovery, Paper/kill gates,
opposite-close coordination, and exact/idempotent protective fill reconciliation.
Run the full production-equivalent container suite before activation.

1. Record current commit/image, save a versioned app rollback image and the current
   mounted `tools/ibkr_bridge.py` outside the repository before pulling the merged change.
2. Build and test app with `-T` and mount `$PWD/tools:/app/tools:ro` for bridge tests.
3. Restart the bind-mounted bridge. Verify the mounted file hash matches the new source,
   `/health` is connected/simulation and advertises the native protection capability,
   and `/account` succeeds. Do not activate against an old bridge.
4. Recreate app with `-f docker-compose.oracle.prod.yml
   -f ops/docker-compose.ibkr-protection.yml` using `.env.oracle`. Verify the feature flag
   inside the running app, running image, healthy dependencies and Alembic head.
   Retain the override on subsequent recreations; `restart app` preserves the environment.
5. Observe the manager's initial check. Confirm exact stop/limit pairs, account, side,
   quantities, GTC, OCA group/type and broker statuses via `/orders`, then compare current
   `/positions`. A close may fill during activation if a saved level is already reached.
   Do not force a new entry to test protection. Rejections/pending states need inspection.

Rollback requires inspection first. Broker-held GTC orders survive app/bridge restarts;
never globally cancel or recreate them as part of rollback. Restore the saved app image
with protection disabled if needed, and preserve broker metadata in the bridge until
orders are reconciled. Only restore the old bridge script after confirming no outstanding
native protective orders require its metadata. The saved entry audit is retained.
