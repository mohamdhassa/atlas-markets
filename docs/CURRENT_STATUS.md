# ATLAS MARKETS — Current Status

Last updated: 2026-09-25

## Baseline

- v1.0.0 Simulation Release: COMPLETE and tagged.
- v82 provider-aware shadow analytics: DEPLOYED on Oracle.
- v83 documentation and architecture closeout: COMPLETE.
- v84 MT5 runtime-readiness software: COMPLETE; native Windows certification pending.
- v85 consolidated responsive frontend: COMPLETE.
- v86 IBKR half-open session recovery: COMPLETE; production deployment pending.
- Database: `20260925_0019 (head)`.
- Live Money remains gated.

## v1.1 objectives

1. Promote all eligible certified simulation symbols to AUTO_TRADE.
2. Use the certified simulation routes during the observation period: Fusion MT5 Demo, IBKR Paper, and Bybit Testnet/Demo Spot.
3. Monitor Bybit managed-inventory and broker-balance reconciliation during controlled Spot automation.
4. Run the application, PostgreSQL and Redis continuously on Oracle Cloud.
5. Keep broker bridges reachable privately from Oracle.
6. Keep documentation synchronized with the deployed architecture.

## Provider state

### Fusion MT5 Demo

- Application adapter, centralized runtime, readiness and bridge support: COMPLETE
- Dedicated native Windows installation/recovery certification: PENDING EXTERNAL NODE
- Automatic unattended production route: not claimed until the terminal, authorization, bridge and recovery tests pass together
- Intended markets: FX, metals, commodities

### IBKR Paper

- Connectivity: CERTIFIED
- Execution: CERTIFIED
- Automatic route: ELIGIBLE
- Markets: stocks, ETFs
- Hard cap: 1 share/order
- WhatIf + broker fill verification required
- Real-time API market-data subscriptions strongly recommended for broad unattended U.S. equity automation
- v82 shadow coverage: 9 configured strategies observed with zero scan errors at deployment acceptance

### Bybit Testnet

- Private/API diagnostics: PASS
- Wallet/account/permissions: PASS
- Spot BUY/SELL and broker-fill verification: PASS
- Quantity metadata: `qtyStep` with `basePrecision` fallback
- Managed SELL reconciliation: available broker balance + exchange-step rounding
- Execution certification: CERTIFIED for Testnet/Demo Spot
- Automation: ELIGIBLE when account, strategy and risk gates pass
- Live Money and non-Spot products: NOT CERTIFIED
- v82 shadow coverage: 5 configured strategies observed and 5 outcomes settled with zero scan errors at deployment acceptance

## v82 production evidence

- Application image: `sha256:798306df1a4d4381e03d2931491aec7e53a247dd2d2f9a05c03177914d46127f`.
- v81 rollback image: `sha256:1dc025b01543611cdaa244506f644dd40e6d89703b621da10bb5ab8753403b18`.
- Full acceptance suite: 239 passed, four expected external integration skips.
- Health: application, PostgreSQL and Redis healthy.
- GitHub main: `cdbacec`.

### Twelve Data

- Market/historical data only
- Never execution

## Bulk AUTO_TRADE

v1.1 adds ADMIN endpoint:

`POST /strategies/symbols/auto-trade/eligible`

It seeds/promotes starter-universe symbols only on ready certified simulation routes. MT5 Demo, IBKR Paper, and Bybit Testnet/Demo Spot can be promoted. Live Money is never included.

## Oracle deployment

New assets:

- `docker-compose.oracle.yml`
- `.env.oracle.example`
- `docs/ORACLE_DEPLOYMENT.md`

Oracle target:

- FastAPI bound internally to `127.0.0.1:8000`
- PostgreSQL/Redis private Docker network
- persistent volumes
- `restart: unless-stopped`
- HTTPS reverse proxy/load balancer
- private VPN to execution nodes

## Execution-node requirement

A fully online website does not guarantee broker execution. Fusion MT5 requires an always-on Windows execution node. IBKR requires TWS/IB Gateway plus the ATLAS IBKR bridge. For a true multi-week unattended run, these execution nodes must also remain online and reachable from Oracle.

## Documentation state

v83 adds a canonical documentation index, production ERD, API reference, user/admin guide, operations runbook, backup/recovery guide and security-operations guide. Architecture, README, current status, roadmap and final handover are aligned to v82 production evidence.

## Next ordered work

1. Install and certify the native Windows MT5 execution node using the v84 runbook.
2. Accumulate and analyze settled provider-specific shadow evidence.
3. Calibrate strategies without contaminating the forward-validation window.
4. Begin separately specified development only after acceptance criteria are documented.

## Safety boundary

Do not broaden the Bybit certification beyond Testnet/Demo Spot. Do not expose bridge/database ports publicly. Do not enable Live Money as part of the Oracle migration.
