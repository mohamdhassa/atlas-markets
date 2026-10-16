# Project closeout and live-money decision

## 2026-10-16 delivery checkpoint

The application through PR #170 is deployed. Its immutable candidate passed 814
container tests with zero skips, clean migrations and app health/system smoke.
Production health/schema and a reviewed, durable closed Paper round trip were
verified. Automation remains paused and Live trading disabled.

IBKR's connected Demo login reports unsubscribed market data (10167) and supplies
historical quote fallback. Freeze feature work at this software checkpoint;
full Paper runtime acceptance remains pending. The table below records the earlier
source-audit plan; the current evidence and unresolved runtime checks are recorded
in [Paper handover](PAPER_HANDOVER_20261016.md). Do not treat tests, flags, or this
checkpoint as proof of broker-connected trading readiness or a successful restore.

## Earlier source audit and acceptance plan

Source review: 2026-10-16, based on main `30ddccf655abb20a631346104a152b1944cef11d`
plus this candidate. This is a source audit, not a production attestation.

Candidate updates also persist uncertain IBKR entry intent, block retries, retain
partial/unknown cancelled outcomes, and refresh authorization immediately before
submission. See `RELEASE_V1_IBKR_SUBMISSION_INTENT.md`. The same candidate validation
runner now runs in CI and on a Docker host, without production configuration.

## Finish line

Freeze the existing application and trading policy. No new dashboards, indicators,
timeframe searches, broker additions or frontend rebuilds are required to close the
Paper milestone. Existing MT5 authorization work does not block an IBKR Paper release.
Engineering completion and a profitable live strategy are separate outcomes.

| Release area | Evidence now | Remaining acceptance |
|---|---|---|
| App and broker regression suite | Local Python suite passes; candidate includes delayed-fill regression coverage | Full production-equivalent container result with PostgreSQL/Redis |
| Schema | Source head `20261010_0023`, no new migration in this candidate | Clean-database upgrade and actual production head |
| Market data | Main has completed/recent bars and actual live quote provenance gates | Deployed app/bridge agreement and subscribed session evidence |
| IBKR protection | Native Paper OCA lifecycle and persistent intent; candidate retains delayed entry prices | Broker-confirmed quantities, sides, OCA groups and active stop/target statuses |
| Orders and ledger | Durable fill/statement/native-close recovery; candidate deduplicates delayed callbacks | No unresolved submission; one confirmed close represented once |
| Recovery | Restart/outage guards have regression coverage | Controlled Paper interruption and app restart reconcile without duplicate orders |
| Access and UI | Existing ADMIN/USER and frontend regression suite | Desktop/mobile and ownership smoke checks on deployed release |
| Recovery assets | Existing backup/rollback runbooks | Successful isolated restore drill and recorded rollback image |
| Live execution | `/release/readiness` explicitly reports providers NOT_CERTIFIED | Separately implemented and reviewed provider execution release |

Do not mark a row complete from documentation, a green health endpoint, an order
acceptance, or a skipped integration test. Record the commit/image, timestamp and
sanitized evidence for each completed runtime check.

## Bounded Paper acceptance

Use the existing fixed criteria from `RELEASE_V1_IBKR_ENTRY_DATA_QUALITY.md`:

1. Container suite passes and the merged app/bridge deployment is verified.
2. Ten consecutive regular-session scheduled scans retain quality evidence or a
   specific expected block, without an unclassified data/execution error.
3. Broker positions and protective quantities agree; there is no unresolved submission;
   a broker-confirmed close appears exactly once in the ledger.
4. One app restart and a controlled Paper connectivity interruption preserve broker
   orders, block entries during failure and reconcile on recovery.

Then archive the Paper release with known external dependencies and stop feature work.
Do not interrupt a real account or force trades to manufacture evidence.

## What still prevents a real-money release

Current certified executors are simulation-only. The live arming fields and a
configuration flag do not create a certified live route. Required work is:

1. Select one provider/environment and implement its separately reviewed live entry,
   exit, protection, timeout, duplicate and restart lifecycle without weakening the
   existing simulation boundaries.
2. Enforce the agreed capital/exposure limits and broker-authoritative daily realized
   loss at submission, with unknown/stale evidence blocking entries. An analytical
   P&L page is not an execution risk control.
3. Verify actual real-time data, fees, minimum quantities and protective-order behavior
   for that account. Paper fills do not establish live liquidity or stop execution.
4. Supply the existing starter-capital promotion evidence for one frozen policy:
   at least 30 validation trades, 30 forward days, positive net expectancy after
   costs, profit factor >=1.2, drawdown <=10%, and zero duplicate/unreconciled orders.
   These are existing project gates, not a promise that meeting them prevents loss.
5. Record restore/kill/recovery validation, the initial capital and loss limits, and
   the separately reviewed live go/no-go release.

This review has no production connection, current broker-state attestation or fresh
strategy-performance evidence. It cannot truthfully certify Live Money or close the
runtime acceptance rows. Historical losing Spot comparisons are not replaced by
optimistic assumptions or another parameter search.

## Candidate validation command

From a checkout containing the runner, supply the full candidate commit SHA:

```bash
bash ops/validate_release_candidate.sh <FULL_CANDIDATE_COMMIT_SHA>
```

The runner creates and removes its own isolated test services. It never reads production
connection variables or `.env.oracle`. It tests the archived commit even when the host
worktree is on another branch. It does not switch the checkout or deploy anything.
Capture its final PASS line with the immutable SHA. A failed or unavailable Actions
runner is not a pass; the same server command can supply the container check before merge.
