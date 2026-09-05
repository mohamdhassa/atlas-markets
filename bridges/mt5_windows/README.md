# ATLAS Windows MT5 Bridge

This bridge is the Windows execution node for Fusion Markets MT5. The ATLAS backend remains on Oracle Linux; native MetaTrader 5 runs on Windows and is reached through a private reverse SSH tunnel.

## Security defaults

- Binds to `127.0.0.1` only.
- Requires `X-ATLAS-BRIDGE-TOKEN` on every route.
- Locks the expected MT5 login and server.
- Serializes MetaTrader5 API access with a process lock.
- `ALLOW_TRADING=false` by default.
- `/order` and `/positions/{ticket}/close` refuse execution while trading is disabled.

## Run

Create `.env` from `.env.example` and set a private token. Never commit `.env`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765 --env-file .env
```

Keep Uvicorn at one worker because the MetaTrader5 terminal API is process-local and bridge calls are serialized.

## Architecture

```text
ATLAS MARKETS on Oracle Linux
  -> Docker host relay 172.19.0.1:18765
  -> reverse SSH tunnel
  -> Windows 127.0.0.1:8765
  -> native MetaTrader 5
  -> FusionMarkets-Demo
```

The current bridge is not independent of the Windows machine. If the Windows PC is shut down, sleeping, logged out in a way that stops the processes, or loses Internet connectivity, both the bridge and reverse SSH tunnel become unavailable and ATLAS cannot read or trade the MT5 account. For 24/7 production operation, run this bridge and native MT5 on an always-on Windows VPS/VM and configure automatic service/task startup.
