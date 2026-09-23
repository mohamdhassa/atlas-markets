# ATLAS MARKETS — Current Status

Last updated: 2026-09-23
Production checkpoint: v77 `a141d2c`

## Production state

ATLAS MARKETS is running on Oracle Cloud with FastAPI, PostgreSQL 17 and Redis 7 healthy. Production deployment uses the Oracle compose override and app-only upgrades are used when database/Redis changes are not required.

Live Money remains gated. Current automatic execution work is limited to certified simulation environments.

## Providers

### Bybit Testnet
- Connected managed Spot simulation route.
- AUTO_TRADE universe: BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT.
- BUY execution has been verified on Testnet.
- SELL is restricted to ATLAS-managed inventory; unrelated wallet holdings are not adopted automatically.
- v76 added broker-wallet reconciliation before managed SELL submission to address managed quantity vs broker balance drift.
- Runtime verification of the next naturally occurring ETH/SOL SELL is still pending. Do not force a trade or change risk rules solely to test it.
- Live Bybit execution remains gated.

### Interactive Brokers Paper
- Connected Paper route for stocks/ETFs.
- Certified safeguard: maximum 1 share/order plus existing preflight/duplicate controls.
- Provider-unavailable conditions are represented separately from strategy/risk BLOCK decisions.
- Gateway and bridge run on Oracle. IB Gateway authentication/2FA remains an operational dependency after security/session resets.
- Daily authenticated restart behavior is under observation; do not bypass IBKR 2FA.

### Fusion Markets MT5 Demo
- Demo integration exists.
- Terminal/authorization health remains an external runtime dependency and should be verified independently before relying on the route.

### Twelve Data
- Data provider only; never an execution route.

## v74-v77 operational changes

- v74: Bybit Spot metadata fallback and per-symbol execution isolation.
- v75: broker-aware Live Activity Log with execution/fill context.
- v76: Bybit Testnet managed SELL balance reconciliation and explicit no-fill UI values.
- v77: frontend operational visibility for provider state, BLOCK/provider-unavailable counts, reconciliation markers and Live Activity rendering.

## Frontend

The Live Activity Log now distinguishes decision rows from broker fills. Non-filled rows display `N/A · no broker fill` for execution-only values. Broker/account/environment, reason, quantity, price/notional, fee, realized P&L, broker IDs and scan IDs are exposed when available.

## Acceptance evidence

The v77 branch passed the full pytest suite on Oracle (four existing skipped tests; only known dependency deprecation warnings). Production was rebuilt from `main` and `/health` returned application, database and Redis status `ok`.

## Open verification items

1. Observe the next natural Bybit ETH/SOL SELL and verify v76 reconciliation prevents the prior `170131 Insufficient balance` failure.
2. Observe the next IB Gateway daily restart and confirm whether authentication survives as configured; weekly/security-reset 2FA may still require manual action.
3. Continue frontend portfolio work to distinguish ATLAS-managed positions from broker-held/external assets wherever broker data supports that distinction.
4. Keep documentation synchronized after operational changes.
5. Run a multi-week simulation observation without repeatedly changing strategy/risk logic.

## Safety boundary

Do not enable Live Money as part of routine deployment. Do not manually adopt external broker holdings into ATLAS-managed inventory. Do not bypass broker authentication, provider restrictions, risk gates or the kill switch.
