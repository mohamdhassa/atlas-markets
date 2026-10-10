# IBKR Paper statement reconciliation

## Export

Log into IBKR Client Portal with the Paper account and open Reporting → Statements / Flex
Queries. Create an **Activity Flex Query**, XML output, Trades section, **Executions** level.
Choose the historical dates covering ATLAS entries and closes. Include:

- Account ID, Asset Class, Currency, Symbol, Buy/Sell, Quantity, Trade Price;
- Trade ID, IB Order ID, IB Execution ID, Date/Time, Open/Close Indicator, Level of Detail;
- IB Commission, IB Commission Currency, FIFO P/L Realized (Realized PNL), Multiplier;
- Transaction Type, Original Trade ID and Taxes, if present.

Set Date/Time formatting to `YYYYMMDD;HHMMSS` and record the configured timezone. For an
Eastern-time export use `America/New_York`; do not assume Bahrain or server time. Do not send
login credentials or a Flex Web Service token. The initial implementation accepts downloaded
XML files, not automatic Flex Web Service polling, CSV or PDF statements.

Official references:
- https://www.ibkrguides.com/clientportal/accountmanagementforpapertradingaccount.htm
- https://www.ibkrguides.com/reportingreference/reportguide/tradesfq.htm

## Preview and match

Authenticated ADMIN endpoint: `POST /performance/ibkr-statement/import`.

```json
{
  "profile_id": "IBKR_PROFILE_UUID",
  "xml": "<FlexQueryResponse>...</FlexQueryResponse>",
  "timezone": "America/New_York",
  "mapping": {},
  "apply": false
}
```

An empty mapping returns normalized statement trades and saved audit actions without writes.
Review the statement against the broker fill audit. Map each action UUID to all statement
trade IDs for that broker order. Statement IB order IDs are **not assumed to be TWS API local
order IDs**, and nearest-time/price candidates are never automatically assigned.

```json
{"ATLAS_ACTION_UUID": ["STATEMENT_TRADE_ID_1", "STATEMENT_TRADE_ID_2"]}
```

Send the same request with the reviewed mapping and `apply:false` to validate the full plan.
Then send `apply:true` to save it in one transaction. Account, profile, owner, environment,
symbol, side, quantity, full Filled audit and weighted average execution price must agree.
All executions of an order must be supplied; audit time must be within 24 hours after execution
(or five minutes before for clock skew). Mappings to partial fills, unmatched orders, mixed
open/close trades, non-USD currencies, non-stock assets, taxes or corrections stop for review.
No arbitrary unmatched broker transactions are added to ATLAS history.

A repeated identical import is a no-op. A conflicting import is rejected instead of silently
replacing earlier evidence. Imports sharing a profile serialize through row locks. No external
broker calls occur while locks are held. Evidence is stored in its own table, so concurrent
protection audit JSON updates cannot erase it. Non-admin and unauthenticated calls are refused.

## Server operator alternative

The same workflow is available inside the app container:

```bash
python -m app.scripts.import_ibkr_statement \
  --file /imports/ibkr-activity.xml \
  --profile-id IBKR_PROFILE_UUID --admin-id ACTIVE_ADMIN_UUID \
  --timezone America/New_York
```

Mount a private server directory read-only at `/imports`. Save the reviewed mapping locally as
`/imports/mapping.json`. Add `--mapping /imports/mapping.json` to preview it, then add `--apply`
to commit. IDs above are placeholders; obtain the actual IDs from Accounts/authenticated
`/accounts` and `/auth/me`, or authorized read-only server inspection. Keep exported statements
and mapping files private and out of git. CLI execution requires server operator access and an
existing active ADMIN audit identity; it does not replace API authentication.

## Ledger behavior and recovery

Imports store normalized execution evidence, file SHA-256, operator, import timestamp,
timezone and explicit mapping basis in `ibkr_statement_evidence`, keyed uniquely by the saved action ID.
Original result, fill audit and native protection data remain intact. Migration `20261010_0023` adds the isolated evidence table.

The ledger revalidates that evidence and uses one complete statement order aggregate in place
of the same order's live fragments or saved fallback. Scope remains profile/owner/environment.
Statement timestamps replace approximate audit times for imported rows. Opening orders do not
become closed trades merely because their statement reports zero realized P&L. Closing orders
contribute only when FIFO realized P&L is explicitly present; an explicit zero is valid, while
missing P&L stays pending. Closing-order commission is displayed separately, with rebates
retaining their sign. Broker FIFO P&L already includes commissions, so it is never reduced a
second time. Interest, dividends and other account charges are outside trade P&L.

The report covers imported mapped ATLAS trades, not a complete account statement. Existing
historical import mismatches require a separate reviewed correction; this workflow does not
overwrite conflicting evidence. A rollback of the app leaves the added table and imported evidence in PostgreSQL
and older builds ignore it. Older images lack the new Alembic revision, so use the temporary
`ops/docker-compose.ibkr-statement-rollback.yml` command override alongside the production and
protection Compose files when recreating the previous image. This bypasses the old image’s
startup migration and runs its normal Uvicorn command. Remove the rollback override on the
next normal upgrade. Do not downgrade the migration during an app rollback; downgrading
would drop the evidence table. Database backups retain the evidence with existing action audits.
There is no live-data recovery without the actual broker export.

Deployment: preserve a rollback image and make a private `pg_dump --format=custom` backup of
`atlas_markets` before applying the migration. Build app, run the full container suite with
`IBKR_NATIVE_PROTECTION_ENABLED=false` **only in the temporary test container**, then recreate
only app with `ops/docker-compose.ibkr-protection.yml`. Verify health, Alembic head, protection
flag and broker-held orders. Do not restart Gateway/bridge or modify positions for this import.
