# ATLAS MARKETS — Current Status

Last updated: 2026-08-30

## Baseline

- v1.0.0 Simulation Release: COMPLETE and tagged.
- v1.1: active deployment/expansion candidate.
- Database baseline verified at Alembic head before v1.1 work.
- Live Money remains gated.

## v1.1 objectives

1. Promote all eligible certified simulation symbols to AUTO_TRADE.
2. Use both certified execution brokers during the observation period: Fusion MT5 Demo and IBKR Paper.
3. Resolve Bybit `10024` through provider support/account-product approval and re-certify before enabling crypto execution.
4. Run the application, PostgreSQL and Redis continuously on Oracle Cloud.
5. Keep broker bridges reachable privately from Oracle.
6. Keep documentation synchronized with the deployed architecture.

## Provider state

### Fusion MT5 Demo

- Connectivity: CERTIFIED
- Execution: CERTIFIED
- Automatic route: ENABLED when account/strategy/risk gates pass
- Markets: FX, metals, commodities

### IBKR Paper

- Connectivity: CERTIFIED
- Execution: CERTIFIED
- Automatic route: ELIGIBLE
- Markets: stocks, ETFs
- Hard cap: 1 share/order
- WhatIf + broker fill verification required
- Real-time API market-data subscriptions strongly recommended for broad unattended U.S. equity automation

### Bybit Testnet

- Private/API diagnostics: PASS
- Wallet/account/permissions: PASS
- Controlled order reaches provider
- Provider response: `10024` compliance/product restriction
- Execution certification: BLOCKED
- Automation: provider gate remains active

### Twelve Data

- Market/historical data only
- Never execution

## Bulk AUTO_TRADE

v1.1 adds ADMIN endpoint:

`POST /strategies/symbols/auto-trade/eligible`

It seeds/promotes starter-universe symbols only on ready certified simulation routes. MT5 Demo and IBKR Paper can be promoted. Bybit is reported as blocked. Live Money is never included.

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

Updated for v1.1:

- README
- Architecture
- ERD
- Authorization
- Providers
- Testing & Certification
- Oracle Deployment
- Current Status

Final handover/roadmap are updated as part of the same rollout before the Oracle cutover is considered complete.

## Immediate acceptance sequence

1. Pull v1.1 changes locally.
2. Rebuild app.
3. Run full pytest.
4. Call bulk eligible AUTO_TRADE endpoint as ADMIN.
5. Review promoted vs blocked symbols.
6. Run one monitored automatic scan.
7. Confirm MT5 + IBKR broker truth.
8. Prepare Oracle VM secrets/network.
9. Restore/copy PostgreSQL state to Oracle.
10. Establish private broker-bridge connectivity.
11. Run Oracle acceptance suite.
12. Begin multi-week observation.

## Safety boundary

Do not remove the Bybit provider gate to make the UI look complete. Do not expose bridge/database ports publicly. Do not enable Live Money as part of the Oracle migration.
