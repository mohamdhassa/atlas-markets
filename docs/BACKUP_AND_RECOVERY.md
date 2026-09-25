# ATLAS MARKETS — Backup and Recovery

## What must be protected

- PostgreSQL data and Alembic version.
- `.env.oracle` and encryption key material.
- Reverse-proxy/TLS configuration.
- IBKR/MT5 bridge service definitions and firewall rules.
- Git commit/tag identifying every deployed application image.

Secrets and dumps must never be committed to Git.

## Database backup

Use PostgreSQL custom format and store the output outside the repository. Example pattern:

```bash
mkdir -p "$HOME/atlas-backups"
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  > "$HOME/atlas-backups/atlas-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

Use the actual container database user/name from the protected environment. Verify the resulting file is non-empty and generate a SHA-256 checksum.

## Restore principles

1. Stop application writes.
2. Preserve the damaged/current database before replacement.
3. Restore into a separate validation database first.
4. Run `pg_restore --list` and verify the expected schema.
5. Confirm Alembic revision compatibility with the intended application image.
6. Restore production only after validation and an explicit recovery decision.
7. Reconcile provider-native positions/orders after startup.

## Recovery objectives

- Application images: recoverable from Git commit plus Docker build.
- PostgreSQL: recoverable from the latest verified dump.
- Redis: disposable; rebuild transient state.
- Broker state: recover from provider-native truth, never from assumptions.

## Required recovery drill

At least monthly, restore the newest backup into an isolated PostgreSQL instance, run migrations/read checks, count critical tables, and document duration and failures. A backup is not certified until restoration succeeds.
