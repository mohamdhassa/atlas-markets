# Paper software handover — 2026-10-16

Status: validated software delivery checkpoint; automated entries paused.
Full broker-connected Paper acceptance and Live Money certification are pending.
This handover freezes feature work so another project can proceed without
representing an unavailable market-data feed as an application defect.

## Verified evidence

Evidence below was supplied by the server operator and inspected during the
release session. Private broker statements, account identifiers and trade
financials are deliberately excluded from this public handover.

| Check | Recorded result |
|---|---|
| Tested candidate | `97d8d44dfaba11d68493c3162f9ccf54e8fb3991` |
| Deployed integration commit | `0f12cce20dddbb7bf75f9787270bb0082209a46b` (PR #170); source tree matches candidate |
| App image | `sha256:8db93ceb491370bafdabfad0b0bd9babb1a424bfd78eb931985bb0b5cec788a1` |
| Isolated production-equivalent validation | 814 passed, zero skipped; PostgreSQL/Redis and Node-backed checks included |
| Clean schema upgrade and production schema | `20261010_0023` head |
| Deployed health | App, database and Redis returned `ok` |
| Trading controls | `LIVE_DISABLED AUTOMATION_PAUSED` verified |
| Legacy unprotected Paper position | Operator-approved full broker close; position zero and no remaining symbol orders |
| Reviewed historical evidence | Original Flex XML checksum verified; preview then atomic application through PR #170 workflow |
| Durable closed-trade ledger | `DURABLE_LEDGER_VERIFIED`; exactly one opening and closing with explicit broker P&L, using an empty live execution list |
| Backup | Private custom-format production dump created; archive listing successfully checked |
| Rollback | Previous app image retained under a versioned `pre-pr170` tag; previous commit/image recorded on server |

The backup listing check is not a restore drill. Reading retained ledger rows
without live fills is not a physical bridge restart test. Core health is not
proof that all provider sessions, user interfaces or trading feeds are ready.

## External dependency

The connected IBKR login is labelled **Individual (Demo)**. Its Account Settings
page exposes a Paper account reset, but no market-data subscription or sharing
controls. The operator confirmed this is their only IBKR account.

The deployed bridge returned `HISTORICAL_FALLBACK` / `HISTORICAL` for the stock
quote. IBKR callback **10167** explicitly reported that requested market data
is not subscribed. Native protection is enabled and the bridge advertises its
capability; that alone does not attest a current broker-held protective pair.

Do not weaken quote provenance, bar coverage, freshness, risk or certification
checks to restart entries on this feed. Do not create new trades simply to
manufacture release evidence. No subscription purchase, account opening,
funding, Live execution or strategy-profitability claim is part of this handover.

## Regression coverage already executed

The passing container suite includes:

- Native GTC/OCA protection construction, exact quantity/side validation,
  partial fills, conflicting orders and protection submission timeout recovery.
- Persistent uncertain entry intent, worker cancellation, duplicate prevention,
  refreshed authorization and engine/kill-switch checks before submission.
- Broker disconnect/recovery, stale-session blocking, read cooldowns and
  account-summary refresh requirements.
- Reviewed closed-pair evidence, next-session opening timestamps, callback
  deduplication, wrong scope, contradictory financial evidence, unknown/zero
  financial values, immutable imports and reused local order identifiers.

These simulated broker regressions validate software behavior; they do not
replace the remaining runtime checks below. No new runtime code was changed
for this documentation checkpoint, so the unchanged suite was not repeated.

## Resume checklist when suitable broker access is available

1. Confirm eligible IBKR API market-data permissions for the intended Paper
   login. During a regular session, verify actual `LIVE` quote provenance and
   adequate, recent completed bars with the existing data-quality checks.
2. Inspect all provider positions, open orders and unresolved action intents.
   Validate native protection against broker-held orders for any approved test
   position; a capability flag does not complete this check.
3. Complete ten scheduled regular-session scans with retained quality evidence
   or specific expected blocks and no unexplained execution/data errors.
4. Run the controlled Paper connectivity interruption and app restart checks,
   verifying preserved broker orders and no duplicate submissions on recovery.
5. Complete the isolated production-backup restore drill and desktop/mobile
   ADMIN/USER ownership smoke checks.
6. Review the collected evidence before deliberately resuming Paper automation.
   Keep Live execution disabled until its separate certification is complete.

Use [Project closeout](PROJECT_CLOSEOUT.md) for the fixed acceptance criteria and
remaining live-route, capital/loss-control and frozen-policy evidence gates.
No further feature expansion or parameter search is needed for this checkpoint.
