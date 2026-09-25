# ATLAS MARKETS v80 — Shadow Strategy Intelligence

v80 introduces a non-executing strategy laboratory. It is designed to test whether regime detection, multi-timeframe agreement, news context and optional chart-vision observations improve out-of-sample results before any execution behavior changes.

## Safety boundary

- Every v80 decision returns `mode=SHADOW` and `executable=false`.
- Shadow output is not connected to broker order submission.
- Vision is optional, bounded to one confirmation vote and cannot create a trade direction.
- Existing provider certification, Live Money gates and risk controls remain unchanged.

## Analysis

- Market regimes: trending up/down, ranging, high volatility and low volatility.
- Per-symbol calibration with stricter confirmation for higher-volatility stocks.
- Higher-timeframe, news and chart-vision confirmations and contradictions.
- Explicit abstention when confidence, confirmation or regime gates do not pass.

## Validation

`POST /analysis/shadow/backtest` performs chronological walk-forward evaluation and reports training and unseen validation metrics separately. Round-trip trading costs are deducted from every result. Promotion always remains disabled until adequate validation trades and forward paper observation exist.

The purpose is repeatable risk-adjusted performance. v80 makes no daily-return promise and does not optimize toward extraordinary social-media profit claims.
