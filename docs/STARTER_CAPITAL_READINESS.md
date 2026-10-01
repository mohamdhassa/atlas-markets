# $100 starter-capital readiness

ATLAS can size each Paper/Testnet/Demo account against an optional simulation-capital override.
Setting it to $100 makes the large broker simulation account behave like the intended first live
balance. Clearing it returns sizing to actual broker equity, so the system scales without a code
change as capital grows.

## Scalable policy

| Control | Limit |
|---|---:|
| Sizing capital | Broker equity, or optional simulation override |
| Risk per trade | Existing Risk Profile / symbol percentage |
| Maximum daily loss | Existing Risk Profile percentage |
| Maximum position notional | Existing strategy percentage |
| Maximum simultaneous positions | Existing Risk Profile setting |

The override does **not** enable Live Money and is ignored for Live accounts. Bybit remains
Testnet/Demo Spot and IBKR remains Paper.
IBKR symbols whose safe quantity is below one share use risk-sized fractional quantities rounded
down to the broker-supported 0.0001-share step. Every order must pass broker-native What-If before
submission; duplicate-symbol guards, Paper-only checks, fill reconciliation and exact-quantity exits
remain mandatory. Broker rejection blocks the order without falling back to a whole share.

## Promotion requirements

Real-money activation remains blocked until each provider has at least 30 validation trades,
positive net expectancy after transaction costs, profit factor of at least 1.2, maximum drawdown
no greater than 10%, 30 days of forward paper observation, reliable live market data and zero
unreconciled or duplicate orders. Daily-loss enforcement must use broker-authoritative realized
P&L before live activation.
