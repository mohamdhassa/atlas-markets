# ATLAS MARKETS — Providers

Last updated: 2026-08-30

## Provider matrix

| Provider | Purpose | Current environment | Automatic execution |
|---|---|---|---|
| Fusion Markets MT5 | FX, metals, commodities | Demo | CERTIFIED |
| Interactive Brokers | Stocks, ETFs | Paper | CERTIFIED with max 1 share/order |
| Bybit | Crypto | Testnet | BLOCKED by provider `10024` |
| Twelve Data | Market/historical data | API data service | NEVER execution |

## Fusion Markets MT5

The MT5 route is the primary certified automatic execution route for FX, metals and commodities.

Operational requirements:

- Fusion MT5 Demo terminal logged in.
- Algo Trading enabled.
- ATLAS MT5 bridge running.
- broker profile enabled, active, connected and credentials configured.
- stop-loss and take-profit protection required for automatic orders.
- existing-symbol position/open-order guards remain active.

For Oracle hosting, MT5 runs on a Windows execution node reachable through a private VPN. Do not publish the bridge port to the Internet.

## Interactive Brokers

Current environment: Paper.

Certified safeguards:

- Paper/simulation bridge only.
- WhatIf preflight required.
- maximum 1 share per automatic order.
- duplicate position/open-order prevention.
- broker status verification after submission.
- cancelled broker orders are persisted as `CANCELLED` rather than `EXECUTED`.

The bridge currently requests delayed data when live entitlements are not present. For broad automated U.S. stock/ETF simulation, enable the appropriate IBKR real-time market-data subscriptions for API use. IBKR documents delayed data as delayed and separately identifies missing real-time subscriptions; delayed data should not be considered equivalent to live execution-quality pricing.

The v1.1 bulk AUTO_TRADE operation may promote configured IBKR Paper stock/ETF strategies because the route itself is certified. The 1-share cap and all preflight/risk gates remain enforced.

## Bybit

Current environment: Testnet.

Confirmed working:

- authentication;
- wallet/private API;
- read/write permissions;
- ContractTrade Order/Position permissions;
- unified account status;
- account balance;
- order request reaches Bybit.

Current blocker:

- Bybit rejects the controlled order with error `10024` and a regulatory/product availability message.

ATLAS classification: `PROVIDER_EXECUTION_NOT_CERTIFIED`.

This is not a bad-secret or signature problem. Do not rotate keys simply to try to evade `10024`, do not use a VPN to misrepresent jurisdiction, and do not create false residency/account information.

Resolution path:

1. Log into the same Bybit Testnet account in the browser.
2. Attempt the same perpetual product manually in Testnet.
3. If the UI also blocks it, open a Bybit support ticket and provide the account UID, exact `10024` message and that this is Testnet/API product access.
4. If support changes/approves account product access, rerun ATLAS diagnostics.
5. Run a controlled test order.
6. Add/verify controlled reduce-only close lifecycle.
7. Only then change Bybit automation certification.

Until step 7, crypto strategies may remain WATCH/SIGNALS/AUTO_TRADE-configured for analysis if desired, but the automatic execution layer will still block Bybit.

## Twelve Data

Twelve Data supplies market/historical data. It is intentionally not an execution provider. Its presence does not create a third trading broker.

## Oracle topology

Oracle hosts the core app/database/Redis. Broker bridges are private execution nodes. Recommended topology:

- Oracle -> private VPN -> MT5 bridge node
- Oracle -> private VPN -> IBKR bridge node
- Oracle -> HTTPS -> Bybit/Twelve Data

See `ORACLE_DEPLOYMENT.md`.
