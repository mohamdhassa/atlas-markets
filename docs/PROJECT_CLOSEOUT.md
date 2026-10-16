# Project closeout and live-money decision

Source review: 2026-10-16, based on main `30ddccf655abb20a631346104a152b1944cef11d`
plus this candidate. This is a source audit, not a production attestation.

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

Run against an isolated disposable test database and Redis, never production. Set the
four test connection variables in the shell without printing their values:

```bash
docker build --tag atlas-markets:closeout-test .
docker run --rm --network host -e DATABASE_URL atlas-markets:closeout-test alembic upgrade head
docker run --rm --network host \
  -e DATABASE_URL -e TEST_DATABASE_URL -e REDIS_URL -e TEST_REDIS_URL \
  -v "$PWD/tools:/app/tools:ro" \
  atlas-markets:closeout-test python -m pytest -o addopts='' -q -rs
```

`DATABASE_URL` and `TEST_DATABASE_URL` must identify the same disposable database.
The two Redis variables must identify the disposable Redis. The CI workflow provisions
these isolated services itself. A failed or unavailable Actions runner is not a pass;
use the equivalent isolated server container check before merge.
