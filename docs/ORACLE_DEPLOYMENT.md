# ATLAS MARKETS — Oracle Cloud Deployment

Last updated: 2026-09-05

## Target architecture

ATLAS MARKETS v1.1 uses Oracle Cloud Infrastructure (OCI) as the always-on application and data tier. IBKR Paper is now also hosted directly on the Oracle ARM64 production host.

```text
Internet
  |
  | HTTPS 443
  v
Reverse proxy / TLS on OCI Ubuntu
  |
  v
ATLAS FastAPI container
  |-- PostgreSQL 17 container (private Docker network, persistent volume)
  |-- Redis 7 container (private Docker network, persistent volume)
  |-- Twelve Data / Bybit HTTPS APIs
  |-- IBKR HTTP bridge :8766 (private)
  |     `-- IB Gateway Paper API 127.0.0.1:4002
  `-- private relay/VPN -> Windows MT5 execution node
```

The PostgreSQL and Redis ports are not published to the Internet. Public application access is terminated through the reverse proxy/TLS layer; broker bridges remain private.

## Broker execution architecture

Fusion MT5 depends on the native MetaTrader 5 Windows terminal and remains a Windows execution-node dependency. A personal Windows PC is not an acceptable final 24/7 execution node because MT5 stops being reachable when that PC sleeps, shuts down, loses Internet access, closes MT5, stops the bridge, or stops its relay/tunnel.

IBKR Paper has been migrated to the Oracle ARM64 host using the official ARM64 IB Gateway. The production path is:

```text
ATLAS app -> IBKR HTTP bridge :8766 -> IB Gateway 127.0.0.1:4002 -> IBKR Paper
```

IB Gateway is displayed through Xvfb/Fluxbox and its runtime is managed by systemd. See `docs/IBKR_ORACLE_RUNBOOK.md` for recovery and authentication procedures.

## OCI network rules

Recommended public ingress:

- TCP 22: SSH, restricted to the administrator IP whenever possible.
- TCP 80: HTTP only for ACME redirect/certificate issuance if needed.
- TCP 443: HTTPS public application access.

Do not expose PostgreSQL 5432, Redis 6379, FastAPI internal ports, MT5 bridge/relay ports, IBKR API 4002, VNC 5901, or IBKR bridge 8766 publicly.

## Server preparation

Recommended OS for future deployments: a supported Ubuntu LTS image. The current production host is ARM64 and has been verified with the ARM64 IB Gateway build.

Install Git, Docker Engine and Docker Compose plugin, then clone the repository.

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
# Install Docker from Docker's supported Ubuntu repository/package instructions.
sudo usermod -aG docker $USER
```

Reconnect after adding the user to the docker group.

## Application setup

```bash
git clone https://github.com/mohamdhassa/atlas-markets.git
cd atlas-markets
cp .env.oracle.example .env.oracle
chmod 600 .env.oracle
```

Generate unique production secrets. `ALLOW_LIVE_TRADING` must remain `false` during the multi-week simulation.

The same PostgreSQL password must be used in `POSTGRES_PASSWORD`, `DATABASE_URL`, and `TEST_DATABASE_URL`.

## Start the Oracle stack

```bash
docker compose --env-file .env.oracle -f docker-compose.oracle.yml up -d --build
docker compose --env-file .env.oracle -f docker-compose.oracle.yml ps
docker compose --env-file .env.oracle -f docker-compose.oracle.yml exec app alembic current
docker compose --env-file .env.oracle -f docker-compose.oracle.yml exec app python -m pytest -q
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/system
```

All required containers must be healthy before the reverse proxy is enabled.

## Database migration from local v1.0

Copy the private `atlas-markets-v1.0.0.dump` to the server using SCP/SFTP. Do not commit it to Git.

For a clean new production database, start the stack first so PostgreSQL is created, then restore intentionally during a maintenance window. A typical custom-format restore is:

```bash
docker compose --env-file .env.oracle -f docker-compose.oracle.yml stop app
docker compose --env-file .env.oracle -f docker-compose.oracle.yml exec -T postgres \
  pg_restore -U atlas -d atlas_markets --clean --if-exists --no-owner < /secure/path/atlas-markets-v1.0.0.dump
