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
