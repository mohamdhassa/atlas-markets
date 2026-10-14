# Signal, router and exit audit — 2026-10-14

Audited source: main `64b36422e9c0e637aac5f3adba1d18b96fa19816`.
This is a source/behavior audit, not a production change or broker certification.
No thresholds, strategy rules, orders, risk controls or data were changed.

## Confirmed findings

### 1. Signal strength measures directional balance, not evidence magnitude

`app/analysis/strategy_intelligence.py::scenario_from_candles` calculates
`50 + 40*(bull-bear)/max(bull+bear,1)` and labels it bullish probability.
Five bullish points against zero bearish points and 72 bullish points against
zero bearish points both yield 90. A minimum strength of 65 therefore does not
require a fixed number or absolute weight of confirmations. The number is a
heuristic score; no calibration against realized outcomes is present here.

`app/analysis/technical.py::rsi` returns 100 whenever losses are zero, including
when gains are also zero. A reproducible 200-bar flat-close fixture with
open/close=100, high=101, low=99 and volume=1000 produces SELL strength 90,
with `rsi_overbought_risk`, despite neutral EMA/structure and zero MACD.
The real router returns NO_TRADE for this fixture, so this example does not
prove that a flat-market order is submitted. It does expose a score/indicator
edge case independently of routing. Fixing it would change trading signals.

### 2. Route names are filters around one engine

`app/services/signal_risk.py::generate_signal` always calls the same scenario
engine; no strategy family argument selects a separate implementation.
`autotrade_readiness` then adds `_router_blocker`. Trend uses a moving-average
regime/direction gate; Darvas checks completed prior-box close breakout and
volume confirmation. Mean reversion uses a RANGING regime but the blocker
adds no oversold/overbought distance, rejection, reversion target or directional
reversal rule. Therefore the route cannot be treated as an independently
implemented mean-reversion strategy. The existing evidence snapshot accurately
records `router_role=ENTRY_FILTER`.

Router branch order matters: high volatility, then moving-average trend, then
confirmed box breakout, then low volatility, then range. A box breakout with
a strong enough trend receives the trend label. This is source precedence,
not proof of a defect or of which family caused the return. Route cohorts in
the research remain observational labels from the shared engine.

### 3. Bybit exit lifecycle uses the entry router gate

Readiness applies `_router_blocker(route, generated.decision)` before handling
Bybit managed SELL inventory. Consequently NO_TRADE blocks a SELL, and a
TRENDING_UP route rejects SELL with STRATEGY_ROUTER_DIRECTION_CONFLICT even
when it would reduce existing managed inventory. Position-slot and portfolio
entry guards are already bypassed for managed SELLs; the router gate is not.
The offline signal baseline reproduces this eligible-SELL requirement.

Bybit Spot submission does not send the sizing plan's stop/target. Readiness
also omits measured ATR when building that plan, using its price-percent
fallback. Those previously documented facts remain confirmed. The offline ATR
experiment is hypothetical and cannot establish native Bybit protection.

IBKR behaves differently: its position manager can close on an opposite shared
signal without the entry router when native protection is disabled. With
native protection enabled, the broker-held protective lifecycle owns exits and
the manager deliberately does not race it with an opposite-signal order.
That protection behavior must remain intact.

### 4. IBKR 3m requests silently return 5m bars

`tools/ibkr_bridge.py::bar_size` has no 3m mapping and defaults to `5 mins`.
`/candles` still labels its response with the requested timeframe. Reproduced
locally: `bar_size('3m') == '5 mins'`. The earlier TSLA configuration requested
3m; current server configuration was not re-read in this audit. This needs
correct mapping or explicit unsupported-timeframe rejection, with regression
coverage and provider validation before a bridge deployment.

### 5. Live-input parity with completed-bar research is not enforced here

`app/market_data/bybit.py::get_candles` sorts returned bars but does not filter
them by a completion cutoff. Readiness passes all returned bars to the engine
and router. Thus it does not exclude a forming last bar if one is returned.
The live IBKR candle path likewise exposes no explicit completion cutoff in
the inspected endpoint. Actual provider responses were not sampled in this
audit; do not claim that a specific recorded trade used a forming bar.
The offline collectors/evaluators intentionally use completed candles only.

## Recommended implementation order

1. Establish input integrity: accurate requested/actual timeframe and completed-
   bar boundaries. Preserve chart behavior while enforcing completed inputs at
   the trading decision boundary. Test UTC boundaries and provider timestamps.
2. Specify and test zero-change RSI handling and score semantics in research.
   An evidence threshold requires a defined rule; do not invent a calibrated
   probability or silently substitute an optimized threshold.
3. Define inventory-aware exit policy separately from entry eligibility. Any
   Bybit exit change must preserve owner/profile scope, managed inventory,
   broker verification, minimums, duplicate handling and simulation gates.
4. Specify family-specific research rules if independent strategies are desired.
   Keep route labels honest until separate engines exist. Do not retrospectively
   relabel old trades or promote favorable small cohorts.
5. Freeze revised rules before evaluation on fresh prospective data. Existing
   repeated six-week experiments do not provide a new independent holdout.

## Verification and limits

Read the signal/technical/router code, readiness, Bybit submission, IBKR manager,
market candle adapter, bridge and relevant unit tests. Locally reproduced the
flat-close SELL-90/NO_TRADE pair, uptrend SELL conflict and 3m-to-5m fallback.
No production session, credentials, provider queries or database mutations
were used. This audit does not establish which finding caused a particular
historical loss. No behavior fix or live-money eligibility is delivered here.
