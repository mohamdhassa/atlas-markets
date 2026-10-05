# ATLAS MARKETS v1 — Documentation Index

This index is the entry point for the canonical `v1.0.0` baseline at Git commit
`5ef08db6426876be6019541c45c0b3b3851f85eb`.

## Product and design

- [Architecture](ARCHITECTURE.md) — components, trust boundaries and runtime flow.
- [ERD](ERD.md) — PostgreSQL entities, relationships and ownership rules.
- [ERP operating model](ERP_OPERATING_MODEL.md) — ERP-style control, workflow and audit model.
- [Authorization](AUTHORIZATION.md) — ADMIN/USER authority and execution gates.
- [Providers](PROVIDERS.md) — broker and data-provider responsibilities.
- [Adaptive strategy router](ADAPTIVE_STRATEGY_ROUTER.md) — regime selection, Darvas Box and shadow-only safety.
- [Adaptive router release](RELEASE_V1_ADAPTIVE_ROUTER.md) — delivered scope and execution exclusions.
- [Routed paper execution](RELEASE_V1_ROUTED_PAPER_EXECUTION.md) — strategy agreement gate for certified simulation orders.
- [$100 starter-capital readiness](STARTER_CAPITAL_READINESS.md) — conservative sizing and promotion gates for the planned first live balances.
- [IBKR fractional Paper execution](IBKR_FRACTIONAL_PAPER_EXECUTION.md) — risk-sized fractional entries, broker preflight, reconciliation and exact exits.
- [IBKR whole-share sizing](RELEASE_V1_IBKR_WHOLE_SHARE_SIZING.md) — round entries down to the certified step without increasing risk.
- [IBKR fractional capability fix](RELEASE_V1_IBKR_FRACTIONAL_CAPABILITY_FIX.md) — error 10243 handling and safe whole-share fallback.
- [Starter-capital readiness release](RELEASE_V1_STARTER_CAPITAL_READINESS.md) — delivered controls and verification status.
- [Trade and performance ledger](TRADE_PERFORMANCE_LEDGER.md) — provider capital, closed trades, attribution and news context.
- [Trade ledger release](RELEASE_V1_TRADE_PERFORMANCE_LEDGER.md) — delivered frontend consolidation and reporting scope.

## Use and administration

- [User and administrator guide](USER_ADMIN_GUIDE.md) — daily use and interpretation.
- [Developer onboarding](DEVELOPER_ONBOARDING.md) — repository map, workflow and definition of done.
- [API reference](API_REFERENCE.md) — operational endpoint families and roles.
- [Current status](CURRENT_STATUS.md) — deployed baseline and known limitations.
- [Roadmap](ROADMAP.md) — work after the v1 baseline.

## Production operations

- [IBKR outage recovery](RELEASE_V1_IBKR_OUTAGE_RECOVERY.md) — backend connectivity, bounded read cooldowns and explicit stale balances.

- [Provider request isolation](RELEASE_V1_PROVIDER_REQUEST_ISOLATION.md) — IBKR summary cleanup and bounded read-only page workers.
- [Live system logs](LIVE_SYSTEM_LOGS.md) — ADMIN timeline, scan correlation, trading outcomes, safe provider/browser telemetry and retention limits.

- [Database operations](DATABASE_OPERATIONS.md) — production identity, pgAdmin SSH access and schema changes.
- [Operations runbook](OPERATIONS_RUNBOOK.md) — health, deployment, incident and rollback procedures.
- [IBKR continuity runbook](IBKR_CONTINUITY.md) — Gateway, bridge, watchdog and VNC recovery.
- [IBKR IBC reliability](IBKR_IBC_RELIABILITY.md) — staged automated login/restart candidate and rollback.
- [Oracle deployment](ORACLE_DEPLOYMENT.md) — production topology and deployment.
- [Backup and recovery](BACKUP_AND_RECOVERY.md) — protected assets, backup and restore drills.
- [Security operations](SECURITY_OPERATIONS.md) — secrets, network boundaries and response.
- [Testing and certification](TESTING_AND_CERTIFICATION.md) — application and provider acceptance.
- [Final handover](FINAL_HANDOVER.md) — ownership and release handoff.

## Source-of-truth rule

Broker-native positions, orders, fills, balances and P&L are authoritative for broker state.
PostgreSQL is authoritative for ATLAS configuration, audit and attribution. The running
OpenAPI document at `/docs` is authoritative for exact request and response schemas.

Repository contributors also follow root `CONTRIBUTING.md`; automated coding and AI tools
follow root `AGENTS.md` before making changes.
