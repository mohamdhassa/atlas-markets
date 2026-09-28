# ATLAS MARKETS v1 — Final Handover

## Release identity

- Canonical tag: `v1.0.0`
- Canonical commit: `5ef08db6426876be6019541c45c0b3b3851f85eb`
- Repository: `mohamdhassa/atlas-markets`
- Production model: Oracle-hosted core with private broker bridges

## Included system

- current frontend and navigation;
- PostgreSQL data and Redis coordination;
- Bybit Testnet and IBKR Paper integrations;
- portfolio, decisions, actions, executions, fills and P&L surfaces;
- shadow strategy observations and provider-aware analytics;
- ADMIN/USER authentication and administration;
- risk gates, kill switch, certification and audit history.

## Operating ownership

| Area | Source of truth | Primary runbook |
|---|---|---|
| Application/dependencies | Docker health and application logs | `OPERATIONS_RUNBOOK.md` |
| Database/schema | PostgreSQL and Alembic | `BACKUP_AND_RECOVERY.md` |
| Provider positions/fills | Broker-native provider | `PROVIDERS.md` |
| IBKR availability | Gateway, bridge and watchdog | `IBKR_CONTINUITY.md` |
| Authorization/secrets | Auth audit and protected configuration | `SECURITY_OPERATIONS.md` |
| Data model | migrations and SQLAlchemy models | `ERD.md` |

## Deployment rule

Create and validate a candidate image, preserve a rollback image, recreate only the app when
appropriate, then verify health, migration, logs, providers and one monitored scan. Never
replace the frontend or canonical baseline implicitly. Database, Redis and broker bridges are
changed only when the release explicitly requires it.

## Recovery rule

When execution integrity is uncertain, kill new automation, preserve evidence, verify broker
truth, recover the smallest failed component and reconcile before resuming. Backups are not
certified until a restore drill succeeds.

## Forward work

1. Keep the v1 baseline stable during documentation and operational hardening.
2. Add/authorize the MT5 execution node through a separately tested change.
3. Improve frontend behavior only through scoped, approved, regression-tested updates.
4. Continue forward shadow observation before strategy promotion.
5. Develop additional functionality from v1 without reviving reverted baselines.

Live Money requires a separate certification and approval release.
