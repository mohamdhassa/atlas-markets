# ATLAS MARKETS Agent Instructions

These instructions apply to automated coding and AI tools working anywhere in this repository.

## Baseline and scope

- Treat tag `v1.0.0` at `5ef08db6426876be6019541c45c0b3b3851f85eb` as the canonical
  application baseline and current `main` as the documentation/code integration branch.
- Build forward. Do not restore reverted versions, replace the frontend, reset production data
  or revive experimental branches unless the user explicitly authorizes that exact action.
- Preserve authentication, ADMIN/USER ownership, Bybit Testnet, IBKR Paper,
  portfolio/activity/P&L, shadow analytics and existing PostgreSQL data.

## Mandatory discovery

Before changing code, read `docs/DOCUMENTATION_INDEX.md`, the documents relevant to the task,
the affected implementation and its tests. Verify the actual branch, dirty worktree, migration
head and deployment target. Never assume an old transcript or branch is production truth.

## Safety and secrets

- Never print, commit or transmit `.env.oracle`, provider credentials, database passwords,
  bridge tokens, SSH keys, dumps or unredacted connection URLs.
- PostgreSQL production is `atlas_markets`; the older `atlas` database is not a migration target.
- Use migrations for schema changes and application workflows for data changes. Default
  administrative database work to read-only inspection.
- Live Money remains explicitly gated. Do not weaken provider, environment, certification,
  risk, kill-switch or broker-verification controls.
- Broker-native state is authoritative for positions, orders, fills, balances and P&L.

## Engineering requirements

- Make the smallest cohesive change and preserve unrelated work.
- Add regression tests for every behavior change.
- Validate in a production-equivalent container, including the full suite.
- For frontend changes, verify asset order, initial render, desktop/mobile layouts, navigation,
  loading/error/empty states and existing workflows.
- For provider changes, test failures, timeouts, duplicate protection and reconciliation.
- For database changes, update models, Alembic migration, ERD and recovery implications.
- Update documentation and release notes in the same pull request.

## Deployment

Do not deploy an unmerged or unverified commit. Before an app deployment, record the current
commit/image and create a versioned rollback image. Recreate only `app` unless the approved
change explicitly requires another component. Verify health, Alembic head, logs, providers and
one monitored reconciliation after deployment.
