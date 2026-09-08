# ATLAS Native Windows MT5 Execution Node

ATLAS keeps the main application on Oracle Linux and connects MT5 through a native Windows terminal. This avoids Wine-specific MT5 authentication failures while keeping MT5 infrastructure details out of end-user account forms.

## Security defaults

- The bridge is intended to bind to `127.0.0.1` only.
- Every API call requires `X-ATLAS-BRIDGE-TOKEN`.
- The node locks itself to one expected MT5 login and server.
- `ALLOW_TRADING=false` is the default and must remain false during integration testing.
- MT5 API access is serialized with a process lock.
- `MT5_TERMINAL_PATH` can pin the bridge to a specific terminal installation.

## User-facing account fields

Users provide only:

- MT5 login
- MT5 password
- MT5 server

`bridge_url` and `bridge_token` are infrastructure settings and are configured on the ATLAS server with `MT5_BRIDGE_URL` and `MT5_BRIDGE_TOKEN`.

## Run on Windows

Create `.env` from `.env.example`, set a long private token, the expected demo login/server, and optionally `MT5_TERMINAL_PATH`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765 --env-file .env
```

Keep one Uvicorn worker.

## ATLAS server settings

The ATLAS backend uses:

```text
MT5_BRIDGE_URL=http://<private-or-relay-address>:<port>
MT5_BRIDGE_TOKEN=<same-private-token>
```

Existing profiles that still contain legacy `bridge_url` / `bridge_token` values continue to work as a migration fallback, but new profiles no longer store those infrastructure values.

## 24/7 deployment

For true PC-independent MT5 operation, run the native Windows terminal and this execution node on an always-on Windows VM/VPS, then connect it privately to Oracle. A Linux/Wine MT5 terminal is not used in the production path.

The bridge can serve Fusion Markets, MetaQuotes-Demo, or another MT5 broker as long as the native Windows terminal is successfully logged into the configured account/server.
