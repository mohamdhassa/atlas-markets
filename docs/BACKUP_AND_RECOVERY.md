# ATLAS MARKETS v1 — Backup and Recovery

## Protected assets

- PostgreSQL data and Alembic revision.
- `.env.oracle`, encryption keys and provider credentials.
- reverse-proxy/TLS configuration.
- systemd units, firewall rules and broker bridge configuration.
- IB Gateway configuration, including the corrected per-profile Auto Restart settings.
- deployed Git commit, tag and Docker image identifier.

Secrets, private keys and database dumps never belong in Git.

## Database backup

Use PostgreSQL custom format and store it outside the repository:

```bash
mkdir -p "$HOME/atlas-backups"
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  > "$HOME/atlas-backups/atlas-$(date -u +%Y%m%dT%H%M%SZ).dump"
sha256sum "$HOME"/atlas-backups/atlas-*.dump
```

Use the protected environment's actual database name/user. Verify the file is non-empty.

## Restore discipline

1. Stop application writes and automation.
2. Preserve the current database before replacement.
3. Restore into an isolated validation database first.
4. Inspect `pg_restore --list` and critical table counts.
5. Confirm Alembic compatibility with the target image.
6. Restore production only after validation.
7. Reconcile all provider-native positions/orders after startup.

Redis is transient and rebuildable. Broker state is recovered from the provider, not assumed
from cached or stale application values. Conduct and record a restore drill at least monthly.

