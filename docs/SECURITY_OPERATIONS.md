# ATLAS MARKETS — Security Operations

## Security boundary

Public ingress should expose HTTPS only. Do not publicly expose PostgreSQL `5432`, Redis `6379`, internal FastAPI, IBKR bridge `8766`, MT5 bridge `8765` or VNC.

## Identity and authorization

- Two roles only: `ADMIN` and `USER`.
- Public registration is disabled.
- Sessions are revocable and authentication activity is audited.
- Every resource query must remain user-scoped unless an ADMIN endpoint explicitly requires broader access.

## Secret management

- Provider credentials are encrypted at rest in broker profiles.
- `.env.oracle`, private keys, bridge tokens, OAuth secrets and database dumps stay outside Git.
- Rotate credentials after suspected exposure, staff/access changes or provider security events.
- Do not copy secrets into logs, screenshots, tickets or chat.

## Trading safety

- Simulation certification never grants live-money authorization.
- Keep `ALLOW_LIVE_TRADING=false` until a separate live certification is approved.
- Kill switch, provider/environment gates, risk limits and broker verification are independent controls.
- Shadow eligibility cannot enable execution.
- Bybit sells remain limited to reconciled ATLAS-managed inventory.

## Host maintenance

Ubuntu 20.04 has ended standard support. Plan a tested upgrade to a supported LTS release; take verified database and configuration backups first and validate broker GUI/bridge compatibility in a separate environment.

## Audit review

Review user changes, account activation, credential replacement, strategy changes, kill/restart actions, certification changes, automation actions and provider discrepancies. Preserve UTC timestamps and broker references.

## Incident response

1. Kill automation when execution integrity is uncertain.
2. Revoke exposed credentials/tokens.
3. Preserve logs and audit evidence.
4. Verify provider-native positions and orders.
5. Repair and test in simulation.
6. Re-enable only after reconciliation and documented approval.
