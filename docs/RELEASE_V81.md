# ATLAS MARKETS v81 — Forward Shadow Observation

v81 connects the non-executing v80 evaluator to enabled symbol strategies and records forward observations every five minutes.

## Runtime behavior

- Fetches provider candles for enabled IBKR, MT5 and Bybit strategies.
- Applies symbol calibration, regime detection and available news sentiment.
- Persists one observation per strategy/source candle.
- Settles directional observations after six configured timeframe bars.
- Deducts an eight-basis-point round-trip cost before classifying wins and losses.
- Continues operating independently of order execution and never calls broker order endpoints.

## Visibility

- `GET /analysis/shadow/observations`
- `GET /analysis/shadow/performance?days=30`
- Strategy page forward-observation table with latest direction, regime, sample count, win rate, net return and readiness.

## Safety

Shadow eligibility is informational. It cannot enable `AUTO_TRADE`, raise position size, bypass provider certification or unlock Live Money. At least 30 settled directional observations plus positive results are required even for an informational eligible label.
