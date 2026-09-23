# ATLAS MARKETS — Operational Handover

Last updated: 2026-09-23
Production checkpoint: v77 `a141d2c`

## Purpose

ATLAS MARKETS is an Oracle-hosted multi-provider market analysis, simulation, automation and reporting platform. Current production work is simulation-only: Bybit Testnet, IBKR Paper and provider-specific Demo routes. Live Money remains separately gated.

## Current production stack

- FastAPI application/frontend
- PostgreSQL 17
- Redis 7
- Oracle Cloud production host
- IB Gateway Paper + private IBKR bridge on Oracle
- Bybit Testnet HTTPS API
- Twelve Data market/historical data
- Fusion MT5 Demo integration with terminal authorization dependency

## Current checkpoints

- v74: Bybit Spot metadata/execution isolation
- v75: Live Activity Log
- v76: Bybit managed SELL wallet reconciliation
- v77: operational frontend visibility
- Production `main`: `a141d2c`

## Current broker state

Bybit Testnet is a managed Spot simulation route. ATLAS tracks its own managed inventory and must not silently sell unrelated broker wallet holdings. The v76 reconciliation path only reduces ATLAS managed quantity to broker-observed balance before a SELL; it does not increase managed inventory from external holdings. The next natural ETH/SOL SELL remains the runtime proof point for the reconciliation fix.

IBKR Paper is connected through the Oracle-hosted Gateway and bridge. Strategy/risk BLOCK is distinct from provider unavailability. Gateway authentication can still require manual IBKR login/2FA after security/session resets. Do not automate or bypass 2FA.

## Deployment rule

Use the production app-only rebuild when only application code changes:

```bash
cd ~/atlas-markets
git checkout main
git fetch origin
git status --short
git reset --hard origin/main
docker compose -f docker-compose.yml -f docker-compose.oracle.prod.yml up -d --build --no-deps app
sleep 10
curl -s http://127.0.0.1:8100/health
echo
```

Before reset, inspect `git status --short`. Production-only untracked files must not be deleted or overwritten, including the Oracle production compose override and operational backup artifacts.

## Testing rule

Prefer an isolated worktree and disposable container. Do not use a Compose test command that can recreate the production PostgreSQL service.

```bash
git fetch origin
rm -rf /tmp/atlas-test
git worktree prune
git worktree add --detach /tmp/atlas-test origin/<branch>
docker run --rm -e PYTHONPATH=/app -v /tmp/atlas-test:/app -w /app atlas-markets-app pytest -q
```

## Operational verification

After deployment verify:
- `/health` is OK;
- latest automation scans continue;
- provider/account states are truthful;
- broker fills are not inferred from decision rows;
- Bybit reconciliation is verified only after a natural SELL;
- IBKR API port/bridge recover correctly after any Gateway authentication event;
- Live Money remains disabled.

## Frontend behavior

Live Activity is broker-aware. Decision-only rows show `N/A · no broker fill` for execution-only fields. v77 also improves provider-unavailable/auth attention visibility and reconciliation markers.

## Security

Never commit or paste credentials, API secrets, session tokens, 2FA codes, SSH private keys or database dumps. Keep PostgreSQL, Redis, broker bridge ports, IBKR API and VNC private. VNC should be reached through an SSH tunnel.

## Remaining work

- natural Bybit SELL reconciliation verification;
- IBKR restart/auth observation;
- managed-vs-external portfolio visibility;
- continued multi-week simulation measurement;
- documentation/architecture refresh after each meaningful production change.

Live Money requires a separate future certification and explicit human decision; simulation deployment does not authorize it.