docker compose --env-file .env.oracle -f docker-compose.oracle.yml up -d app
```

Take a fresh Oracle-side backup immediately after a successful restore.

## Broker execution nodes

### Fusion MT5

Required on the Windows execution node:

- Fusion Markets MT5 Demo logged in.
- Algo Trading enabled.
- Secured Windows MT5 bridge running.
- Bridge bound only to localhost/private reachability and protected by its bridge token.
- Persistent private relay/VPN/tunnel from Oracle.

The final 24/7 target is an always-on Windows VPS/VM rather than the administrator's personal PC.

### Interactive Brokers Paper on Oracle

Verified production components:

- IB Gateway 10.45 Stable ARM64 installed at `/home/ubuntu/Jts/ibgateway/1045`.
- Xvfb virtual display `:99`.
- Fluxbox desktop.
- IB Gateway Paper API socket on `127.0.0.1:4002`.
- Docker IBKR HTTP bridge on port `8766`, connecting to localhost port 4002 with client ID 27.
- Paper account `DUR980544`.

The following systemd services are enabled at boot:

```text
atlas-ibkr-xvfb.service
atlas-ibkr-fluxbox.service
atlas-ibkr-gateway.service
```

IBKR may still require manual authentication/2FA after a restart, logout, maintenance window or security reset. Service auto-start must not be confused with authenticated-session auto-login. Use the localhost-only VNC + SSH-tunnel procedure in `docs/IBKR_ORACLE_RUNBOOK.md` when authentication is required.

IBKR real-time market data subscriptions are strongly recommended for broad automated U.S. stock/ETF Paper testing. The bridge can request delayed data, but delayed data is not a substitute for execution-quality market data.

## Production integration verification

Use the production application container to verify all configured providers:

```bash
docker exec atlas-markets-prod-app python -m app.scripts.verify_integrations
```

On 2026-09-05 the production environment returned PASS for:

```text
TWELVE_DATA
MT5 DEMO
BYBIT TESTNET
IBKR PAPER
```

This confirms provider connectivity at that verification point; it does not remove the MT5 personal-PC dependency or IBKR's periodic authentication requirements.

## HTTPS

Use Nginx, Caddy, or an OCI load balancer to terminate TLS and proxy to the private FastAPI endpoint.

The public application should be HTTPS-only. Keep `/docs` exposure under review because FastAPI interactive API documentation can reveal operational endpoints even when authentication is required.

## Backups

At minimum:

- daily PostgreSQL custom-format dump;
- retain multiple generations;
- keep at least one copy off the Oracle VM;
- retain Git tags/releases separately;
- never include `.env.oracle` or database dumps in Git.

Example:

```bash
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
docker compose --env-file .env.oracle -f docker-compose.oracle.yml exec -T postgres \
  pg_dump -U atlas -d atlas_markets -Fc > backups/atlas-markets-$STAMP.dump
```

## Upgrade procedure

```bash
cd atlas-markets
git pull origin main
docker compose --env-file .env.oracle -f docker-compose.oracle.yml build app
docker compose --env-file .env.oracle -f docker-compose.oracle.yml up -d app
docker compose --env-file .env.oracle -f docker-compose.oracle.yml exec app alembic current
docker compose --env-file .env.oracle -f docker-compose.oracle.yml exec app python -m pytest -q
```

Do not automatically enable Live Money as part of an upgrade.

## Simulation release rule

Oracle deployment changes hosting, not certification. During the observation period:

- MT5 Demo may auto-trade only under its separately certified safeguards and remains dependent on its Windows execution node.
- IBKR Paper may auto-trade under certified safeguards.
- Bybit Testnet remains a simulation route and must remain independently certified for execution behavior.
- Twelve Data remains data-only.
- Live Money remains gated.
