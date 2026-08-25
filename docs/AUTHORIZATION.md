# ATLAS MARKETS — Authentication and Authorization

Last reconciled: 2026-08-25.

## Roles

ATLAS MARKETS has exactly two application roles:

- `ADMIN`
- `USER`

There is no intermediate application role hierarchy.

## Authentication model

Authentication uses opaque bearer session tokens backed by PostgreSQL.

Flow:

1. User submits username/password to `POST /auth/login`.
2. Password is verified against the stored salted password hash.
3. A cryptographically random session token is generated.
4. Only the protected/hash representation required by the server-side session model is persisted.
5. The raw bearer token is returned to the client for authenticated requests.
6. Protected requests send `Authorization: Bearer <token>`.
7. Logout/revocation invalidates the server-side session.

Session lifetime is controlled by application configuration.

## Application identity tables

### `users`

Stores application identity, password hash, role and active/disabled state.

### `user_sessions`

Stores revocable server-side session information and expiration/security metadata.

### `auth_audit_log`

Records authentication/security events such as login attempts and administrative identity actions supported by the implementation.

## Broker/account ownership

External execution accounts are represented by `BrokerProfile` records.

Each broker profile has a `user_id` owner and operational fields including provider, environment, external account reference, enabled/active state, encrypted credentials, connection/sync state and Live Money gates.

Authorization rule:

```text
authenticated user
      ↓
resolve permitted BrokerProfile IDs
      ↓
account-scoped service/API operation
```

A client-provided profile ID is never sufficient authorization by itself.

`ADMIN` may perform explicitly authorized platform-wide operations. `USER` access must remain constrained to the user's own permitted resources.

## ADMIN capabilities

The intended ADMIN/Owner role has platform-wide control over:

- users;
- external provider/broker profiles;
- system/integration state;
- strategy configuration;
- risk configuration;
- automation/engine controls;
- kill/restart/safety controls where implemented;
- aggregate dashboards/results;
- viewing user results for administration.

ADMIN authority does **not** automatically bypass execution safety or Live Money gates.

## USER capabilities

The intended USER role can access the user's own permitted:

- provider/account state;
- balances/equity;
- positions/orders/executions where exposed;
- signals/analysis;
- performance/history;
- permitted account controls.

Users must not be able to enumerate or mutate another user's broker profiles or trading data by changing IDs in frontend/API requests.

## Public registration

Public self-registration is not part of the current intended security model. User creation is an administrative function unless a future approved requirement explicitly changes this decision.

## Bootstrap administrator

For a new local/development database, use the repository's administrator creation script, for example:

```powershell
docker compose exec app python -m app.scripts.create_admin --username admin
```

Use a strong password and avoid putting production credentials in shell history.

## Provider credential security

The current `BrokerProfile` ORM stores encrypted provider credential fields directly on the profile (`api_key_encrypted`, `api_secret_encrypted`, `credential_blob_encrypted`) together with the safe boolean `credentials_configured`.

Rules:

- never log readable API secrets/tokens;
- never return encrypted credential blobs as normal account API data;
- do not store new provider secrets in plaintext columns;
- do not commit `.env` secrets or generated OAuth/access tokens to Git;
- rotate any credential exposed during development.

## Live Money authorization is separate

Authentication and ADMIN role do not by themselves authorize Live Money trading.

The broker profile includes explicit live-safety state:

- `live_execution_enabled`
- `live_execution_armed_at`

Execution code must additionally validate provider environment, account state, risk policy and any other required server-side gate.

Current certification policy:

- Fusion MT5 execution certification: Demo only;
- IBKR execution certification: Paper only;
- Bybit execution work: Testnet only and currently provider-blocked by `10024`;
- unrestricted Live Money automatic execution: not certified.

## Bridge security

MT5 and IBKR use local Windows-side bridges. These bridges should remain local/private and should not become unauthenticated internet-facing execution APIs.

For IBKR, simulation/Paper mode must be verified before certification orders. Duplicate TWS/IB Gateway client IDs should be avoided.

## Security invariants

1. Disabled users cannot retain normal authenticated access.
2. Account ownership is enforced server-side.
3. ADMIN access is explicit, not an accidental missing ownership filter.
4. Provider credentials remain encrypted/server-side.
5. Strategy/AI decisions cannot bypass risk or environment gates.
6. Live Money requires explicit server-side authorization beyond login/role.
7. Regulatory/provider restrictions are surfaced, not bypassed.
8. Authentication/security events should remain auditable.

## Testing expectations

Authorization tests should cover at minimum:

- unauthenticated rejection;
- USER rejection from ADMIN-only routes;
- USER inability to access another user's broker profile/data;
- ADMIN permitted administrative access;
- disabled/revoked session behavior;
- Live Money gate independence from role;
- secret fields absent from normal API responses.

Any new account-scoped endpoint must add ownership/authorization tests with the feature rather than deferring them to release.
