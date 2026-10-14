# Exploratory Spot exit comparison

This offline experiment compares the unchanged signal-exit baseline with
`signal_plus_atr`: eligible SELL exits plus fixed ATR-triggered protection.
It changes no production orders, settings, broker connections or databases.

Run against the existing provenance-tagged Spot datasets:

```sh
python -m app.backtesting.spot_exit_comparison --input DATASET --output NEW_REPORT \
  --capital 100 --fee-bps 10 --slippage-bps 2,5,10
```

Files are created exclusively. Mount datasets read-only and use a separate
output directory in the tested research container with `--network none`.
No application deployment, Gateway restart or data recollection is required.

## Frozen experiment

Both policies keep the baseline signal engine, router gates, strength threshold,
next-open entry fills, order-size limits, fees and position sizing. Sizing still
uses readiness's price-percent fallback; this experiment changes exits only.
Different exits can change available cash and subsequent entry opportunities,
so the policies need not produce identical trade lists.

The candidate captures mean true range over the preceding 14 completed bars
(the application's arithmetic-mean ATR, not Wilder smoothing). Stop distance
is exactly 1.5 ATR; target distance is twice the stop distance. Levels anchor
to the modeled entry fill and remain fixed. Invalid ATR/levels block the entry.
These parameters were fixed before this comparison; there is no parameter grid
or automated winner selection.

Opening protective triggers precede eligible SELL market exits; intrabar triggers
then apply to remaining inventory, including the entry candle. A stop gap uses
the opening price, followed by adverse exit slippage. A favorable target gap
is capped at the target, followed by adverse slippage. When both levels touch
in one candle, the stop wins. A BUY generated while holding cannot reenter on
the same candle after a protective exit. Dust remains inventory, not a fake fill.

The candidate models hypothetical market-trigger exits. It does not reproduce
native limit orders, guaranteed stops, order-book liquidity, OCO handling,
partial fills or rejections. Existing Bybit production submits no such stops.

## Evidence and limits

The baseline report remains reproducible. Both policies use the same continuous
validation window after 200 warmup bars and 2016 initial diagnostic bars.
Disjoint 1008-bar slices group closes by exit candle; inventory carries across
slices and final holdings remain marked. Net P&L, fees, expectancy, profit factor,
marked equity, candle-close drawdown, route groups and exit reasons are reported.
Training is not used to select parameters. Each asset has its own 100 USDT;
these are not combined portfolio returns.

The six-week datasets have already been inspected. Reusing them after observing
baseline losses makes this an exploratory policy comparison, not a fresh
independent holdout. Any apparent improvement needs new prospective paper
evidence before further conclusions. Every report retains `executable=false`,
`live_eligible=false` and `parameter_optimization=false`.

## Release validation

Regression coverage checks previous-candle ATR, unchanged initial sizing/costs,
fixed levels, entry-candle ambiguous triggers, adverse gaps, signal priority,
no duplicate exits/reentry, size/dust gates, cross-slice inventory, exact
baseline reproduction and exclusive output. Run the full suite in the isolated
production-equivalent container before merging. Production behavior is unchanged.
