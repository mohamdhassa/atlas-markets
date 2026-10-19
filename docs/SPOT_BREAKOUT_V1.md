# Frozen prospective Spot breakout candidate v1

Policy: `SPOT_BREAKOUT_15M_V1`. This is a new research hypothesis, not an
improvement established by evidence, a production strategy or a profitability
promise. The existing platform, automation and broker controls are unchanged.

## Why this experiment

The previously inspected five-asset sample lost after modeled costs under the
current shared engine/router. Removing the router or its exit gate worsened
marked returns in all 15 asset/cost cases. The neutral flat-RSI research candidate
changed no result and found zero flat lookbacks in validation. Fifteen-minute
signals reduced turnover and generally reduced losses but did not show robust
net profitability. These observations motivate explicit independent entry/exit
rules; they are not justification to tune more thresholds on that sample.

## Frozen rules

- Long-only USDT Spot, each asset evaluated independently from 100 USDT.
- Build UTC-aligned 15m candles from three validated consecutive 5m candles.
  Discard only partial edge groups. Use 200 completed 15m bars per decision.
- Entry: completed close strictly above the highest high of the preceding 20
  bars, EMA20 above EMA50, and current volume at least 1.5 times the mean volume
  of those preceding 20 bars. Prior mean volume must be positive.
- Exit signal: completed close strictly below EMA20, regardless of entry
  conditions, volume or the production router. Execute at next 5m open.
- Initial modeled stop: actual slipped entry minus twice the preceding completed
  15m ATR14. Target: actual slipped entry plus three times that stop distance.
  Levels stay fixed; no trailing or parameter search.
- Quantity rounds down to current instrument precision. Price-distance risk is
  1% of current flat-account cash, with maximum entry notional 20% of that cash,
  available-cash/fee and instrument limits. Gaps/slippage/fees can exceed 1% loss.
- One position per asset; no shorting, pyramiding or exit/re-entry on one 5m bar.
  Re-entry can occur at a later completed 15m decision.
- Check opening stop gap first, then target gap, then EMA exit. Stop gaps fill
  at the worse open; target gaps receive no improvement beyond the target.
  On intrabar ambiguity, stop precedes target. All fills receive adverse
  slippage; fees are charged once per leg in quote currency.
- Fixed research assumptions: 10 bps fee per leg and 2/5/10 bps adverse slippage
  per leg. These are assumptions, not verified account execution costs.
- No forced final close: remaining inventory is marked to the last 5m close.
  Drawdown uses every 5m close for all cases. No-trade cash benchmark is 100.

## Freeze and prospective evidence

The evaluator rejects dataset starts before 2026-10-20 00:00 UTC (03:00 Bahrain)
and requires a 200-bar 15m warmup followed by at least 14 complete evaluation
days. With a start on October 20, sufficient data cannot exist until approximately
November 5. Do not claim current historical results for this candidate. The old
September/October datasets cannot be substituted as independent validation.

The report records the policy and its hash, dataset candle hash, exact evaluation
window, all three cost cases, full trade evidence, fees, net realized P&L,
expectancy, profit factor, open inventory, marked return and drawdown. Freeze the
source commit before collecting the future window. Keep a log of any later
inspections or changes; a timestamp/hash alone cannot prove independent research.
Any rule revision is a new hypothesis and needs a new untouched evaluation window.

Standalone command (only after sufficient eligible data exists):

```
python -m app.backtesting.spot_breakout_v1 --input DATASET --output NEW_REPORT
```

Run in a separate tested container with networking disabled, no credentials or
production database, datasets mounted read-only and a new output directory.
No web/worker integration, migration, app deployment or Gateway restart is needed.

## Decision and limitations

Report all five assets and all cost cases, including failures and no-trade
outcomes. Do not choose an asset or cost case afterward and call it validated.
Do not promote a candidate with negative net expectancy, cost-sensitive results
or too few closed trades to assess; report that the hypothesis is rejected or
inconclusive. A favorable simulation is only a prerequisite for separately
specified prospective Paper testing, not Live approval.

There is no simulated liquidity, spread/order-book model, partial/rejected fill,
exchange outage or daily-loss/combined portfolio control. Current instrument
rules proxy history. Five-minute OHLC cannot establish intrabar order, and
close-marked drawdown can miss intrabar risk. Protective fills are hypothetical,
not native Bybit orders. These limitations prevent execution or live certification.

## Validation

Regression tests cover prior-box exclusion, volume gating, router-independent
exits, future-candle exclusion, sparse completed-bar decisions, next-open fills,
precision/cost accounting, stop-first collisions, gap semantics, no shorts or
stacked entries, invalid stops, minimum sizes, prospective date rejection,
frozen policy hash and no-trade reports. Run the full isolated production-
equivalent suite before merge. Production strategy modules remain unchanged.
