# Frozen 5-minute versus 15-minute Spot research

This offline experiment compares signal exits at 5m and 15m using the saved
public Spot datasets. Thresholds, sizing, instrument limits and cost assumptions
stay fixed. No production settings, strategy eligibility or orders change.

```sh
python -m app.backtesting.spot_timeframe_comparison --input DATASET --output NEW_REPORT \
  --capital 100 --fee-bps 10 --slippage-bps 2,5,10
```

Run only the separately tested research image with networking disabled, datasets
mounted read-only and a new report directory. Output creation is exclusive.
No downloads, database access, migrations or app/Gateway deployment are needed.

## Aggregation and timing

Validate the complete provenance-tagged 5m dataset before aggregation. Group
three consecutive source candles into UTC-aligned 15m candles: first open,
maximum high, minimum low, final close and summed volume. Discard only incomplete
boundary groups, report their count and hash the derived candle list. Missing
interior source bars cannot be silently filled or stitched across gaps.

Each timeframe uses the same signal engine/router agreement gate with the
correct timeframe argument and its last 200 completed candles. Thus 15m uses
three times the elapsed lookback, as part of this fixed experiment. It is not
an isolated change to polling cadence. A 15m signal appears only after all
three constituents close; it executes once at the next source open. It is never
forward-filled between 15m closes. Signal exits remain eligible SELL decisions;
the rejected ATR exit policy is not included.

Both policies start flat on the same UTC 15m boundary after the original 5m
warmup/initial diagnostic window and after 15m indicator warmup. Their common
end is the final complete 15m boundary. Alignment shifts relative to the old
baseline start are explicit. At least two full validation slices are required.
The old baseline CLI and its original reports remain unchanged.

Both policies reuse the unchanged baseline simulator on the same underlying
5m execution/mark grid. Entry sizing uses the prior source close (identical to
the completed 15m close at a 15m decision), readiness's price-percent fallback,
the same capital/precision/limits and adverse next-open fills. Equity is marked
every 5m for both, preventing different drawdown sampling. Disjoint calendar
slices group closes; positions carry across boundaries and final inventory
remains marked. Training is not used to select a timeframe.

## Reporting and interpretation

Record common dates, source/derived hashes, edge exclusions, fixed settings,
eligible decision counts, closes, net P&L, fees, profit factor, expectancy,
open inventory, marked equity, 5m-close drawdown, entry-route groups and slices.
Costs are modeled assumptions and current order rules proxy historical rules.
Independent per-asset runs are not a combined portfolio.

This comparison follows inspection of baseline and ATR losses on the same
datasets. It is exploratory reuse, not an independent holdout. Slower signals
may reduce or increase turnover; code does not assume they will be profitable.
No parameter grid, winner promotion or live eligibility is added. Fresh
prospective paper evidence would be required after any research hypothesis.

## Release validation

Regression tests cover UTC OHLCV aggregation, partial edges/missing interiors,
completed-window signals, future-candle exclusion, sparse 15m decisions,
next-open execution, common dates/costs/sizing, equal 5m mark sampling, slice
carry, final inventory, invalid data/assumptions and exclusive output. Full
production-equivalent container tests precede merge. Production is unchanged.
