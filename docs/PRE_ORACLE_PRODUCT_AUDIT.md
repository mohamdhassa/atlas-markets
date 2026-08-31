# ATLAS MARKETS — Pre-Oracle Product Audit

## Target operating model

ATLAS MARKETS should be operated through three primary surfaces:

1. **Dashboard** — overall multi-provider equity, realized P&L, positions, orders, automation activity, strategy counts, and verified ATLAS performance.
2. **Engines** — one independent operating dashboard per provider. Each provider page contains its accounts, connection/engine state, strategies, positions, orders, automation actions, broker performance, and ATLAS-verified performance.
3. **Management** — provider integrations, account lifecycle, connection tests/sync, application users, roles, account readiness, and Live Money safety boundary.

The global automation kill switch remains the final system-wide safety control.

## Provider status and constraints

### Fusion Markets / MT5
- Demo automation is the primary certified simulation execution route.
- MT5 requires the Windows terminal/bridge execution node to remain available.
- Demo and future LIVE profiles must remain separate.

### Interactive Brokers
- PAPER automation is certified with the existing maximum-one-share safety boundary.
- Broad unattended stock/ETF execution still requires reliable market data appropriate for API trading.
- Management actions must use the certified `/ibkr/...` adapter rather than the obsolete generic IBKR probe.

### Bybit
- Testnet market/account connectivity exists.
- Execution remains blocked by provider error 10024 / provider-side restriction.
- ATLAS must not bypass or weaken this provider restriction.

### Twelve Data
- Data-only integration.
- Never an execution route.

## Strategy/performance audit rule

Raw broker history is useful for diagnosis but is not automatically ATLAS strategy performance. Historical trades matched only by account/market/symbol have `BROKER_SYMBOL_MATCH_ONLY` confidence and must not drive automatic strategy tuning.

Strategy decisions should prioritize `/strategies/performance/verified`, which only counts broker trades linked to persisted ATLAS automation actions by exact broker identifiers. IBKR actions additionally require confirmed fills.

### Recommendation thresholds for the UI
- Fewer than 10 verified closed trades: **INSUFFICIENT VERIFIED DATA**.
- 10+ verified trades and negative verified P&L: **REVIEW STRATEGY**.
- 10+ verified trades and non-negative verified P&L: **KEEP / OBSERVE**.

These labels are advisory. They must not automatically increase risk, disable a strategy, or promote a symbol.

## User management audit

Required long-term controls:
- Create users.
- ADMIN and USER roles only.
- Activate/deactivate users.
- Change role with protection against removing the last active ADMIN.
- Admin password reset.
- Revoke active sessions when a user is disabled or their password is reset.

## Account/integration audit

Required controls:
- Add/configure provider profiles.
- Store credentials encrypted.
- Test connection.
- Sync balances/positions/orders.
- Run/stop account route.
- Activate one account route per provider/user where required.
- Disconnect/remove safely.
- Keep simulation and Live Money environments explicit.
- Keep global Live Money permission disabled until separate certification.

## Before Oracle deployment

Do not deploy until:
- Full pytest suite passes.
- Dashboard, Engines, and Management surfaces load successfully.
- MT5 and IBKR provider pages can read their current account state when their bridges are running.
- Bybit correctly remains execution-blocked.
- Twelve Data remains data-only.
- Admin user lifecycle actions are tested.
- Account test/sync controls are tested for each provider.
- No Live Money execution is enabled.

## Recommended cleanup after functional verification

The repository still contains many historical `phaseXX` frontend files. They should not all remain active indefinitely. After the new operating surfaces are verified, consolidate the active frontend into stable modules such as:

- `static/core/`
- `static/dashboard/`
- `static/engines/`
- `static/management/`
- `static/components/`

Keep old phase files in Git history rather than continuing to layer new runtime overrides. This cleanup should be done before or immediately after the first stable Oracle deployment, not while broker behavior is still being validated.
