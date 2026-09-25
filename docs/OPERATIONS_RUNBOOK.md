# ATLAS MARKETS — Production Operations Runbook

## Canonical production commands

```bash
cd ~/atlas-markets
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml ps
curl --fail --silent --show-error http://127.0.0.1:8100/health
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml exec -T app alembic current
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml logs --tail=100 app
```

Expected v82 migration: `20260925_0019 (head)`.

## Safe deployment sequence

1. Fetch and verify the intended commit.
2. Build an isolated image.
3. Run the complete test suite.
4. Tag the current production image as the versioned rollback image.
5. Build the production app image.
6. Recreate only `app`; do not restart PostgreSQL, Redis or broker bridges unnecessarily.
7. Wait for Docker health to become healthy.
8. Verify migration, application health, logs and provider readiness.
9. Run one shadow scan and inspect provider totals.

## Rollback

Application rollback is appropriate when startup, migrations or smoke tests fail. Record the failing image and logs first. Retag the known rollback image as `atlas-markets-app`, recreate only the app, and verify health. Database migrations must be assessed separately; do not blindly downgrade a database containing newly written data.

## Shadow scan verification

```bash
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml exec -T app \
  python -c "import asyncio; from app.services.shadow_monitor import run_shadow_scan; print(asyncio.run(run_shadow_scan()))"
```

The returned `providers` map proves configured coverage. `errors: []` means the run completed without provider/analysis failures. `skipped` requires inspection through the coverage API/frontend.

## Incident priorities

1. Engage the kill switch if execution safety is uncertain.
2. Preserve broker and application evidence.
3. Confirm broker-native positions/orders.
4. Diagnose application, database, Redis and provider bridges independently.
5. Recover the smallest failed component.
6. Reconcile broker truth before restarting automation.

## Known non-fatal conditions

- IBKR code `366`: cancelled or missing historical query context.
- IBKR delayed market-data warnings: connected but not execution-quality real-time subscription.
- Four skipped integration tests in an isolated Docker run: expected when external services are unavailable.
- First health request during container startup can return an empty response; wait for Docker health.
