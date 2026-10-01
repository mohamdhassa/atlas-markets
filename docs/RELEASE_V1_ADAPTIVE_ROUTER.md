# v1 adaptive strategy router

This release adds a shadow-only market-regime router and Darvas Box detection.

## Included

- completed-candle Darvas Box boundaries and volume-confirmed breakout detection
- regime routes for trend, range, low volatility, high volatility and news uncertainty
- explicit `NO_TRADE` fallback when confidence is insufficient
- strategy-route evidence persisted inside new shadow-observation details
- authenticated analysis endpoint for controlled evaluation from normalized candles
- regression coverage and operating documentation

## Excluded

The release does not enable automatic strategy promotion, change risk limits, arm Live Money or
submit broker orders. Existing execution and certification controls are unchanged.
