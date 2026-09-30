# Multi-user security and ownership

ATLAS MARKETS uses authenticated ownership boundaries for operational trading data.

## Rules

- A `USER` can read and mutate only broker profiles owned by that user's UUID.
- Data linked to a broker profile—signals, orders, positions, reports, executions, and strategy assignments—must be selected through the authorized profile scope.
- An `ADMIN` may inspect all owners. Operational list endpoints may accept `owner_user_id` to narrow an administrator view to one user.
- Supplying another user's identifier never expands an ordinary user's scope; it returns HTTP 403.
- Unknown broker profiles return HTTP 404. Existing profiles owned by another ordinary user return HTTP 403.
- Global safety configuration remains administrator-managed and is not silently duplicated per user.

## Developer requirement

New endpoints must use `app.services.access_scope` rather than reproducing role checks. Queries for child records must join or otherwise constrain through `BrokerProfile.user_id`. Mutation handlers must call `authorized_broker_profile` before changing account-linked records.

## Verification

The access-scope unit tests exercise two-user denial and administrator filtering behavior. Release verification must also run the full test suite in the production image before deployment.
