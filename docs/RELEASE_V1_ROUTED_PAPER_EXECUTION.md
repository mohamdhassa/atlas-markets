# v1 routed paper execution

The adaptive strategy router now participates in the existing certified simulation-order path.

An order can proceed only when all existing automation, account, provider, certification,
position, exposure, duplicate-order and risk gates pass **and** the router selects a strategy
whose direction agrees with the generated signal. `NO_TRADE` and directional conflicts are
recorded as explicit blockers.

Execution scope remains limited to certified simulation environments:

- Bybit Testnet or Demo Spot
- IBKR Paper, capped at the existing certified maximum of one share per order
- MT5 Demo when separately configured and certified

This release does not enable a live-money provider. Live arming does not override the certified
simulation-only automation route list.
