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

The watchdog treats the IBC Gateway container health check as authoritative. The published
host API port is proxied by `socat` and can remain open even when the Gateway process inside the
container is refusing API connections; a TCP probe alone is not Gateway readiness.

Recovery order is Gateway first, bridge second:

1. If Gateway health is `starting`, wait without restarting it.
2. If Gateway is stopped or unhealthy, restart it once and wait for container health.
3. Apply a recovery cooldown so an IBKR authentication/2FA prompt is not destroyed by a
   restart every minute.
4. Only after Gateway is healthy, verify the host endpoint and recover a stale bridge.
5. Never restart ATLAS, PostgreSQL or Redis for an IBKR provider incident.

`IBKR_AUTH_REQUIRED` after the wait means automated login did not complete and VNC/mobile
approval may be required. `IBKR_GATEWAY_RECOVERY_COOLDOWN` means a recent recovery already ran
and the watchdog is intentionally preserving the current authentication session.

- Gateway port unavailable: log `IBKR_AUTH_REQUIRED`; do not loop-restart the login screen.
- Gateway available and bridge stale: restart only the bridge container.
- Healthy connection: log `IBKR_HEALTHY`.

## IBC production reliability

The 2026-09-29 incident proved that the bare systemd Gateway exits during its daily restart and
returns to an unauthenticated login screen. Production now uses the ARM64 IBC deployment in
`IBKR_IBC_RELIABILITY.md`. Weekly token invalidation and exceptional IBKR security challenges
still require operator approval.
