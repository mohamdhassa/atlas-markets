# ATLAS MARKETS — Oracle Cloud Deployment

Last updated: 2026-08-30

## Target architecture

ATLAS MARKETS v1.1 uses Oracle Cloud Infrastructure (OCI) as the always-on application and data tier.

```text
Internet
  |
  | HTTPS 443
  v
Reverse proxy / TLS on OCI Ubuntu
  |
  | localhost:8000
  v
ATLAS FastAPI container
  |-- PostgreSQL 17 container (private Docker network, persistent volume)
  |-- Redis 7 container (private Docker network, persistent volume)
  |-- Twelve Data / Bybit HTTPS APIs
  |-- private VPN -> MT5 execution node
  `-- private VPN -> IBKR execution node
```

The PostgreSQL and Redis ports are not published to the Internet. The FastAPI container is bound to `127.0.0.1:8000`; a reverse proxy should expose only HTTPS.

## Why broker bridges are separate

Fusion MT5 depends on the MetaTrader 5 terminal and should run on a Windows execution node. The current IBKR adapter connects to TWS/IB Gateway and can also be operated as a separate execution node. The Oracle server must reach those bridges over a private VPN address. Do not expose ports 8765 or 8766 to the public Internet.

For an unattended multi-week simulation, use an always-on Windows execution node or Windows VPS. Using a personal laptop means broker execution stops whenever that machine sleeps, reboots, loses Internet access, or closes MT5/TWS/IB Gateway.

## OCI network rules

Recommended public ingress:

- TCP 22: SSH, restricted to the administrator IP whenever possible.
- TCP 80: HTTP only for ACME redirect/certificate issuance if needed.
- TCP 443: HTTPS public application access.

Do not expose PostgreSQL 5432, Redis 6379, FastAPI 8000, MT5 bridge 8765, or IBKR bridge 8766 publicly.

## Server preparation

Recommended OS: supported Ubuntu LTS image.

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

All three containers must be healthy before the reverse proxy is enabled.

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
- `tools/mt5_bridge.py` running.
- Bridge bound only to a private/VPN interface or protected by host firewall and bridge token.

The Oracle BrokerProfile credential blob must use the private VPN URL, for example `http://10.x.x.x:8765`.

### Interactive Brokers

Required on the IBKR execution node:

- TWS or IB Gateway logged into Paper.
- API socket access enabled.
- `tools/ibkr_bridge.py` running.
- Bridge bound only to private/VPN reachability.
- Account remains Paper during simulation.

The Oracle BrokerProfile credential blob must use the private VPN URL for port 8766.

IBKR real-time market data subscriptions are strongly recommended for broad automated U.S. stock/ETF Paper testing. The bridge can request delayed data, but delayed data is not a substitute for execution-quality market data.

## HTTPS

Use Nginx, Caddy, or an OCI load balancer to terminate TLS and proxy to `http://127.0.0.1:8000`.

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

- MT5 Demo may auto-trade.
- IBKR Paper may auto-trade under certified safeguards.
- Bybit remains blocked until Bybit permits the product/account and ATLAS re-certifies the route.
- Twelve Data remains data-only.
- Live Money remains gated.
