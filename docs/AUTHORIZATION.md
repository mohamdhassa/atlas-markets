# ATLAS MARKETS — Authorization

Last updated: 2026-08-30

ATLAS MARKETS has exactly two application roles: `ADMIN` and `USER`.

## ADMIN

ADMIN has system-wide access to:

- user creation and administration;
- all external broker profiles;
- provider credentials/configuration workflows;
- strategy/risk administration;
- automation state, kill/restart and monitored scans;
- bulk AUTO_TRADE promotion for eligible certified simulation routes;
- system-wide broker/performance/action reporting;
- integration and release-readiness views.

ADMIN access does **not** bypass provider certification, Live Money gates, broker restrictions, risk limits or the kill switch.

### Bulk AUTO_TRADE authorization

`POST /strategies/symbols/auto-trade/eligible` is ADMIN-only.

The endpoint may seed/promote symbols only when the assigned BrokerProfile is:

- on a certified simulation route;
- enabled;
- active;
- connected;
- credentials-configured.

Current certified routes are Fusion MT5 Demo and IBKR Paper. Bybit is returned as blocked until provider-side execution certification succeeds. Live Money routes are never bulk-promoted.

## USER

USER is restricted to user-owned/account-scoped data and operations. A USER may view and manage permitted own strategy/account data but cannot use ADMIN bulk automation controls, create other users, or operate system-wide automation controls.

## Authentication

- login: `POST /auth/login`
- current user: `GET /auth/me`
- logout/revocation: `POST /auth/logout`
- bearer access token is required for authenticated API routes.
- user sessions are persisted/revocable.
- public self-registration is disabled.

## BrokerProfile ownership

A BrokerProfile belongs to one user. Normal USER queries are filtered by ownership. ADMIN can inspect/manage system-wide profiles.

Provider credentials are encrypted at rest in BrokerProfile encrypted fields. API/UI responses must never expose decrypted secrets.

## Execution authorization layers

A strategy being `AUTO_TRADE` is necessary but not sufficient for order submission. Automatic execution additionally requires:

1. automation engine enabled;
2. kill switch not active;
3. simulation execution enabled;
4. provider/environment certified;
5. BrokerProfile ready;
6. valid strategy signal/order proposal;
7. risk/preflight approval;
8. duplicate/position/open-order checks;
9. broker-native preflight where supported;
10. broker acceptance and fill confirmation.

This layered model is intentional. ADMIN is not a permission to skip these controls.

## Live Money

`ALLOW_LIVE_TRADING=false` remains the deployment default for the simulation period. Live Money requires a separate certification and explicit configuration; it is not enabled through role elevation alone.
