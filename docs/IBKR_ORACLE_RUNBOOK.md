# ATLAS MARKETS — IBKR Paper on Oracle Runbook

Last updated: 2026-09-05

## Verified production state

IBKR Paper has been migrated onto the Oracle `atlas-trader` host and verified through the production ATLAS application.

Verified path:

```text
ATLAS production app
  -> IBKR HTTP bridge :8766
  -> IB Gateway API 127.0.0.1:4002
  -> Interactive Brokers Paper account DUR980544
```

Production verification on 2026-09-05 returned PASS for Twelve Data, Fusion MT5 Demo, Bybit Testnet, and IBKR Paper. IBKR reported simulation mode with account data, positions and orders available through the bridge.

## Oracle host

- Host role: ATLAS production application + IBKR Paper execution node
- OS: Ubuntu 20.04 LTS ARM64 (`aarch64`)
- IB Gateway: 10.45 Stable ARM64
- Install path: `/home/ubuntu/Jts/ibgateway/1045`
- Virtual X display: `:99`
- IBKR Paper API socket: `127.0.0.1:4002`
- ATLAS IBKR HTTP bridge: port `8766`
- Bridge client ID: `27`
- Paper account: `DUR980544`

## Runtime architecture

```text
Oracle host
  |
  +-- Xvfb :99
  |     `-- Fluxbox
  |           `-- IB Gateway 10.45
  |                 `-- Paper API 127.0.0.1:4002
  |
  +-- atlas-markets-ibkr-bridge (Docker, host networking)
  |     `-- connects to 127.0.0.1:4002
  |
  `-- atlas-markets-prod-app
        `-- calls IBKR bridge :8766
```

The IBKR bridge must not be exposed publicly.

## systemd services

The following services are enabled at boot:

```text
atlas-ibkr-xvfb.service
atlas-ibkr-fluxbox.service
atlas-ibkr-gateway.service
```

Check them with:

```bash
systemctl is-enabled atlas-ibkr-xvfb atlas-ibkr-fluxbox atlas-ibkr-gateway
systemctl --no-pager --full status atlas-ibkr-xvfb atlas-ibkr-fluxbox atlas-ibkr-gateway
```

Expected result: all three are enabled and active after startup.

## Authentication limitation

Starting IB Gateway automatically does not guarantee an authenticated IBKR session. Interactive Brokers may require username/password and 2FA after restart, logout, session expiry, maintenance or a security reset.

ATLAS does not store or automate IBKR login credentials or 2FA in this runbook.

If Gateway is running but this fails:

```bash
nc -vz 127.0.0.1 4002
```

then use the secure VNC recovery procedure below and authenticate to IBKR Paper manually.

## Secure VNC recovery

Run VNC only on Oracle loopback:

```bash
x11vnc -display :99 -localhost -forever -shared -rfbport 5901 > /tmp/atlas-x11vnc.log 2>&1 &
```

Verify it is private:

```bash
sudo ss -ltnp | grep 5901
```

It should listen on `127.0.0.1:5901` / `::1:5901`, not a public interface.

From an administrator Windows PowerShell session, create an SSH local tunnel to Oracle and leave that terminal open:

```powershell
ssh -N -L 5901:127.0.0.1:5901 -i "<PATH-TO-ORACLE-SSH-KEY>" ubuntu@<ORACLE-PUBLIC-IP>
```

Then connect the VNC viewer to:

```text
127.0.0.1:5901
```

Authenticate directly inside IB Gateway Paper and complete any required 2FA. Never paste IBKR credentials into shell commands, logs, documentation or Git.

## Recovery verification

After authentication:

```bash
nc -vz 127.0.0.1 4002
```

Expected: connection succeeds.

Restart the bridge so it establishes a fresh API session:

```bash
docker restart atlas-markets-ibkr-bridge
sleep 5
curl -sS http://127.0.0.1:8766/account
```

Expected: JSON for `DUR980544` with `simulation: true`.

Then certify the full production integration stack:

```bash
docker exec atlas-markets-prod-app python -m app.scripts.verify_integrations
```

Expected provider state:

```text
TWELVE_DATA  PASS
MT5 DEMO     PASS
BYBIT TESTNET PASS
IBKR PAPER   PASS
```

## Troubleshooting

### `/account` returns 504

Check the API listener:

```bash
nc -vz 127.0.0.1 4002
```

If refused, verify Gateway is running and authenticate through VNC.

If port 4002 succeeds, check whether the bridge has an established socket:

```bash
sudo ss -tnp | grep 4002
```

Then restart the bridge:

```bash
docker restart atlas-markets-ibkr-bridge
sleep 5
docker logs --tail 100 atlas-markets-ibkr-bridge
```

A healthy startup reports connection to `127.0.0.1:4002`, client ID 27, account `DUR980544`, and the configured market-data mode.

### Bridge health works but account times out

`/health` only proves the HTTP bridge is alive. It does not prove that the bridge has a usable authenticated IB Gateway API session. Check port 4002, the established TCP connection, Gateway authentication, and then restart the bridge.

### Market data

The verified bridge can operate in delayed market-data mode. Delayed data is not equivalent to real-time execution-quality pricing. Appropriate IBKR API market-data subscriptions are recommended before relying on IBKR pricing for broad automated stock/ETF execution tests.

## Security rules

- Keep IB Gateway API on localhost unless there is a documented private-network reason to change it.
- Keep VNC on localhost and reach it through SSH tunneling.
- Do not expose ports 4002, 5901 or 8766 publicly.
- Do not commit IBKR passwords, 2FA codes, API secrets or SSH private keys.
- Keep the account in Paper/simulation mode until Live Money is separately approved and certified.

## Remaining 24/7 dependency

IBKR Paper is now hosted on the always-on Oracle server. Fusion MT5 is still a separate dependency: until native Windows MT5 and the secured MT5 bridge are moved from the administrator's personal Windows PC to an always-on Windows VPS/VM, ATLAS is not fully independent of that PC.
