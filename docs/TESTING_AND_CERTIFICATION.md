# ATLAS MARKETS — Testing and Certification

Last updated: 2026-09-23

## Release rule

A code change is not considered deployed until the local/Oracle runtime has passed:

```bash
alembic current
python -m pytest -q
health check
/api/system check
```

For broker changes, automated tests are necessary but not sufficient; broker-native controlled certification is also required.

## Current provider certification

### Fusion MT5 Demo

Status: CERTIFIED.

Evidence requirements already satisfied:

- bridge/terminal connectivity;
- Demo server verification;
- broker order check;
- protected order submission;
- open position confirmation;
- SL/TP lifecycle support;
- controlled close verification;
- automatic execution through the ATLAS engine.

### IBKR Paper

Status: CERTIFIED with restrictions.

Required safeguards:

- Paper/simulation bridge only;
- WhatIf preflight;
- max 1 share/order;
- existing position/open-order guard;
- post-submit status polling;
- fills marked `EXECUTED` only after broker confirmation;
- cancellation persisted as `CANCELLED`.

Known operational dependency: real-time market-data entitlement. The bridge can receive delayed data, but broad unattended stock/ETF automation should use the appropriate IBKR real-time API market-data subscriptions. If broker market orders are cancelled due to unavailable major-exchange market data, that is a broker/data entitlement condition, not permission to falsify execution state.

### Bybit Testnet

Status: CERTIFIED for Testnet/Demo Spot only.

Required safeguards:

- private diagnostics and wallet access pass;
- provider/environment is Testnet or Demo;
- Spot instrument quantity metadata resolves through `qtyStep` or `basePrecision`;
- only persisted ATLAS-managed inventory may be sold;
- managed SELL quantity is capped to available broker balance and rounded down;
- broker fills are verified and persisted;
- a per-symbol broker failure does not fail the complete scan;
- Live Money and non-Spot products remain uncertified.

## Bulk AUTO_TRADE v1.1

The ADMIN endpoint `/strategies/symbols/auto-trade/eligible` is designed to promote all configured/seedable symbols that are on certified, ready simulation routes.

Expected behavior:

- Fusion MT5 Demo symbols -> promoted/created as AUTO_TRADE when route ready.
- IBKR Paper stocks/ETFs -> promoted/created as AUTO_TRADE when route ready.
- Bybit Testnet/Demo Spot crypto -> promoted/created when the route is ready.
- Live Money -> never bulk-promoted.

After deployment, verify the response counts and then inspect `/strategies/symbols` before allowing the observation period to proceed.

## Automation verification

For each scan confirm:

- scan ends `COMPLETED` unless a true runtime failure occurred;
- `BLOCK` reasons correspond to safety/provider decisions;
- `SKIP` corresponds to non-execution strategy state;
- `CANCELLED` corresponds to broker cancellation;
- `EXECUTED` has broker evidence;
- no duplicate symbol positions are opened by repeated scans;
- the kill switch stops new automatic execution.
- Bybit SELL quantities never exceed the available base-asset balance;
- Bybit balance reconciliation markers are visible in the activity log when applied.

## Performance verification

Do not infer strategy quality from raw broker-symbol P&L alone. Use verified attribution only when ATLAS action/order/fill lineage is present. Historical broker trades that predate lineage remain unverified.

## Oracle deployment acceptance

Before leaving the Oracle stack unattended:

- app/PostgreSQL/Redis all healthy;
- Alembic at head;
- pytest 100% pass;
- `/api/system` expected release/version;
- HTTPS working;
- 5432/6379/8000/8765/8766 not public;
- Oracle can reach MT5 and IBKR bridges over private VPN;
- broker profiles updated to private bridge URLs;
- one monitored automatic scan completes successfully;
- database backup completed and restore procedure documented.

## Live Money certification

Live Money is a separate future program. Simulation profitability alone is not certification. Live certification requires provider-by-provider controls, smaller initial limits, operational rollback, monitoring, explicit approval and a new release checkpoint.
