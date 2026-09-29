# ATLAS MARKETS v1 — Database Operations

## Production identity

| Item | Canonical value |
|---|---|
| Application database | `atlas_markets` |
| Database user | `atlas` |
| PostgreSQL service/container | `postgres` / `atlas-markets-prod-postgres` |
| Internal port | `5432` |
| Verified Alembic head | `20260925_0019` |
| Verified application-table count | 23 including `alembic_version` |

The Oracle host also contains an older database named `atlas`. It belongs to the earlier
project and is not the ATLAS MARKETS v1 application database. Never infer the target from a
pgAdmin registration name: verify `current_database()` and the Alembic revision.

## Source-of-truth verification

Run this from the application container so the check uses the exact production `DATABASE_URL`
without printing its password:

```bash
cd ~/atlas-markets
docker compose --env-file .env.oracle -f docker-compose.oracle.prod.yml exec -T app \
  python -c "from sqlalchemy import create_engine,text; from app.core.config import get_settings; e=create_engine(get_settings().database_url); c=e.connect(); print(c.execute(text('select current_database()')).scalar()); print(c.execute(text('select version_num from alembic_version')).scalar()); c.close()"
```

Expected output is `atlas_markets` and `20260925_0019`.

## pgAdmin through its built-in SSH tunnel

PostgreSQL must remain private. Configure a saved pgAdmin server instead of publishing port
`5432` or keeping a separate PowerShell tunnel open.

Connection tab:

| Field | Value |
|---|---|
| Host | current private IP of `atlas-markets-prod-postgres` |
| Port | `5432` |
| Maintenance database | `atlas_markets` |
| Username | `atlas` |
| Password | protected `POSTGRES_PASSWORD`; save only in pgAdmin's password store |

SSH Tunnel tab:

| Field | Value |
|---|---|
| Use SSH tunneling | Yes |
| Tunnel host | Oracle public IP from protected operations configuration |
| Tunnel port | `22` |
| Username | `ubuntu` |
| Authentication | Identity file |
| Identity file | operator's private Oracle SSH key |

Obtain the current container IP without exposing secrets:

```powershell
ssh -i "<SSH_KEY_PATH>" ubuntu@<ORACLE_PUBLIC_IP> `
  "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' atlas-markets-prod-postgres"
```

Docker may assign another private IP after network recreation. If pgAdmin times out, obtain the
new address and update only the Connection host. Closing pgAdmin closes its administrative
tunnel; it does not stop PostgreSQL or ATLAS MARKETS.

## Read-only identity test

```sql
SELECT current_database(), current_user, version_num, now()
FROM alembic_version;
```

The result must identify `atlas_markets`, user `atlas`, and revision `20260925_0019` before
operational analysis continues.

## Safe inspection

```sql
SELECT relname AS table_name,
       n_live_tup AS estimated_rows,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
ORDER BY relname;
```

Use pgAdmin for read-only inspection by default. Do not display encrypted credential columns,
paste secrets into tickets/chat, or run `UPDATE`, `DELETE`, `TRUNCATE`, `DROP`, ad-hoc DDL or
manual financial corrections against production.

## Schema changes

1. Change SQLAlchemy models and add an Alembic migration in the same branch.
2. Test upgrade from the current head on disposable data.
3. Test application behavior and downgrade only when the migration genuinely supports it.
4. Back up production and record the current image/revision.
5. Deploy through the reviewed release procedure; never use pgAdmin to bypass migrations.
6. Verify Alembic head, table constraints, application health and provider reconciliation.

## Database families

- Core ownership: `users`, `user_sessions`, `auth_audit_log`, `broker_profiles`.
- Strategy/execution evidence: `strategy_profiles`, `symbol_strategies`, `signals`,
  `risk_profiles`, `risk_events`, `automation_state`, `automation_scans`, `automation_actions`.
- Intelligence/reporting: `historical_candles`, `historical_backtest_runs`, `news_articles`,
  `daily_account_reports`, `shadow_observations`, `shadow_scan_events`.
- Provider inventory: `bybit_managed_inventory`.
- Legacy-compatible internal simulation: `paper_wallets`, `paper_positions`, `paper_orders`.

Multiple logical families do not mean multiple projects. Foreign keys connect the production
ownership and execution lineage described in `ERD.md`.
