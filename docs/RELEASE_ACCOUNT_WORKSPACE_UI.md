# Users and Accounts workspace polish

Users and Accounts retain their existing APIs, role/owner checks and broker flows.
The pages now lead with a title, compact counts and readable identity/status cards.
Create-user and account-management controls use disclosures; connection forms open
on demand and offer Cancel. Owner filtering includes an explicit empty state.

IBKR setup follows the connected-account cards instead of preceding the page title.
Requests use a compact disclosure, with a four-stage progress display and readable
status badges. An owner with an existing non-editable request sees its status rather
than a duplicate request form. Private login fields remain owner-only and clear on
submission failure/success. Administrator approval and broker identity verification
remain unchanged. A connected setup is identity verification, not trading approval.

Scoped styles include 44px controls, single-column narrow forms, wrapping account
identifiers and mobile card actions. Cache versions are advanced together for CSS
and both scripts. Unrelated dashboards and portfolio pages retain their assets.

Validation: Node runtime tests cover page navigation races, owner/admin controls,
setup progress and suppression of duplicate requests. Browser layout checks use
mock broker data, not real credentials or broker sessions. The full release suite
and production verification remain deployment gates. No migration, worker update,
Gateway restart or trading-setting change is required.

On app recreation retain all four production Compose files, including
ops/docker-compose.ibkr-onboarding.yml. The installed provisioning worker keeps
its pinned source and image; this frontend release does not alter its policy.
