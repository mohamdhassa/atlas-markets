# IBKR intraday hypothesis v1 — offline only

The October 24 exploratory replay covered only five measured sessions. ATR
sizing showed mixed returns and more exits. At 5 bps per leg, its simulated TSLA
overnight gap loss was $1,519 against about $535 planned price risk; the baseline
also had a gap loss. Overnight winners also mattered, including a baseline AMZN
target around $1,467. These are simulated results, not reconstructed historical
broker fills or evidence of a profitable fix.

Freeze one hypothesis before rerunning: no new entries at or after 15:00 New York
time, and close remaining positions at the 15:45 bar open with adverse exit
slippage and commission. The cutoffs are not optimized. Use all nine existing
5m datasets and all 2/5/10 bps scenarios. Compare four arms: price-fallback and
ATR sizing, each with overnight holdings allowed and with intraday restrictions.
Use one eligible signal stream, unchanged signal/router thresholds, risk and
notional parameters and the same accounting engine. Session restrictions change
which later entries are possible; this is a policy comparison, not a matched
trade attribution or isolated measurement of overnight gap cost.

Scheduled exits inspect only that bar's open, never its future high/low. A gap
through a protective level at the same open retains its gap exit reason. Stops
and targets before the cutoff remain active. The previous overnight experiment's
default behavior remains unchanged. Intraday runs must finish flat with no
cross-date closed trades. Every measured session must contain a 15:45 bar;
incomplete sessions and early-close days are rejected. There is no exchange
calendar, live broker latency or delayed-data scheduled-exit model. Full input
OHLC/volume/order/RTH/gap validation still applies.

```sh
python -m app.backtesting.ibkr_intraday_comparison \
  --input /data/SPY-5m.json --output /reports/SPY-intraday.json
```

Run with no network, read-only datasets, a new writable reports folder and the
verified research image. Do not rebuild or restart production to run research.
The prior server commands require user 0 with the host group ID for private
mounted directories; restrictive umasks may also make archived image sources
unreadable to a non-root user. Do not relax dataset permissions globally.

Reports retain full trades, marked returns, realized P&L, fees, close-marked
drawdown, remaining positions, sample labels, dataset and frozen-policy hashes.
Deltas are intraday minus overnight within the same sizing policy. Positive
return deltas and negative drawdown deltas indicate sample improvements. Returns
remain independent single-symbol account returns, not a combined portfolio.
Costs remain assumptions, short availability/borrow/financing/dividends/margin
and liquidity are omitted. Intrabar drawdown is not measured.

The hypothesis was motivated by this selected sample: reusing it is exploratory,
not out-of-sample validation. Do not tune cutoffs or select winning symbols from
these results and call that certification. Preserve regressions, missed winners,
all cost scenarios and LIMITED sample labels. A frozen subsequent holdout is
still required. Every report remains EXPLORATORY_NOT_APPROVED_FOR_ACTIVATION.
ATR remains off; no runtime strategy or account setting changes, order actions,
API/UI changes, migrations or app deployment are included in this release.
