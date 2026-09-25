# MT5 execution-node certification runbook

ATLAS MARKETS no longer treats per-profile `bridge_url` and `bridge_token` values as MT5 infrastructure configuration.

MT5 account profiles keep only broker-account credentials (`login`, `password`, `server`). The MT5 execution node is configured centrally on the ATLAS server through:

- `MT5_BRIDGE_URL`
- `MT5_BRIDGE_TOKEN`

When no MT5 execution node is configured, MT5 is reported as `PENDING` instead of a failed broker credential connection. This allows Twelve Data, Bybit, and IBKR to remain operational while a free 24/7 native-Windows MT5 host is unavailable.

Live execution remains disabled unless explicitly enabled by the existing global and account-level safety controls. The native Windows node also defaults `ALLOW_TRADING=false`.

## Software state

The application-side integration is complete: centralized configuration, authenticated readiness reporting, broker-native account/position/order/history access, safe read retries, no POST retries, and simulation execution gates are implemented. This does **not** certify a Windows host that has not yet been installed and observed.

## Certification sequence

1. Provision an always-on native Windows host and install the broker's supported MetaTrader 5 terminal.
2. Log into the intended demo account and confirm the exact login and server name.
3. Deploy `bridges/mt5_windows`, bind it to localhost/private networking, and set a unique bridge token.
4. Keep `ALLOW_TRADING=false`; verify `/readiness`, `/account`, `/positions`, `/orders`, symbol lookup, candles and deal history.
5. Confirm ATLAS `GET /mt5/readiness` reports `simulation_ready=true` and `execution_ready=false`.
6. Set `ALLOW_TRADING=true` only for the demo account, restart the bridge, and verify `execution_ready=true`.
7. Run order-check, one minimum-size protected demo order, broker-fill reconciliation and controlled close.
8. Restart the terminal, bridge and Windows host independently; verify automatic recovery after each event.
9. Observe at least 24 hours including the broker's daily maintenance window before recording certification.

## Acceptance evidence

Record the Git commit, Windows host identifier, MT5 terminal build, broker server, account environment, readiness payload, test order/deal IDs, recovery timestamps and ATLAS application logs. Never put passwords or bridge tokens in the evidence.

Until every item passes, the provider remains `PENDING_CERTIFICATION`; other providers continue independently.
