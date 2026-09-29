# ATLAS MARKETS v1 — IBKR Continuity Runbook

## Production components

| Component | Service/endpoint | Recovery |
|---|---|---|
| Virtual display | `atlas-ibkr-xvfb.service` | systemd restart |
| Window manager | `atlas-ibkr-fluxbox.service` | systemd restart |
| IB Gateway + IBC 10.50 | `atlas-ibkr-ibc-gateway`, host API `4002` | Docker `unless-stopped` + IBC login |
| IBC VNC | localhost port `15902` | Docker restart |
| Bridge | `atlas-markets-ibkr-bridge`, host port `8766` | Docker `unless-stopped` |
| Watchdog | `atlas-ibkr-bridge-watchdog.timer` | every 60 seconds |

The former `atlas-ibgateway.service` is preserved for rollback but must remain masked and
inactive. Starting it alongside IBC creates two Gateway processes competing for API port
`4002`.

## Historical daily restart correction

IB Gateway stores settings per internal user directory. Both stored profiles must contain
`AutoRestart=1`; otherwise the active paper profile can report `Daily auto-restart is not
enabled` and stop at the login screen after daily maintenance.

The verified active-profile correction is:

```ini
[u:oeljfbdfjdcaopacmbglefiokadfljhgbdkcbgaj]
AutoRestart=1

[u:lmlhjpipknpfikjeaacekjjnglecmonnjjgmalnl]
AutoRestart=1
```

After authentication, `/home/ubuntu/Jts/launcher.log` must contain a newer line:

```text
Daily auto-restart is enabled.
```

## Health verification

```bash
timeout 3 bash -c '</dev/tcp/127.0.0.1/4002'
curl --max-time 20 --fail --silent --show-error http://127.0.0.1:8766/health
curl --max-time 20 --fail --silent --show-error http://127.0.0.1:8766/account
systemctl is-active atlas-ibkr-bridge-watchdog.timer
```

Expected result: the configured paper account, simulation `true`, connected `true`.

## Manual authentication recovery

Periodic IBKR security authentication cannot be bypassed. From Windows PowerShell:

```powershell
ssh -N -L 15901:127.0.0.1:15902 `
  -i "<SSH_KEY_PATH>" `
  ubuntu@<ORACLE_PUBLIC_IP>
```

Keep the tunnel open, connect TigerVNC to `127.0.0.1:15901`, authenticate the Paper account,
and wait for the Gateway main screen. The watchdog restarts the bridge after port `4002`
returns. Credentials and 2FA secrets must not be stored in PostgreSQL or Git.

## Watchdog behavior

- Gateway port unavailable: log `IBKR_AUTH_REQUIRED`; do not loop-restart the login screen.
- Gateway available and bridge stale: restart only the bridge container.
- Healthy connection: log `IBKR_HEALTHY`.

## IBC production reliability

The 2026-09-29 incident proved that the bare systemd Gateway exits during its daily restart and
returns to an unauthenticated login screen. Production now uses the ARM64 IBC deployment in
`IBKR_IBC_RELIABILITY.md`. Weekly token invalidation and exceptional IBKR security challenges
still require operator approval.
