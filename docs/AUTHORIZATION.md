# ATLAS MARKETS — Authentication and Authorization

## Roles

ATLAS MARKETS has exactly two application roles:

- `ADMIN`
- `USER`

There is no intermediate role hierarchy.

## Authentication model

Authentication uses opaque bearer session tokens backed by PostgreSQL.

Flow:

1. User submits username/password to `POST /auth/login`.
2. Password is verified against a salted PBKDF2-SHA256 hash.
3. A cryptographically random session token is generated.
4. Only an HMAC-SHA256 hash of the session token is stored in `user_sessions`.
5. The raw token is returned once to the client.
6. Protected requests send `Authorization: Bearer <token>`.
7. Logout revokes the server-side session immediately.

Sessions expire according to `SESSION_TTL_HOURS`.

## Password storage

Readable passwords are never stored. Password hashes use PBKDF2-HMAC-SHA256 with a per-password random salt.

## Tables

### users

Stores application identities, password hashes, role and active/disabled state.

### user_sessions

Stores hashed session tokens, expiration, revocation state and basic connection metadata.

### auth_audit_log

Records login attempts, successful logins, logout and user creation events.

## API

### Public

- `POST /auth/login`

### Authenticated

- `GET /auth/me`
- `POST /auth/logout`

### ADMIN only

- `GET /admin/users`
- `POST /admin/users`
- `GET /admin/ping`

## Bootstrap the first administrator

After migrations are current, run inside the application container:

```powershell
docker compose exec app python -m app.scripts.create_admin --username admin
```

The command prompts for a password. Use at least 12 characters.

For non-interactive local automation only, `--password` is also supported. Avoid placing real production passwords in shell history.

## Authorization rules

`ADMIN` can access platform-wide administration endpoints.

`USER` can authenticate but receives HTTP 403 for ADMIN endpoints.

Future account-scoped APIs must resolve allowed `profile_id` values from the authenticated user. Client-supplied profile IDs must never be trusted without ownership/authorization validation.

## Security notes

- `SESSION_SECRET` must be replaced with a strong secret before production.
- Session tokens are revocable because sessions are server-side.
- Failed and successful authentication attempts are audited.
- Disabled users cannot create or use sessions.
- Live trading remains independently controlled by server-side trading policy; authentication does not enable live trading.

---

# Current Security / Authorization Addendum — 2026-08-25

The original authentication and role model above remains in force. Later development adds external-provider ownership and execution-safety requirements without replacing the original model.

## Broker/account ownership

External broker/exchange accounts are represented by `BrokerProfile` records with a `user_id` owner.

Account-scoped operations must follow:

```text
authenticated identity
→ resolve/validate permitted BrokerProfile IDs
→ perform account-scoped operation
```

A client-provided profile ID is never sufficient authorization by itself.

`ADMIN` has explicit platform-wide administrative access where routes/services authorize it. `USER` remains restricted to owned/permitted resources.

## Expanded ADMIN / USER scope

ADMIN/Owner may manage users, provider profiles, strategy/risk configuration, integrations, automation/system controls and aggregate results. USER access remains scoped to the user's own permitted accounts, analysis, orders/positions, history and performance.

There are still only two application roles; later provider work does not introduce another role tier.

## Provider credential handling

The current BrokerProfile implementation stores encrypted credential material in fields such as:

- `api_key_encrypted`
- `api_secret_encrypted`
- `credential_blob_encrypted`
- `credentials_configured` (safe status flag)

Secrets/tokens must not be logged, returned by normal profile reads, or committed to Git/.env examples with real values.

## Live Money authorization remains separate

Authentication, ownership and ADMIN status do **not** by themselves authorize Live Money execution.

The current broker profile includes explicit safety state such as:

- `live_execution_enabled`
- `live_execution_armed_at`

Execution paths must also validate provider environment, account status, risk policy and global/server-side Live Money gates.

Current certification environments remain:

- Fusion MT5: Demo
- IBKR: Paper
- Bybit: Testnet

Unrestricted Live Money automatic execution is not certified.

## Bridge security

MT5 and IBKR use local Windows-side bridges. These should remain private/local rather than exposed as unauthenticated internet-facing execution APIs. IBKR Paper/simulation mode must be verified before certification orders, and duplicate TWS/IB Gateway client IDs should be avoided.

## Provider/regulatory restrictions

Provider errors indicating product/regulatory restrictions must be surfaced and respected. In particular, Bybit Testnet execution currently returns provider error `10024`; ATLAS must not attempt to bypass that restriction.

## Additional authorization testing expectations

New account/provider features should test:

- unauthenticated rejection;
- USER rejection from ADMIN-only routes;
- USER inability to read/mutate another user's broker profile/data;
- ADMIN authorized access;
- revoked/disabled session behavior;
- Live Money gate independence from login/role;
- secret/encrypted fields absent from normal API responses.
