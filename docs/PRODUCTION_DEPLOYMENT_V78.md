# v78 Production Deployment Certificate

## Release identity

- Release: v78
- Git commit: `21d9fd4205ae7c5f24c1c310895c5d3f1651640f`
- Pull request: #93
- Deployment date: 2026-09-23 UTC
- Environment: Oracle Cloud production
- Application image: `sha256:438388b828ecb0cc415e7237f8945bfa22f86976b65996ea722c779aa50bf509`
- Rollback image: `atlas-markets-app:v77-rollback`
- Database migration: `20260913_0017 (head)`

## Validation evidence

The exact PR branch was built in an isolated Oracle worktree and the complete containerized test suite finished with no failures and four expected skips. The production Compose image subsequently completed its unit suite with no failures.

Post-deployment verification confirmed:

- application container running and Docker health status `healthy`;
- `GET /health` returned HTTP 200 with database and Redis both `ok`;
- `GET /api/system` returned HTTP 200 and reported the consolidated-core production runtime;
- PostgreSQL and Redis remained running and were not recreated;
- startup migrations completed successfully;
- Uvicorn startup completed without application errors.

## Safety boundary

v78 does not enable Live Money. Execution remains limited to certified routes and the runtime continues to report `live_money_policy=EXPLICITLY_GATED`.

Certified simulation scope includes:

- Fusion Markets MT5 Demo, subject to runtime terminal authorization;
- Interactive Brokers Paper;
- Bybit Testnet/Demo Spot with managed-inventory and reconciliation safeguards.

## Rollback

The pre-deployment application image is retained as:

```text
atlas-markets-app:v77-rollback
```

Rollback must replace only the application service unless database recovery is independently required. Do not restart PostgreSQL, Redis, or broker bridges as part of a routine application rollback.

## Operational notes

- Production ATLAS MARKETS is bound to `127.0.0.1:8100`.
- The canonical health endpoint is `/health`, not `/api/health`.
- Production Compose configuration is supplied by `.env.oracle`; do not source this file as a shell script because values may contain spaces.
