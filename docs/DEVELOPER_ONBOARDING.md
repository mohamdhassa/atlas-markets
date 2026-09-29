# ATLAS MARKETS v1 — Developer Onboarding

## Read first

1. `DOCUMENTATION_INDEX.md`
2. `CURRENT_STATUS.md`
3. `ARCHITECTURE.md`
4. `ERD.md` and `DATABASE_OPERATIONS.md`
5. `AUTHORIZATION.md`, `PROVIDERS.md` and `TESTING_AND_CERTIFICATION.md`
6. `OPERATIONS_RUNBOOK.md`, `SECURITY_OPERATIONS.md` and `FINAL_HANDOVER.md`
7. Repository `AGENTS.md` and `CONTRIBUTING.md`

## Canonical baseline

The application baseline is tag `v1.0.0` at commit
`5ef08db6426876be6019541c45c0b3b3851f85eb`. Documentation may advance on `main`, but new
application work must preserve the v1 frontend, PostgreSQL data, authentication,
administration, Bybit Testnet, IBKR Paper, portfolio/activity/P&L and shadow analytics.

Historical or reverted release branches are evidence, not deployment baselines.

## Repository map

| Path | Responsibility |
|---|---|
| `app/api/` | authenticated/public HTTP routes |
| `app/services/` | application workflows and provider orchestration |
| `app/brokers/` | provider bridge clients |
| `app/analysis/` | strategy and analytical logic |
| `app/db/models/` | SQLAlchemy persistence model |
| `app/static/` | canonical browser frontend |
| `migrations/` | Alembic schema history |
| `bridges/` and `tools/` | external execution-node utilities |
| `ops/` | production operational scripts |
| `tests/` | regression, integration and contract tests |
| `docs/` | product, data, security and operations truth |

## Local workflow

1. Branch from current `origin/main` in a clean worktree.
2. Inspect existing tests and ownership/security boundaries before editing.
3. Make the smallest cohesive change; do not replace established subsystems implicitly.
4. Add regression tests and documentation in the same change.
5. Run the full container test suite and targeted tests.
6. Review `git diff --check`, migrations, generated assets and secret exposure.
7. Open a pull request; merge only after validation.

## Change-specific requirements

- Database: model plus Alembic migration, upgrade validation and ERD update.
- API: authorization, ownership, validation, error contract and API-reference update.
- Provider: independent environment/certification gates and broker-truth reconciliation.
- Strategy: historical and forward/shadow evidence; no performance guarantee.
- Frontend: preserve current navigation/functionality, validate desktop/mobile and prevent
  unstyled-content or asset-order regressions.
- Operations: retain app-only deployment isolation and a versioned rollback image.

## Production boundary

Developers do not manually change production rows to make tests pass. Production access uses
least privilege and private tunnels. Provider credentials, `.env.oracle`, database dumps and
SSH keys never enter Git, prompts, logs, screenshots or issue bodies.

## Definition of done

- behavior and acceptance criteria are explicit;
- tests pass in the production-equivalent container;
- schema and API contracts are compatible or intentionally migrated;
- security, ownership and simulation/live-money gates remain intact;
- documentation and release notes match the delivered behavior;
- deployment and rollback steps are known;
- post-deployment health and provider reconciliation are recorded.
