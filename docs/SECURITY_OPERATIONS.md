# ATLAS MARKETS v1 — Security Operations

## Network boundary

Expose HTTPS only. Never publicly expose PostgreSQL `5432`, Redis `6379`, internal FastAPI,
MT5 bridge `8765`, IBKR bridge `8766` or VNC. VNC is reached only through an SSH tunnel.

## Identity and secrets

- Roles are exactly `ADMIN` and `USER`; public registration is disabled.
- Sessions are revocable and authentication activity is audited.
- Resource access remains owner-scoped unless an ADMIN route explicitly permits more.
- Provider credentials are encrypted at rest.
- `.env.oracle`, SSH keys, bridge tokens, OAuth secrets, IBKR credentials and dumps stay out
  of Git, logs, screenshots and tickets.

## Trading safety

- Simulation certification never grants Live Money authority.
- Keep `ALLOW_LIVE_TRADING=false` until a separate release is approved.
- Kill switch, provider certification, risk controls and broker verification are independent.
- Shadow eligibility cannot submit an order.
- Bybit sells remain restricted to reconciled ATLAS-managed inventory.

## Incident response

1. Kill automation when execution integrity is uncertain.
2. Revoke exposed credentials and sessions.
3. Preserve UTC logs and audit evidence.
4. Verify provider-native positions, orders and fills.
5. Repair and validate in simulation.
6. Re-enable only after documented reconciliation.

Ubuntu 20.04 is beyond standard support. Upgrade to a supported LTS only through a separately
tested migration with verified database/configuration backups and broker GUI compatibility.

