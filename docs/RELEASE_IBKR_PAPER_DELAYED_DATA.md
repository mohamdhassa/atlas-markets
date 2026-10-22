# Restore delayed-data IBKR Paper entries explicitly

The operator requested restoring Demo stock trading after entry data-quality
checks blocked the delayed feed. Default production behavior remains real-time
only. Opt-in `IBKR_PAPER_DELAYED_DATA_ENABLED=true` permits delayed references
only when the profile environment is PAPER, global Live execution is disabled,
and a fresh bridge health response proves connected=true and simulation=true.
A Live profile, enabled global Live flag or missing Paper proof cannot select
this policy. Disconnected or unverified bridges fail rather than relax checks.

## Entry behavior

The source is the last completed, timestamped and validated broker candle.
Readiness and the executor independently fetch their own candle windows. The
executor does not trust a saved preflight policy. At least 200 completed bars,
actual/requested timeframe agreement, sorted timestamps and valid OHLC remain
required. The normal one-interval-plus-90-second age budget gains a fixed
20-minute delayed-data allowance. Future timestamps, older session data and
weekend/overnight gaps beyond that budget remain blocked. For 5m bars the
maximum last-completed-bar age is 26 minutes 30 seconds.

The validated close is explicitly `PAPER_DELAYED_CANDLE_REFERENCE` with
`data_status=DELAYED_SIMULATION`, its original bar-end timestamp, age and policy.
It is never represented as a real-time snapshot or actual fill. This mode avoids
waiting for a snapshot that the Demo account cannot supply; default mode retains
the original live-quote checks. Audit evidence persists through existing
preflight/result JSON with no schema migration.

The same opt-in is used in readiness and certified entry submission. The
legacy scanner keeps its strict data checks; the scheduled certified worker
is the supported automation path. Signal/router thresholds, timeframe, share sizing, portfolio
limits, what-if, owner/profile authorization, pause/kill, existing-position/order
checks, pending-submission reconciliation and native protection remain intact.
Entries remain broker-filled market orders, not simulated fills at the delayed
reference. Fill-anchored protection and close evidence remain unchanged. Delayed
reference prices can differ materially from fills, affect risk sizing and cause
protection/what-if rejection. This is Demo functionality, not strategy validation
or Live-money certification. It does not guarantee a signal or an executed order.

## Verification and rollout

Regression tests cover default rejection, opt-in Paper proof, Live exclusion,
bounded ages, invalid references, retained insufficient-history rejection,
readiness sizing, submission-boundary rechecks, kill behavior and unchanged
strict quote validation. Run the full isolated production-equivalent suite
before merge. Deploy app only after capturing current image/commit and a rollback
image. No bridge/Gateway restart, account login or database migration is required.

Pause automation before recreating the app and verify current positions/orders.
Use the existing production compose and native-protection overlay plus the new
`ops/docker-compose.ibkr-paper-delayed.yml` overlay. Verify Live remains disabled,
the flag is enabled, health/migrations succeed and one read-only preflight retains
`IBKR_PAPER_DELAYED_DATA` evidence. Resume only the existing certified simulation
routes and inspect one monitored scan; no forced entry is needed. Retain both
protection and delayed-data overlays on later app recreations.

Rollback: pause new submissions, use the preserved app image and omit the delayed
flag overlay; retain native protection for any existing holdings. Reconcile
orders and protection before resuming. Changing this data mode never closes or
cancels positions/orders or deletes audit history.
