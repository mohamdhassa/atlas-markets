# ATLAS MARKETS — Post-v1 Roadmap

## Current checkpoint

ATLAS MARKETS **v1.0.0 Simulation Release is complete** for Paper / Demo / Testnet automated trading.

Certified automatic routes:

- Fusion MT5 Demo
- Interactive Brokers Paper, maximum 1 share/order

Provider-limited route:

- Bybit Testnet execution remains blocked by provider error `10024`

Data-only provider:

- Twelve Data

Live Money remains explicitly gated.

## Completed in v1.0

- [x] FastAPI/PostgreSQL/Redis/Docker platform
- [x] ADMIN / USER authentication and account isolation
- [x] external provider profiles and encrypted credentials
- [x] Fusion MT5 Demo connectivity and execution certification
- [x] IBKR Paper connectivity and execution certification
- [x] Bybit Testnet connectivity/private API integration
- [x] Twelve Data integration
- [x] validated multi-market universe
- [x] centralized provider routing
- [x] technical/multi-timeframe analysis
- [x] historical intelligence
- [x] news intelligence
- [x] per-symbol WATCH / SIGNALS / AUTO_TRADE modes
- [x] account/portfolio risk controls
- [x] duplicate position/order guards
- [x] certified-route-only automatic execution
- [x] broker fill/cancellation verification
- [x] persistent automation scan/action history
- [x] unified broker-derived P&L/history
- [x] strategy performance diagnostics
- [x] conservative broker-verified strategy attribution
- [x] responsive frontend
- [x] Automation Operations Center
- [x] release readiness endpoint
- [x] final handover/runbook

## Post-v1 enhancement track

These items are enhancements, not requirements to call v1.0 simulation complete.

### Strategy research and intelligence

- expand financial/fundamental data inputs;
- improve explainable confidence calibration;
- add formal backtest/replay workflows;
- compare strategy variants without automatically rewriting production logic;
- expand regime and correlation analysis.

### Performance analytics

- richer equity-curve and drawdown charts;
- monthly/yearly performance views;
- more detailed per-strategy/per-provider/per-symbol comparisons;
- exact future execution-to-signal attribution using persisted correlation IDs on every new order lifecycle.

### Frontend product polish

- additional mobile refinements;
- simplified provider onboarding;
- charting enhancements;
- notification preferences;
- optional user-customizable dashboards.

### Additional providers/instruments

Any new provider must pass:

`CONNECT → READ → PREFLIGHT → CONTROLLED ORDER → FILL VERIFY → CLOSE → AUDIT → CERTIFY`

Certification never transfers automatically between providers, accounts or environments.

## Live Money readiness program

Live Money is a separate controlled program and must not be enabled merely because v1.0 simulation is complete.

Before any Live Money certification:

1. run an extended Paper/Demo validation period;
2. review automatic scan stability and broker availability;
3. review drawdown, losses, exposure and failure cases;
4. confirm all expected broker order states are handled;
5. confirm backups/recovery and operational monitoring;
6. define live capital and per-order limits substantially below account capacity;
7. certify one provider/account/environment at a time;
8. retain an immediate kill switch and manual broker access;
9. never bypass provider/regulatory restrictions;
10. document explicit approval before enabling a Live Money route.

## Bybit

Bybit execution may be reconsidered only if provider error `10024` is legitimately resolved by Bybit/account eligibility. Do not use VPNs, identity/location changes or other workarounds to evade provider restrictions.

## Definition of future success

Post-v1 work should improve measurable reliability, explainability, safety or performance without weakening the completed simulation release safety boundaries.
