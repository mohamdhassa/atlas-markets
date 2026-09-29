# ATLAS MARKETS v1 — IBKR IBC Reliability

## Incident and root cause

On 2026-09-29 at `15:30 UTC`, IB Gateway performed its configured daily restart and exited
successfully. `atlas-ibgateway.service` used `Restart=always`, so systemd launched a new bare
Gateway process. That fresh process had no login automation, remained at authentication, kept
API port `4002` closed and caused `/account` to return `504`. The bridge watchdog correctly
reported `IBKR_AUTH_REQUIRED`; it could not authenticate Gateway.

Both stored Gateway profiles contained `AutoRestart=1`. The missing layer was a controller able
to perform a fresh Paper login after the process exits.

## Selected design

Production uses the maintained `ghcr.io/gnzsnz/ib-gateway:10.50.1e` image, which combines ARM64
IB Gateway 10.50.1e, IBC 3.24.2, Xvfb, VNC and a localhost API relay. It is pinned to a
versioned stable tag. The controlled cutover completed on 2026-09-29 and the bridge recovered
after a deliberate container restart without manual username/password entry.

Security properties:

- Paper mode only.
- Read-only API remains the default until a separate execution change is approved.
- API and VNC bind to `127.0.0.1` only.
- Passwords are Docker file secrets outside Git and PostgreSQL.
- Blind trading is disabled.
- Weekly/exceptional IBKR 2FA remains mandatory and uses the SSH/VNC procedure.

## Stage without disrupting production

After pulling the merged change, create protected configuration:

```bash
sudo install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.config/atlas/ibkr-ibc-secrets
install -m 600 /home/ubuntu/atlas-markets/ops/ibkr-ibc/.env.example \
  /home/ubuntu/.config/atlas/ibkr-ibc.env
```

Edit `/home/ubuntu/.config/atlas/ibkr-ibc.env` and replace only `TWS_USERID`. Do not paste the
username into commands, Git or chat.

Create secrets without shell history exposure:

```bash
read -rsp 'IBKR Paper password: ' IBKR_SECRET_VALUE; echo
printf '%s' "${IBKR_SECRET_VALUE}" > /home/ubuntu/.config/atlas/ibkr-ibc-secrets/tws_password
unset IBKR_SECRET_VALUE

read -rsp 'IBC VNC password: ' IBKR_SECRET_VALUE; echo
printf '%s' "${IBKR_SECRET_VALUE}" > /home/ubuntu/.config/atlas/ibkr-ibc-secrets/vnc_password
unset IBKR_SECRET_VALUE

chmod 600 /home/ubuntu/.config/atlas/ibkr-ibc.env
# The parent directory is mode 700. Compose bind-mounts local secrets, so the container UID
# needs read permission on the two files while other host users remain unable to traverse it.
chmod 644 /home/ubuntu/.config/atlas/ibkr-ibc-secrets/*
```

Pull and start on staging ports `14002` and `15902`:

```bash
docker compose --env-file /home/ubuntu/.config/atlas/ibkr-ibc.env \
  -f /home/ubuntu/atlas-markets/ops/ibkr-ibc/compose.yml pull
docker image inspect ghcr.io/gnzsnz/ib-gateway:10.50.1e \
  --format 'Image={{.Id}} Digests={{json .RepoDigests}}'
docker compose --env-file /home/ubuntu/.config/atlas/ibkr-ibc.env \
  -f /home/ubuntu/atlas-markets/ops/ibkr-ibc/compose.yml up -d
```

The first login may require IBKR Mobile approval. Access staging VNC through SSH:

```powershell
ssh -N -L 15901:127.0.0.1:15902 -i "<SSH_KEY_PATH>" ubuntu@<ORACLE_PUBLIC_IP>
```

Connect the VNC client to `127.0.0.1:15901`. Verify the Paper account and never approve a Live
session during this change.

Run `ops/ibkr-ibc/verify.sh`. Staging acceptance requires a healthy container, API port `14002`,
the correct Paper account, settings persistence after container recreation and a successful
scheduled restart without manual username/password entry. Observe for at least one full daily
restart before cutover.

The Compose `settings-init` one-shot service assigns the persistent settings volume to Gateway
UID/GID `1000:1000` before the main container starts. This prevents the `jts.ini: Permission
denied` restart loop observed during the first production activation.

## Controlled cutover

Cutover is a separately approved maintenance action:

1. Kill new ATLAS automation and record broker-native positions/orders.
2. Back up current systemd units and `/home/ubuntu/Jts/jts.ini`.
3. Stop the legacy `atlas-ibgateway.service`, preserve its unit, and mask it. Merely disabling
   it is insufficient because the historical watchdog unit can start it through `Wants=`.
4. Stop staging IBC, change `IBKR_PAPER_HOST_PORT=4002`, and start IBC.
5. Keep IBC VNC on `15902`; the existing VNC service remains available for rollback.
6. Confirm local port `4002`, start the existing watchdog, and verify `/health` plus `/account`.
7. Reconcile the Paper account before automation resumes.

Production acceptance requires the correct Paper account, bridge `connected=true`, container
health, a successful deliberate container restart and the next scheduled daily restart.

The production legacy mask is a `/dev/null` symlink at
`/etc/systemd/system/atlas-ibgateway.service`; the preserved unit is
`/etc/systemd/system/atlas-ibgateway.service.legacy-disabled`. The legacy service must remain
`masked` and `inactive` while IBC owns host port `4002`.

## Rollback

```bash
docker compose --env-file /home/ubuntu/.config/atlas/ibkr-ibc.env \
  -f /home/ubuntu/atlas-markets/ops/ibkr-ibc/compose.yml down
sudo rm /etc/systemd/system/atlas-ibgateway.service
sudo mv /etc/systemd/system/atlas-ibgateway.service.legacy-disabled \
  /etc/systemd/system/atlas-ibgateway.service
sudo systemctl daemon-reload
sudo systemctl enable --now atlas-ibgateway.service
```

Authenticate the restored Gateway through the existing VNC path, then let the watchdog recover
the bridge. Preserve IBC logs and the pulled image digest for incident analysis.

## Authentication boundary

IBC can automate routine login and weekday restarts, but it cannot bypass IBKR Mobile, passkey,
weekly token invalidation or exceptional security challenges. These events require an operator.
An authentication-required alert remains necessary even after successful cutover.
