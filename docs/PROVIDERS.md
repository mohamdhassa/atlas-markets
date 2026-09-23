# ATLAS MARKETS — Providers

Last updated: 2026-09-23

## Provider matrix

| Provider | Purpose | Current environment | Automatic execution |
|---|---|---|---|
| Fusion Markets MT5 | FX, metals, commodities | Demo | CERTIFIED |
| Interactive Brokers | Stocks, ETFs | Paper | CERTIFIED with max 1 share/order |
| Bybit | Crypto Spot | Testnet | CERTIFIED managed simulation route; Live Money gated |
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

Current environment: Testnet Spot.

Current operational state:

- private authentication, wallet/account access and Spot order routing are working;
- managed Testnet BUY execution has been verified;
- SELL is limited to ATLAS-managed inventory;
- unrelated wallet holdings are not automatically adopted as ATLAS positions;
- v76 reconciles managed quantity downward to broker wallet quantity before a managed SELL when broker balance is lower;
- the next naturally occurring ETH/SOL SELL is still the runtime verification point for that reconciliation;
- Live Money remains gated.

Historical provider restrictions and certification incidents remain useful audit history, but they are not the current Bybit Testnet Spot state.

## Twelve Data

Twelve Data supplies market/historical data. It is intentionally not an execution provider. Its presence does not create a third trading broker.

## Oracle topology

Oracle hosts the core app/database/Redis. Broker bridges are private execution nodes. Recommended topology:

- Oracle -> private VPN -> MT5 bridge node
- Oracle -> private VPN -> IBKR bridge node
- Oracle -> HTTPS -> Bybit/Twelve Data

See `ORACLE_DEPLOYMENT.md`.
