# Multi-user onboarding and isolated broker connections

## Delivered boundary

ADMIN creates USER/ADMIN logins, changes roles, resets passwords and suspends or
restores user access in Users. Last-active-admin protections remain. Suspension
revokes login sessions through the existing audited workflow and new automated
entry paths recheck the owner's active state. IBKR protection/reconciliation
workers are not disabled or asked to liquidate positions. Restoration resumes
eligibility under existing account, strategy and global controls; it does not
bypass certification or Live gates. Password resets revoke sessions; role
checks continue to use the current database role.

Accounts is now a complete responsive connection workspace for both roles.
USER sees owned accounts only, connects Bybit credentials and tests/synchronizes
assigned IBKR profiles. ADMIN filters all profiles by owner and provisions
IBKR connections, edits credentials and enables/disables accounts. A disabled
route requires an ADMIN to re-enable it, including routes disabled by the owner.
Activation does not bypass disabled state. IBKR/MT5 provisioning, replacement,
disconnection and removal are administrator-managed. No automatic public signup.

Bybit connection validates the authenticated userID through the existing
`/v5/user/query-api` method, then reads the wallet. Missing identity and withdrawal
permission are rejected. Responses retain no key-information payload or secrets.
Duplicate UID/API-key assignments in the same environment are rejected across
owners. Credential replacement validates identity, compares the old authenticated
UID and clears prior buy/sell execution certification. It cannot switch the
underlying broker account. Existing profiles are not silently rewritten or
reconnected: legacy unverified reference values need administrator review before
claiming that every historical profile has a verified UID.

IBKR connect/validate is ADMIN-only and requires a private bridge token. Profiles
are provisioned to active owners after exact broker account/environment checks.
One bridge endpoint cannot be assigned to another owner/account, and one account
ID in an environment cannot be duplicated. Provisioning uses a PostgreSQL advisory
transaction lock. This is not a schema uniqueness constraint; existing legacy
records need review. Credential-backed application clients filter position,
order and execution lists to their expected account ID, reject account-summary
identity changes and reverify before broker POSTs. Unknown account rows are
excluded. Do not reuse one gateway for independent users or use DNS aliases to
circumvent assignments. Administrators remain trusted infrastructure operators.

MT5 remains a shared execution node: new cross-owner assignment is refused.
Independent MT5 terminals per user are not provisioned by this release. Twelve
Data is market data only. Live remains separately gated and disabled in the
current deployment. All new accounts start without execution certification.
No real-user credentials, new accounts or new Gateway sessions are created by
the source change itself.

## Provision an additional IBKR Paper connection

1. Create the user's application login through Users. Exchange initial passwords
   privately. The owner supplies their own IBKR Paper credentials privately;
   never paste credentials or tokens into chat, logs, commits or screenshots.
2. Create a protected directory outside the repository for that owner. Copy
   `ops/ibkr-user/example.env` there with mode 600. Create a secrets subdirectory
   with mode 700 and files `tws_password`, `vnc_password`, `bridge_token` with
   mode 600. Generate a different bridge token per instance.
3. Export the verified merged `tools/ibkr_bridge.py` into the private directory.
   Set IBKR_BRIDGE_SOURCE to its absolute path, ATLAS_APP_IMAGE to the validated
   immutable image ID, and ATLAS_APP_NETWORK to the app container's network.
   Set unique IBKR_INSTANCE, unused loopback VNC/bridge ports and this owner's
   IBKR_ACCOUNT_ID/TWS_USERID. Never reuse production instance names or ports.
4. Validate the staged configuration with `docker compose --env-file PRIVATE_ENV
   -p atlas-ibkr-INSTANCE -f ops/ibkr-user/compose.yml config --quiet`. Do not print
   expanded configuration. Start this new project only after validation; never
   recreate existing app/Gateway services to add another owner.
5. The template uses isolated project-scoped settings and a new Gateway login.
   Complete any broker login/2FA through an SSH-tunnelled loopback VNC connection.
   The bridge shares its own Gateway network namespace, connecting to Paper API
   port 4002. It has a unique app-network alias `atlas-ibkr-INSTANCE`; bridge and
   VNC operator ports bind only to localhost. Shared app network access still
   requires the per-instance token. Do not expose VNC/API/bridge publicly.
6. Read-only API is the template default. Validate login/account identity first.
   Enabling the API for demo execution is a separate per-instance operator step
   after broker acceptance; do not change current production flags implicitly.
7. As ADMIN, open Accounts → Add broker account → IBKR/PAPER. Choose the owner,
   their account ID, `http://atlas-ibkr-INSTANCE:8766` and private token. Save with
   activation unchecked. Test and sync as ADMIN and then as that USER. Check
   identity and that another USER cannot see the profile. Activate only after
   these checks and configure/certify its strategies separately.

This is a deployment template, not evidence that another authenticated Gateway
has already been provisioned or that the server has capacity for unlimited JVMs.
Inspect memory/CPU before adding instances. User-hosted Gateways additionally
require a private authenticated route; do not open public bridge ports.

## Acceptance and rollout

No schema migration or production data rewrite. Full isolated PostgreSQL/Redis/
Node suite must pass before merge/deployment. Existing native protection,
Paper-delayed-data overlay, 30-second monitor and ATR-off state must be retained.
Record rollback image/commit, back up production and recreate app only. New
Gateway projects are deployed independently, once owner credentials are supplied.
Keep research collection running against its pinned source and existing profile.

Regression tests exercise role/owner isolation, admin provisioning, encrypted
responses, duplicate assignments, disabled-route activation, broker UID checks,
withdrawal-key rejection, suspended-owner final submission guards, account-ID
changes and filtered broker lists. Frontend runtime checks cover both roles,
late responses, creation/management controls and mobile grid constraints.
Desktop/phone acceptance after deployment must cover user creation, empty state,
connection errors, secret clearing, owner filtering and existing Dashboard.

Rollback restores the prior application image and code. There is no migration
to downgrade. Keep any newly created credentials/profiles under review; rollback
also removes these new authorization boundaries, so do not invite users until
acceptance is complete. Never delete existing broker/audit/research records.
