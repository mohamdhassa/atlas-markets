# v79 Portfolio Activity and P&L Visibility

## Scope

v79 corrects read-only portfolio observability. It does not change signal generation, risk limits, provider certification, order sizing, or Live Money gates.

## Fixes

- Preserve execution timestamps returned by IBKR, accepting epoch milliseconds, epoch seconds and ISO timestamps.
- Return normalized `executed_at` values in broker-native performance records.
- Use broker execution timestamps in the Live Activity Log.
- Keep up to 250 decisions and 200 broker fills so frequent blocked decisions cannot evict fills.
- Replace the misleading empty broker mark with a clearly labelled live market mark when candle data loads.
- Derive aggregate open P&L only when every open position has a usable live mark.
- Show an unavailable state rather than a false zero when complete marking is not possible.
- Add a Closed Positions table based only on broker-reported or safely matched realized P&L.
- Include safely matched Bybit managed-Spot entry cost when available.

## Data integrity

Opening fills are not labelled as realized profit or loss. A record appears in Closed Positions only when `pnl_available` is true. Missing broker timestamps, entry prices, marks, commissions or P&L remain unavailable; ATLAS does not invent them.

## Safety boundary

Live Money remains explicitly gated. This release is reporting and frontend visibility only.
