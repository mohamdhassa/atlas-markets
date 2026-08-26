# ATLAS MARKETS — Current Development Status

Last updated: 2026-08-26

## Purpose

This file is the operational handover/checkpoint for the active ATLAS MARKETS development state. Historical project documentation remains preserved elsewhere; this file tracks the current checkpoint.

## Repository state

- Repository: `mohamdhassa/atlas-markets`
- Current baseline branch: `main`
- Local Windows path used during development: `C:\Users\USER\Downloads\altas-markets`
- Last verified automated test baseline before the latest MT5 alias-discovery additions: **69 passed, 1 warning**
- Expected baseline after the two newly added alias tests: **71 passed, 1 warning**

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

The current starter universe contains 21 candidate instruments spanning:

- stocks
- ETFs
- FX
- metals
- commodities
- crypto

Latest broker-native validation result:

```text
supported=20
failed=1
skipped=0
total=21
```

Validated examples include:

- IBKR: AAPL, AMZN, META, MSFT, NVDA, TSLA, IWM, QQQ, SPY
- MT5: AUDUSD, EURUSD, GBPUSD, USDCAD, USDCHF, USDJPY, XAUUSD, XTIUSD
- Bybit: BTCUSDT, ETHUSDT, SOLUSDT

The only failed candidate was `XAGUSD` because Fusion MT5 did not expose that exact symbol name. Broker-native MT5 symbol search/alias resolution is now being added so ATLAS can discover Fusion's actual silver symbol instead of assuming a universal broker symbol name.

## Centralized provider routing

ATLAS now has centralized market/provider routing rules and route-health checks:

- stocks / ETFs → IBKR
- FX / metals / commodities → MT5
- crypto → Bybit
- Twelve Data → market data only

Execution candidates must be connected, enabled, active and credentials-configured.

## Immediate next task

1. Pull/restart the updated MT5 bridge containing `/symbols/search`.
2. Run the full test suite and confirm the expected **71 passed** baseline.
3. Rerun `validate_instrument_universe`.
4. Confirm whether `XAGUSD` resolves to Fusion's broker-specific silver symbol.
5. Once the universe is fully validated, seed verified instruments into safe `WATCH` / `SIGNALS` modes.
6. Do not bulk-enable `AUTO_TRADE` yet; MT5 currently has substantial existing Demo exposure and the risk engine must account for that before multi-instrument automatic execution.

## Central-engine work remaining

- complete broker-symbol alias/capability discovery
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

Live Money automatic trading is intentionally not ready. Provider certification is currently confined to Paper/Demo/Testnet environments. Live execution remains explicitly gated until routing, strategy, risk, automation and extended simulation have been validated.
