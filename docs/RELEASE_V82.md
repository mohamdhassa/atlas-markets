# ATLAS MARKETS v82 — Provider-Aware Shadow Analytics

## Delivered

- Provider coverage reporting proves which configured IBKR, Bybit, and MT5 strategies are observed.
- Every meaningful scan skip or error is persisted with its provider, symbol, and reason.
- Forward outcomes settle on the first available candle at or after their due time rather than the latest price.
- Direction-aware maximum favorable and adverse excursion are recorded for every settled directional observation.
- Performance now reports expectancy, profit factor, compounded-path drawdown, and readiness failures.
- The Strategy workspace shows provider coverage, advanced performance, and expandable skipped-symbol diagnostics.

## Safety

This release remains shadow-only. It does not add an order submission path and cannot promote itself to paper or live execution. Eligibility is evidence shown to an operator, not authorization.

## Promotion requirements

A symbol/provider/timeframe group remains validating until it has at least 30 settled directional observations, positive net expectancy, profit factor of at least 1.2, and maximum drawdown no greater than 10 percent. Operational approval and paper certification remain separate later stages.
