# Exploratory IBKR ATR comparison

This offline research compares the current price-percentage fallback against
14-period completed-candle ATR. It does not enable the candidate, modify account
settings, submit orders or recreate production containers. Keep
IBKR_PAPER_ATR_SIZING_ENABLED=false and Live disabled.

The read-only collector exports nine symbols from an authenticated Paper bridge,
up to 1,000 RTH TRADES bars each. It verifies the returned interval and excludes
unfinished candles. The comparison rejects invalid OHLC, volume, duplicate bars,
intraday gaps and timestamps outside weekday New York regular hours. It does
not implement an exchange holiday/early-close calendar. A short export is not a
full replay of the October losses; entry-time history and broker latency cannot
be reconstructed from closing P&L alone.

Both policies share the current signal/router stream from preceding 200 bars,
strength 65, risk 1%, multiplier 1.5, RR 2 and notional cap 20%. Different holding
durations can produce different executed entries. Each symbol has an independent
$250,000 account; results must not be summed into a portfolio return. Entries
execute at the next open, stops are anchored to the modeled fill and quantity
is rounded down. Short and long trades use the same risk constraints. Protection
is assumed immediate and available during RTH. Adverse gaps fill at the open;
favorable target gaps fill at the target; both-touch bars use the stop first.

Costs are assumptions: $0.005/share with $1 minimum per leg, and separate
2/5/10-basis-point adverse slippage scenarios per leg. They are not verified
account fees. Borrow costs/availability, financing, dividends, regulatory fees,
order-book liquidity, broker rejects, partial fills and delayed-data execution
are omitted. Reported drawdown uses bar closes and misses intrabar excursions.
Open trades remain marked, not forced closed. These limitations prevent claims
that the candidate would have avoided a particular historical loss.

Run after isolated full-suite acceptance using the tested research source:

```sh
python -m app.scripts.collect_ibkr_atr_research \
  --profile-id PAPER_PROFILE_UUID --output /new/export --timeframe 5m
python -m app.backtesting.ibkr_atr_comparison \
  --input /data/SPY-5m.json --output /new/reports/SPY-5m.json
```

The collector needs the existing application environment and only reads profile
credentials locally. Do not copy credentials or production environment files into
the offline comparison. Run comparison containers with networking disabled and
read-only input mounts. Export/report paths refuse overwrites. Preserve JSON
reports, dataset hashes, policy hashes and the exact source commit.

Reports include net closed P&L, marked return, close-marked drawdown, profit factor,
commissions, open positions and trade details. Fewer than 20 measured sessions or
30 closed trades is LIMITED. Larger samples remain DESCRIPTIVE_ONLY. Every report
is EXPLORATORY_NOT_APPROVED_FOR_ACTIVATION: improvement on this selected recent
sample is insufficient to activate. Freeze the policy before collecting a fresh
holdout, compare all cost scenarios and symbols, and investigate any regressions.
No migration or production deployment is required for this research release.
