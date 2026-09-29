# ATLAS MARKETS v1 — Documentation Index

This index is the entry point for the canonical `v1.0.0` baseline at Git commit
`5ef08db6426876be6019541c45c0b3b3851f85eb`.

## Product and design

- [Architecture](ARCHITECTURE.md) — components, trust boundaries and runtime flow.
- [ERD](ERD.md) — PostgreSQL entities, relationships and ownership rules.
- [ERP operating model](ERP_OPERATING_MODEL.md) — ERP-style control, workflow and audit model.
- [Authorization](AUTHORIZATION.md) — ADMIN/USER authority and execution gates.
- [Providers](PROVIDERS.md) — broker and data-provider responsibilities.

## Use and administration

- [User and administrator guide](USER_ADMIN_GUIDE.md) — daily use and interpretation.
- [Developer onboarding](DEVELOPER_ONBOARDING.md) — repository map, workflow and definition of done.
- [API reference](API_REFERENCE.md) — operational endpoint families and roles.
- [Current status](CURRENT_STATUS.md) — deployed baseline and known limitations.
- [Roadmap](ROADMAP.md) — work after the v1 baseline.

## Production operations

- [Database operations](DATABASE_OPERATIONS.md) — production identity, pgAdmin SSH access and schema changes.
- [Operations runbook](OPERATIONS_RUNBOOK.md) — health, deployment, incident and rollback procedures.
- [IBKR continuity runbook](IBKR_CONTINUITY.md) — Gateway, bridge, watchdog and VNC recovery.
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
