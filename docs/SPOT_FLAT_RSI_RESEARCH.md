# Flat-lookback RSI research candidate

The unchanged technical RSI returns 100 when both average gains and average
losses are zero. A flat 200-candle fixture consequently generates SELL strength
90 with an overbought reason; the unchanged router blocks that fixture. This is
an indicator edge case, not proof it caused historical losses or submitted orders.

Candidate `FLAT_RSI_50_V1` returns neutral 50 only when all 15 closes in the
14-change RSI lookback are exactly equal. Non-flat math and insufficient-history
behavior are unchanged. No epsilon, smoothing, score threshold, route policy,
stop/target or execution setting is tuned. The heuristic signal strength is not
a calibrated probability and this candidate does not change that semantics.

The standalone command temporarily substitutes this indicator only inside its
single-threaded research process and restores it on success or failure. Runtime
`app/analysis/technical.py` is unchanged. Do not call the experiment inside a
running web or automation worker; run a separate container with networking off,
no credentials or database, read-only saved datasets and a new output directory.

```
python -m app.backtesting.spot_rsi_comparison --input DATASET --output NEW_REPORT \
  --capital 100 --fee-bps 10 --slippage-bps 2,5,10
```

Both policies use the same existing validated walk-forward evaluator, 200-bar
lookback, seven-day diagnostic training window, disjoint 3.5-day report slices,
continuous validation inventory, sizing rules and cost assumptions. Inputs are
provenance/hash checked. Fills use the next open; drawdown uses identical candle
close marks. Final open inventory stays marked. Independent 100-USDT asset runs
are not a combined portfolio. Fees are modeled assumptions, not account fees.
Reports include flat-lookback incidence, both complete policy reports, hashes,
common validation dates and non-executable/non-live-eligible flags. Output files
are created exclusively and original datasets are never overwritten.

## Existing evidence and interpretation

The operator's offline router comparison on 2026-10-19 reused the five saved
42-day Spot datasets ending 2026-10-13. At 10 bps fees and 2/5/10 bps slippage
per leg, every asset/cost case lost money with the current router. Removing the
router entirely or from SELL exits worsened marked returns in all 15 comparisons.
This supports retaining existing filters for this experiment, not future profits.

These datasets have already informed several experiments and are exploratory
reuse, not an independent holdout. Flat RSI may never occur in actual data; report
zero incidence and unchanged returns honestly. Freeze the candidate before fresh
prospective observation. No automatic adoption or Live readiness follows from
better historical results. Liquidity, outages, historical lot-size changes,
daily-loss limits, combined exposure and broker-held protection remain outside
the shared baseline model. Production automation/settings stay untouched.

## Verification

Tests reproduce the false flat SELL, neutral candidate, unchanged rising/falling
and mixed paths, lookback boundaries, unchanged input data, aligned cost runs,
restoration on exceptions and separate research flags. Run the full isolated
production-equivalent validator before merge. Research requires a separately
built candidate image; no app/Gateway deployment or schema migration is needed.
