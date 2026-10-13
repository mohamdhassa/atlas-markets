# Spot walk-forward baseline research

These offline commands collect public Bybit Mainnet Spot history into separate
JSON datasets and evaluate the current frozen technical signal/router baseline.
They do not connect to private APIs, PostgreSQL, broker profiles or automation,
and never submit orders, mutate live settings or promote a strategy.

## Data

`python -m app.backtesting.spot_history --output /data --days 42` collects the
five configured USDT pairs with explicit `category=spot`, paginated start/end
bounds and only completed 5-minute candles. Each dataset records its endpoint,
source environment, requested window, collection time, page bounds, current
instrument rules and candle-content SHA-256. Files are created exclusively;
existing files and historical database rows are not replaced. Hashes detect
content changes, not independent broker execution verification.

The existing historical collector requests `linear` crypto candles and no IBKR
stock candles. Those rows must not be silently relabeled as Spot. The evaluator
rejects futures/unknown provenance, forming bars, missing/duplicate/reordered
timestamps, invalid OHLCV, invalid hashes and missing instrument-size metadata.

Bybit documents the Spot category, inclusive request bounds, reverse-order
pages, a 1000-row limit, and that an unfinished candle's close is only the last
traded price: https://bybit-exchange.github.io/docs/v5/market/kline
Current instrument limits are described at:
https://bybit-exchange.github.io/docs/v5/market/instrument

## Frozen-policy forward evaluation

`python -m app.backtesting.spot_walk_forward --input DATASET --output REPORT
--capital 100 --fee-bps 10 --slippage-bps 2,5,10` uses **100 USDT per independent
asset run**. This is a research assumption, not a production capital override.
Ten fee basis points per leg and the three slippage cases are assumptions to
stress, not verified account fees. Match them to actual fees before interpreting
results. Five independent runs are not a combined 100-USDT portfolio.

The frozen baseline is 5m, minimum signal strength 65, risk sizing 1%, stop sizing
multiplier 1.5, target ratio 2 and maximum position notional 20%. It shares the
production signal engine and router agreement gate. There is no parameter
optimization or selection using validation results. Training is diagnostic only.

The first 200 bars warm indicators. Rolling training windows use 2016 bars
(seven days), followed by disjoint 1008-bar validation windows (3.5 days). Training
realizations cannot use a later validation candle. Validation starts flat, stays
chronological and carries inventory across fold boundaries; final inventory is
marked rather than forcibly reported as a closed winner. A final partial fold
is retained and reports its smaller bar count. At least two full validation
windows are required. Time-ordered validation avoids training on future data:
https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html

Orders use the prior completed 200-candle signal window and the next bar's open,
with adverse slippage on both legs. Only one long-only Spot position can be open
per asset. BUY while holding and SELL without inventory cannot create overlapping
trades or shorts. Modeled entry/exit fees are charged once in quote currency.
Order quantity rounds down to current instrument precision and respects current
minimums, maximums and cash. Entry-route groups use the entry decision, not exits.

Two production details are intentionally visible: readiness currently omits ATR
when calling `build_execution_plan`, so sizing uses its price-percent fallback;
the Bybit Spot submission passes side/quantity, not native stops/targets. The
baseline therefore models eligible SELL-signal exits and does not invent ATR-
triggered or broker-held protective exits. Stop multiplier/target ratio are
recorded sizing settings, not simulated protections. This research neither fixes
nor certifies those execution behaviors.

## Interpretation and limits

Reports separate closed-trade net P&L, expectancy, fee assumptions, profit factor,
entry routes, fold outcomes, final open inventory and candle-close marked-equity
drawdown. No-loss profit factor stays null. Training metrics are diagnostic and
not pooled into validation metrics. No simulated result is broker-verified P&L.

Historical order rules, fee currency effects, liquidity, partial/rejected fills,
outages, daily-loss controls and cross-asset exposure are not reproduced. Candle-
close drawdown does not measure the worst intrabar or live-account drawdown.
Historical data and frozen settings chosen today do not establish prospective
performance. Paper/Testnet observation and separate provider certification remain
required; every report has `executable=false` and `live_eligible=false`.

Run in a separately built research container with only a dataset-directory bind
mount. No application deployment or Gateway restart is required. Production-
equivalent full-suite validation precedes merge; then collect actual Spot data,
verify coverage and run the baseline and cost stress cases. IBKR stock/ETF testing
is a separate dataset and execution-model task.
