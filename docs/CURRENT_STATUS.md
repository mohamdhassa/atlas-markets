# ATLAS MARKETS — Current Development Status

Last updated: 2026-08-26

## Purpose

This file is the operational handover/checkpoint for the active ATLAS MARKETS development state. Historical project documentation remains preserved elsewhere; this file tracks the current checkpoint.

## Repository state

- Repository: `mohamdhassa/atlas-markets`
- Current baseline branch: `main`
- Local Windows path used during development: `C:\Users\USER\Downloads\altas-markets`
- Verified automated test baseline: **71 passed, 1 warning**

## Product direction

ATLAS MARKETS is a multi-market, multi-provider automated trading platform. The intended central flow is:

`market + historical + news/intelligence data → analysis → strategy decision → risk approval → provider routing → execution → monitoring/exits → P&L/performance → historical evaluation`

The platform supports configurable multi-instrument universes. Single symbols used in certification are test instruments only.

## Provider status

### Fusion MT5 — Demo

- Account/login: `448261`
- Server: `FusionMarkets-Demo`
- Algo Trading: ON
- Connectivity: **CERTIFIED**
- Execution: **CERTIFIED**

A controlled 0.01-lot EURUSD Demo position was opened and closed successfully. The exact certification position returned to flat state.

Known behavior: `/history/deals` can lag execution. Returned deal IDs plus confirmed position lifecycle are treated as authoritative execution proof; delayed history is reported as a warning.

### Interactive Brokers — Paper

- Account: `DUR980544`
- Connectivity: **CERTIFIED**
- Simulation/Paper: `True`
- Execution: **CERTIFIED**

Latest successful controlled certification:

- certification symbol: `DIA`
- quantity: `1` Paper share
- BUY accepted and filled
- position confirmed at quantity `1`
- SELL accepted and filled
- final position restored to baseline quantity `0`
- open execution ID: `00012ec5.6ad7d4cb.01.01`
- close execution ID: `00012ec5.6ad7d4f9.01.01`
- open price: `534.12`
- close price: `534.09`

IBKR execution compatibility work included explicit Paper-only gating, order-status/rejection diagnostics, disabling unsupported legacy `eTradeOnly`/`firmQuoteOnly` attributes, and explicit `DAY` time-in-force.

### Bybit — Testnet

- Current connected AI subaccount UID: `107068845`
- Connectivity/private API/wallet sync: **CERTIFIED**
- Order submission path: **REACHED**
- Execution: **PROVIDER-BLOCKED**

A valid BTCUSDT Testnet order reached Bybit's order endpoint, but Bybit rejected execution with error `10024` due to a product/service regulatory restriction. ATLAS must not bypass this restriction.

### Twelve Data

- Connectivity: **CERTIFIED**
- Role: market/historical data only
- Execution: not applicable

## Multi-instrument universe

The current starter universe contains 21 candidate instruments spanning stocks, ETFs, FX, metals, commodities and crypto.

Latest broker-native validation result:

```text
supported=21
failed=0
skipped=0
total=21
```

Validated instruments:

- IBKR stocks: AAPL, AMZN, META, MSFT, NVDA, TSLA
- IBKR ETFs: IWM, QQQ, SPY
- MT5 FX: AUDUSD, EURUSD, GBPUSD, USDCAD, USDCHF, USDJPY
- MT5 metals: XAGUSD, XAUUSD
- MT5 commodity: XTIUSD
- Bybit crypto: BTCUSDT, ETHUSDT, SOLUSDT

MT5 broker-native symbol discovery/alias resolution is active, and `XAGUSD` now validates successfully.

## Centralized provider routing

ATLAS has centralized market/provider routing rules and route-health checks:

- stocks / ETFs → IBKR
- FX / metals / commodities → MT5
- crypto → Bybit
- Twelve Data → market data only

Execution candidates must be connected, enabled, active and credentials-configured.

## Immediate next task

The provider setup/certification and starter-universe validation stage is complete. Next development should focus on the central engine:

1. seed the fully validated universe into safe `WATCH` / `SIGNALS` modes;
2. build/validate multi-instrument scanning across the seeded universe;
3. preserve per-symbol/provider routing;
4. integrate existing analysis/news/historical inputs into explainable BUY/SELL/HOLD decisions;
5. harden account-wide risk using existing positions/exposure before enabling broad `AUTO_TRADE`;
6. keep Bybit execution disabled while error `10024` remains in force;
7. do not bulk-enable `AUTO_TRADE` yet.

## Central-engine work remaining

- safe universe seeding
- multi-instrument scanning
- technical/fundamental/news intelligence integration
- defined BUY/SELL/HOLD methodology and confidence model
- risk-engine hardening, including existing-position exposure
- automatic execution lifecycle
- position/exit monitoring
- performance analytics
- historical strategy evaluation
- frontend/mobile redesign and provider setup UX
- final deployment/operations/security documentation

## Safety position

Live Money automatic trading is intentionally not ready. Provider certification is confined to Paper/Demo/Testnet environments. Live execution remains explicitly gated until routing, strategy, risk, automation and extended simulation have been validated.
