# MT5 pending execution node

ATLAS MARKETS no longer treats per-profile `bridge_url` and `bridge_token` values as MT5 infrastructure configuration.

MT5 account profiles keep only broker-account credentials (`login`, `password`, `server`). The MT5 execution node is configured centrally on the ATLAS server through:

- `MT5_BRIDGE_URL`
- `MT5_BRIDGE_TOKEN`

When no MT5 execution node is configured, MT5 is reported as `PENDING` instead of a failed broker credential connection. This allows Twelve Data, Bybit, and IBKR to remain operational while a free 24/7 native-Windows MT5 host is unavailable.

Live execution remains disabled unless explicitly enabled by the existing global and account-level safety controls. The native Windows node also defaults `ALLOW_TRADING=false`.
