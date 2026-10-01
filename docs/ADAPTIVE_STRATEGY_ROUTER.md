# Adaptive strategy router

ATLAS evaluates market structure before selecting an eligible strategy family. It does not
force one strategy across all symbols or market conditions.

## Initial routing policy

| Regime | Eligible families | Default route |
|---|---|---|
| Confirmed consolidation breakout | Darvas Box, breakout | Darvas Box |
| Sustained directional movement | Trend, momentum, pullback | Trend |
| Range-bound movement | Mean reversion, Darvas Box observation | Mean reversion |
| Low volatility without breakout | Darvas Box observation | No trade |
| High volatility | News breakout, volatility | No trade until confirmed |
| Extreme news uncertainty | None | No trade |

Darvas Box boundaries use completed candles only. A route requires a close beyond the box plus
volume confirmation. The router reports `NO_TRADE` when evidence or confidence is insufficient.

## Safety and rollout

The router is integrated into shadow observations and exposed at
`POST /analysis/strategy-router/from-candles`. It is advisory (`SHADOW`, `executable=false`) and
cannot independently submit, authorize or promote an order. The existing safe-automation service
may use its output as one additional gate for already-certified paper/testnet routes. Existing
execution gates, account ownership, provider certification and risk controls remain authoritative.

Promotion requires walk-forward validation, transaction costs, sufficient settled shadow trades
and forward paper observation. Profit is never guaranteed, and routing must be evaluated by
expectancy, drawdown, profit factor and stability rather than headline return alone.
