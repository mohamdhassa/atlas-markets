# IBKR Paper measured-ATR sizing candidate

Source audit confirms readiness omitted ATR when calling the existing execution
planner. The stop_atr_multiplier therefore multiplied a fixed 1% price fallback,
subject to the 0.5% minimum distance. Several reviewed requests match that
formula. This does not establish that ATR stops would have prevented their losses.

IBKR_PAPER_ATR_SIZING_ENABLED defaults to false. With it off, entry sizes and
stop geometry retain the baseline and snapshots explicitly identify
PRICE_PERCENT_FALLBACK. With it on, IBKR Paper readiness supplies the existing
14-period SMA true-range ATR from its completed candles. Snapshots record ATR
value/method and last bar end, plus the retained 0.5% minimum distance.
The existing multiplier, target RR, capital limits, whole-share rounding, router,
fill anchoring and broker-native protection still apply. Invalid, zero or
insufficient ATR blocks the opted-in candidate; it never silently falls back.
Live-enabled settings and non-Paper environments cannot opt in. Bybit and MT5
sizing are unchanged.

This changes a real sizing-input defect but is not a proven profitable strategy.
Smaller stops can increase stop-outs; larger stops can reduce quantity and alter
holding duration. Unit fixtures verify geometry, quantities, scope and risk
arithmetic, not returns. Keep the flag off until a baseline-versus-candidate
evaluation includes costs, long/short direction, gap behavior, identical entry
data, drawdown, and fresh out-of-sample observations. Do not optimize and certify
on the already reused Spot datasets, or treat Spot results as IBKR evidence.
Historical entry candles were not supplied in the current loss audit, so an
honest counterfactual for those trades is not yet available.

Deploy app only after full isolated container acceptance, retain both IBKR
overlays and Live disabled. This release does not enable the flag or change
existing orders, open-position protection or historical evidence. No migration.
