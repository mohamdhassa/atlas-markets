# ATLAS MARKETS — Roadmap

## Current checkpoint

Provider connectivity is established across Fusion MT5 Demo, IBKR Paper, Bybit Testnet and Twelve Data. MT5 Demo execution is certified. IBKR Paper execution certification is next. Bybit execution is currently blocked by provider error `10024`.

## Priority 1 — Finish Paper/Demo execution certification

- [x] Fusion MT5 Demo connectivity
- [x] Fusion MT5 Demo execution
- [x] IBKR Paper connectivity
- [ ] IBKR Paper execution
- [x] Bybit Testnet connectivity/private API
- [!] Bybit Testnet execution — provider/regulatory restriction `10024`
- [x] Twelve Data connectivity

After IBKR certification, stop treating provider setup as the main project focus.

## Priority 2 — Multi-instrument universe

- define configurable universes per asset class/account;
- discover/validate provider-supported instruments;
- normalize symbol metadata;
- avoid one-symbol-per-broker assumptions;
- support enable/disable controls and scanning scope.

## Priority 3 — Provider routing

Build/validate automatic routing using asset class, instrument availability, account state, environment, connection health, market session, risk authorization and buying power/margin.

Representative routing: stocks/ETFs → IBKR; FX/metals/commodities → Fusion MT5; crypto → Bybit when execution is permitted.

## Priority 4 — Analysis and strategy

- technical indicators and multi-timeframe analysis;
- momentum/trend/regime inputs;
- historical market context;
- financial/news intelligence;
- explicit BUY/SELL/HOLD methodology;
- meaningful confidence/reason codes;
- deterministic/testable components where possible.

Avoid arbitrary unexplained AI scoring.

## Priority 5 — Risk engine

Harden:

- maximum position size;
- maximum account/asset-class exposure;
- maximum open positions;
- daily-loss limit;
- drawdown controls;
- stop loss/take profit;
- leverage/margin controls;
- spread/slippage limits;
- duplicate-order prevention;
- stale-signal prevention;
- correlated exposure;
- market-hours validation;
- provider health checks;
- kill switch;
- explicit Live Money gate.

## Priority 6 — Automatic trading lifecycle

Certify the complete loop:

`scan → analyze → signal → risk → route → execute → monitor → exit → record → performance → repeat`

Normal automated operation should not require manual Buy/Sell clicks.

## Priority 7 — Performance and historical evaluation

Provide:

- daily/monthly P&L;
- cumulative return;
- win/loss rate;
- profit factor;
- drawdown;
- provider performance;
- instrument performance;
- strategy performance;
- time-series charts;
- trade/execution history;
- AI/strategy decision history.

Historical results should inform evaluation/backtesting. Do not allow a few recent trades to automatically rewrite production strategy logic.

## Priority 8 — Frontend/mobile UX

Complete/polish:

- Dashboard
- Markets
- Analysis
- Signals
- Positions
- Orders
- Performance
- History
- Integrations
- Strategy
- Risk Management
- Users
- Settings
- System Status

The frontend must be responsive on desktop and phone, and provider/account setup should become significantly simpler than the engineering setup used during development.

## Priority 9 — Extended simulation and Live Money readiness

Run an extended Paper/Demo/Testnet validation period. Review stability, risk behavior and performance before considering Live Money.

Live Money is not a completion shortcut and remains explicitly gated.

## Priority 10 — Release/operations documentation

Before release, ensure documentation accurately covers architecture, ERD, authorization, providers, environment/configuration, Docker, migrations, deployment, backups/recovery, security, risk, automated trading, certification, troubleshooting, maintenance and disaster recovery.
