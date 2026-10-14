# Descriptive Spot entry-cost diagnostics

After the fixed ATR candidate worsened all 15 asset/cost comparisons, this
research-only report describes the economics of the existing trade paths.
It changes no entry filters, parameters, sizing, exits or production behavior.
No winner is selected and no new threshold is promoted.

```sh
python -m app.backtesting.spot_cost_diagnostics --input DATASET --output NEW_REPORT \
  --capital 100 --fee-bps 10 --slippage-bps 2,5,10
```

Use the existing saved public Spot datasets in a read-only mount, a new output
directory and a tested isolated container with networking disabled. Files are
created exclusively. No recollection, migration or application deployment is
needed. The baseline and ATR simulators are reused unchanged; their original
validation start and continuous inventory rules remain in force.

## Measures

For each simulated entry, capture the preceding completed-bar ATR, hypothetical
1.5-ATR stop/2R target distance, notional and target economics. Approximate
round-trip cost in basis points is `2*(fee_bps+slippage_bps)`. Descriptive buckets
are target distance at most cost, at most twice cost, or above twice cost;
invalid ATR and zero modeled costs have explicit separate buckets. These are
labels for inspection, not strategy gates. Ratios for zero costs remain null.

Exact hypothetical target net P&L uses the actual modeled entry fill and entry
fee, the slipped target exit and its fee. The target anchors to the entry fill;
its net estimate therefore already starts after entry slippage. The approximate
ratio includes both legs' slippage relative to the raw entry price and need not
have the same sign threshold. For signal-only entries the target is hypothetical,
not an actual submitted order or prediction that it will be reached.

For each closed trade, the reference entry is its raw candle open and reference
exit is its exit fill before adverse exit slippage. The report reconciles:

`reference price move P&L - entry/exit slippage drag - entry/exit fees = net P&L`.

This is accounting for the same frozen trade path, not a zero-cost rerun.
Quantities, entry timing and ATR levels remain those of the costed simulation.
Reference move cannot establish an independent edge before costs. Exit prices
come from the original simulator, preserving stop gaps and capped target gaps.

Summaries include closes, entries, final open entries, median notional/holding
bars, target/cost ratios, cost buckets, fee/slippage decomposition, and positive
reference moves that became net losses. Cohorts use entry routes and descriptive
cost buckets. Closed totals exclude final open-entry fees; those are reported
separately. Full per-entry evidence stays in the JSON report; console output
contains overall summaries only.

## Limits and release validation

These datasets have already been inspected. Cohorts are observational and
dependent; subgroup performance is not proof that filtering will improve
returns. Current size rules and modeled fees are assumptions, not historical
broker verification. Independent assets are not a combined portfolio. Reports
retain non-executable/non-live-eligible status and no parameter optimization.

Regression tests verify exact decomposition, costs erasing positive reference
moves, hypothetical target economics against actual simulated target fills,
invalid/zero-cost cases, unchanged policy outcomes, open-entry separation,
group totals, invalid evidence and exclusive output. Full production-equivalent
container tests are required before merge; this is an offline research release.
