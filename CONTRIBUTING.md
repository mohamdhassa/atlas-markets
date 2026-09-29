# Contributing to ATLAS MARKETS

ATLAS MARKETS is a production trading-operations system. Correctness, traceability and safe
provider behavior take priority over broad rewrites.

## Workflow

1. Start from current `origin/main` in a dedicated branch/worktree.
2. State scope, acceptance criteria and affected trust boundaries.
3. Preserve unrelated user changes and the canonical v1 frontend/data model.
4. Implement code, tests, migration and documentation as one cohesive change.
5. Run targeted tests and the full container suite.
6. Open a pull request with risk, validation, deployment and rollback notes.

## Commit and review rules

- Keep commits focused and reviewable.
- Never commit secrets, private keys, `.env.oracle`, dumps or production exports.
- Never edit production data as a substitute for a migration or code fix.
- Do not broaden simulation certification into Live Money authority.
- Do not treat provider availability as proof of execution readiness.
- Reconcile positions, orders, fills, balances and P&L against broker-native truth.

## Required documentation

Update the relevant architecture, ERD, API, provider, operations, security, user/admin and
release documents whenever their contracts change. New developers begin with
`docs/DEVELOPER_ONBOARDING.md`; automated tools follow `AGENTS.md`.
