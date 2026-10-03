# Trade and performance ledger

The Performance workspace answers two different questions without mixing them:

1. **How much capital did ATLAS start with, and what did it gain or lose?**
2. **What happened in each closed trade?**

## Provider summary

For every accessible provider profile, the summary reports:

- configured ATLAS starting capital;
- broker-confirmed net realized profit or loss;
- strategy value (`starting capital + realized P&L`);
- return percentage, win/loss count and win rate;
- raw broker equity, shown separately.

Raw Paper/Testnet equity is not treated as ATLAS capital. This matters when a broker supplies a
large simulated balance while ATLAS is intentionally sized against a USD 100 allocation.

## Closed trade rows

Each row can contain provider, asset, side, quantity, entry and exit prices, invested amount,
fees, net P&L, return, opening and closing timestamps, duration, strategy configuration,
automation decision, broker order attribution and nearby stored news.

Broker P&L remains authoritative. Entry and duration use FIFO matching of broker executions.
When the available provider history cannot prove an opening execution, those fields remain
blank rather than being invented.

`ATLAS_EXACT_ORDER` means the broker order identifier exactly matches a persisted ATLAS
automation action. `BROKER_REPORTED` means the trade is real broker history but ATLAS cannot
claim exact order attribution.

News is included only for the same symbol and only when published during the 24 hours before
the execution. It is decision context, not proof that the article caused the trade.

## Workspace ownership

- **Portfolio** owns current balances and open positions.
- **Performance** owns provider capital results and closed-trade history.
- **Users & Access** has one canonical implementation in `app/static/app.js`.

This separation removes repeated tables and makes future changes safer for developers and AI
tools.
