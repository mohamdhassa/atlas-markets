# Reviewed closed Paper trade recovery

This candidate adds reporting-only recovery when an opening order filled after
its original callback disappeared, but an operator has the actual Activity Flex
execution export and the complete, independently confirmed exit.

The existing statement importer still requires its original full-fill audit.
The new CLI is a separate workflow; it does not fabricate a Filled callback,
rewrite the original entry, set protection levels, resume automation or submit
orders. It is not an open-position protection recovery tool.

## Preview and apply

Keep automation paused. Place the original XML in a private path accessible to
the app container; do not commit it or include it in an image. Use an active
ADMIN identity and explicitly review the entry/exit UUIDs and every opening
statement trade ID. Statement order IDs are retained separately from TWS IDs.

```bash
python -m app.scripts.recover_ibkr_closed_pair \
  --file /imports/activity.xml --profile-id PROFILE_UUID --admin-id ADMIN_UUID \
  --entry-id ENTRY_UUID --exit-id EXIT_UUID --timezone America/New_York \
  --trade-ids TRADE_ID_1 TRADE_ID_2
```

The default is preview. Inspect its opening and closing quantities, prices,
commissions and P&L, then repeat with `--apply` to persist the pair atomically.
The operator explicitly attests the historical statement-to-action mapping;
matching symbol and quantity alone does not prove that assignment.

The CLI requires a connected Paper bridge, no remaining symbol position or
orders, no other executed/pending symbol actions since the selected entry,
and a saved exit that explicitly links that entry. It locks the profile/actions
and rechecks evidence. Any ambiguity stops recovery. The exit's local order,
account, symbol, side, full quantity, weighted price and execution times must
agree with the saved full Filled status. Identical callbacks are deduplicated;
contradictory financial callbacks are rejected. Pending commissions/P&L remain
unknown, and explicit zero is valid. Broker realized P&L is not reduced by fees
again. Opening execution timestamps must fall after entry creation (five-minute
clock tolerance) and before the confirmed close; next-session fills are allowed.

The existing isolated `ibkr_statement_evidence` table stores the pair's original
normalized statement executions, actual exit callbacks, source hash, timezones,
operator and import time. No schema change is required. Existing evidence is
never overwritten; an identical repeat is a no-op, a conflict needs a separate
reviewed correction. The ledger revalidates both current audits and retained
details before displaying totals. Recovered aggregates replace matching execution
identities, not unrelated orders that reuse the same local order number.

App rollback leaves this evidence in the database; older images ignore this new
source. The original broker audits remain available. Backups include the table.
This candidate needs the full isolated Docker validator before merge/deployment.
It does not certify market-data subscriptions, protection or Live execution.

## Exact opening context in the combined ledger

A deployed browser review found that, with older unmatched stock entries in the
same report, generic FIFO pairing could assign a recovered close an older opening
date and price even though its broker P&L was correct. Revalidated closed-pair
rows now carry their explicit entry action, price, timestamp and timestamp source
into the existing exact-entry pairing path. This changes reporting context only;
broker fees/P&L and original stored evidence remain unchanged. No reimport or
migration is needed. The regression includes older orphan lots and a later
ordinary close to verify inventory consumption as well as price, duration and return.
