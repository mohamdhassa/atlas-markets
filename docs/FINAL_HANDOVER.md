# ATLAS MARKETS — Final Handover

Last updated: 2026-08-30

## Release checkpoints

- `v1.0.0` — completed Simulation Release and permanent rollback/reference tag.
- `main` — v1.1 deployment candidate for multi-broker observation and Oracle Cloud hosting.

## What v1.1 changes

- promotes all eligible certified simulation symbols to `AUTO_TRADE` through an ADMIN-only bulk endpoint;
- keeps Bybit execution blocked until provider-side `10024` is resolved and re-certified;
- keeps IBKR Paper enabled under WhatIf, duplicate guards, broker fill verification and max 1 share/order;
- introduces Oracle production compose/environment assets;
- moves the always-on app/data tier to Oracle;
- keeps MT5/IBKR broker bridges on private execution nodes;
- refreshes all operational documentation.

## Current certified execution routes

1. Fusion MT5 Demo — FX, metals, commodities.
2. IBKR Paper — stocks, ETFs; max 1 share/order.

Blocked/non-execution:

- Bybit Testnet — provider `10024`.
- Twelve Data — data only.
- Live Money — gated.

## Bulk AUTO_TRADE

ADMIN endpoint:

`POST /strategies/symbols/auto-trade/eligible`

It may seed missing starter symbols and promote all configured symbols on ready certified simulation routes. It returns `created`, `promoted`, and `blocked` lists. Bybit and Live Money remain blocked by design.

## Oracle deployment

Use:

- `docker-compose.oracle.yml`
- `.env.oracle.example`
- `docs/ORACLE_DEPLOYMENT.md`

Oracle hosts FastAPI, PostgreSQL and Redis. Public ingress should terminate at HTTPS 443. Do not expose PostgreSQL, Redis, FastAPI internal port or broker bridge ports publicly.

## Broker execution nodes

### MT5

Requires always-on Windows MT5 Demo terminal with Algo Trading enabled and `tools/mt5_bridge.py` running.

### IBKR

Requires TWS/IB Gateway Paper session plus `tools/ibkr_bridge.py`. Appropriate real-time U.S. market-data subscriptions are recommended before broad unattended stock/ETF automation.

Oracle should reach bridge nodes via a private VPN. If the execution node is a personal computer, trading stops when that machine sleeps/reboots/goes offline.

## Bybit resolution

Do not modify ATLAS to suppress or ignore `10024`. Use the same Testnet account in Bybit UI, reproduce the product restriction if possible, open support with the account UID and exact error, then re-run diagnostics and a controlled open/close certification after provider approval.

## Local v1.1 acceptance

```powershell
cd "C:\Users\USER\Downloads\altas-markets"
git pull origin main
docker compose stop app
docker compose rm -f app
docker compose build --no-cache app
docker compose up -d app
docker compose exec app python -m pytest -q
docker compose ps
```

Then authenticate as ADMIN and call the bulk AUTO_TRADE endpoint. Review its blocked list before starting the observation run.

## Oracle acceptance

See `ORACLE_DEPLOYMENT.md`. Minimum acceptance:

- app/PostgreSQL/Redis healthy;
- migration at head;
- tests pass;
- `/api/system` healthy;
- HTTPS works;
- private bridge connectivity works;
- one monitored scan completes;
- MT5/IBKR broker truth matches ATLAS action ledger;
- backup completes successfully.

## Backup rule

Database dumps, `.env`, `.env.oracle`, broker secrets and private keys never go into Git. The repository now ignores `backups/` and database dump extensions.

## Observation period

Run the v1.1 simulation continuously for several weeks without repeatedly changing strategy logic. Track P&L, drawdown, profit factor, broker cancellations, risk blocks, action lineage, automation uptime and broker/ATLAS consistency.

## Live Money

Live Money remains a separate future certification. Oracle hosting and broad AUTO_TRADE simulation do not change that boundary.
