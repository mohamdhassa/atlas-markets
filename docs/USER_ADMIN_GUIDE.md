# ATLAS MARKETS v1 — User and Administrator Guide

## Roles

- `ADMIN`: user management, integrations, certification, strategies, risk and automation.
- `USER`: owned accounts, strategies, portfolio, reports and analysis only.

## Daily operating sequence

1. Confirm `/health` and dependency status.
2. Confirm each required provider account is connected and active.
3. Review kill-switch state, latest scan and next scan.
4. Review broker-native positions, orders/fills and realized/unrealized P&L.
5. Inspect decisions, risk blocks, skips and provider errors.
6. Review shadow coverage separately from broker performance.
7. Use the broker portal/Gateway as final truth for holdings and fills.

## Strategy interpretation

- `WATCH`: observe only.
- `SIGNALS`: compute and display decisions without execution.
- `AUTO_TRADE`: eligible for provider/risk preflight; execution is not guaranteed.

Each symbol is independently scoped to owner, provider profile, market and symbol, with
optional overrides for timeframe, strength, risk, stop, reward and position notional.

## Portfolio interpretation

- Portfolio: current broker balances and open broker-held exposure only.
- Performance: starting allocation, realized gain/loss, strategy value and closed-trade ledger.
- Broker equity: the provider's raw Paper/Testnet balance; it is not the ATLAS allocation.
- Strategy value: configured starting allocation plus broker-confirmed realized P&L.
- Orders/fills: provider events plus ATLAS lineage when an exact order match exists.
- Realized P&L: closed broker result after available costs; broker P&L is authoritative.
- Unrealized P&L: current mark-to-market result.
- Shadow result: hypothetical, non-executable forward observation.

News shown beside a trade is same-symbol context stored during the prior 24 hours. It does not
prove that the news caused the decision. A `BROKER_REPORTED` attribution likewise must not be
presented as an ATLAS-generated trade unless an exact persisted order match exists.

## Automation controls

Open **Operations** as ADMIN to run a monitored scan, pause automation, enable automation
and clear kill, or activate the kill switch. USER sees status only. Enable preserves the
existing simulation execution setting; scan is unavailable while that setting is off.

Kill prevents new automated submissions; it does not liquidate positions. Restart resumes
only after operator review and reconciliation. Scan Now requests a cycle while all safety
gates remain active.

## Troubleshooting

- `401`: authenticate again.
- `502/503`: inspect the named provider/dependency independently.
- IBKR `connected:false`: follow `IBKR_CONTINUITY.md`.
- Page asset mismatch after deployment: use `Ctrl+F5` after backend health is confirmed.
