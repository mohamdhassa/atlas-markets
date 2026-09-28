# ATLAS MARKETS v1 — Production Operations Runbook

## Canonical baseline

- Git tag: `v1.0.0`
- Git commit: `5ef08db6426876be6019541c45c0b3b3851f85eb`
- Application health: `http://127.0.0.1:8100/health`
- IBKR bridge: `http://127.0.0.1:8766`

## Routine checks

```bash
cd ~/atlas-markets
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml ps
curl --fail --silent --show-error http://127.0.0.1:8100/health
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml exec -T app alembic current
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml logs --tail=100 app
```

Provider health is checked independently. Application health does not prove that a broker
session is authenticated.

## Safe app-only deployment

1. Fetch and verify the intended commit.
2. Build and run the full test suite in the candidate image.
3. Tag the current production image with a versioned rollback name.
4. Build the production app image.
5. Recreate only `app` with `--no-deps --force-recreate`.
6. Wait for Docker health to report healthy.
7. Verify `/health`, Alembic head, logs and provider readiness.
8. Run one monitored scan and reconcile provider-native truth.

Do not restart PostgreSQL, Redis or broker bridges during an app-only deployment.

## Incident order

1. Engage the kill switch if execution integrity is uncertain.
2. Preserve application, watchdog and broker evidence.
3. Check provider-native positions, orders and fills.
4. Diagnose app, PostgreSQL, Redis and each provider independently.
5. Recover the smallest failed component.
6. Reconcile state before automation resumes.

## Rollback

Record the failing commit, image and logs first. Restore the known rollback image and recreate
only the app. Database downgrade is a separate decision; never blindly downgrade a database
that may contain data written by a newer schema.

## Non-fatal IBKR notices

- Code `366`: cancelled/missing historical-query context.
- Code `10167`: delayed market data is being used.
- Code `2176`: fractional-size compatibility warning.

These notices do not by themselves mean the Gateway or account is disconnected.

