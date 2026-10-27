# Guided IBKR Paper onboarding

## Behavior and trust boundary

Creating an application login does not launch containers. Accounts now includes
Connect IBKR Paper: request an account, obtain ADMIN approval, submit the owner's
Paper username/password privately, wait for the provisioner, approve any broker
MFA and click Verify connection. An admin can approve/reject and inspect owner
names/status. Live account IDs and environments are not accepted by this flow.

State sequence: REQUESTED → APPROVED → QUEUED → PROVISIONING → LOGIN_REQUIRED →
CONNECTED. Failure gives a fixed error code; retry requires owner credentials,
a prior approval and fewer than three attempts. ADMIN may review and reapprove
failures. Unapproved/rejected requests with no attempts can be corrected. One
onboarding request per user is supported in this first version; additional
connections remain administrator-provisioned through the existing workflow.
Unapproved requests do not reserve another owner's account ID. Approval of a
competing active request is serialized. Existing profiles are rechecked before
approval and worker claim; approved requests block conflicting manual assignments
to prevent a second Gateway login from displacing the existing connection. Final
profile assignment still checks
broker identity and global account/bridge duplicates.

The web process has no Docker socket, subprocess, host file operations or Docker
specification endpoint. A separate trusted operator worker polls a token-protected
claim endpoint, then runs a fixed Compose template with deterministic UUID
project names. User input cannot choose images, commands, paths, networks, ports
or existing production container names. Worker policy fixes an immutable app
image ID, app network, source/template hashes, maximum instances and minimum
available memory. Default limit is one additional Gateway and 2 GiB available
memory; do not increase it without capacity review. Existing production resources
are never stopped, restarted or pruned by the worker.

Docker daemon access is operator/root-equivalent. The worker is trusted
infrastructure, not an OS security sandbox for an untrusted process. Keep its
systemd unit, environment and pinned source operator-controlled. The ordinary web
application receives no Docker access. A single worker/service and private state
root is the supported topology; do not run independent workers with different
state roots against this queue. A different host additionally needs explicit
private networking to the application, which the installer does not establish.

## Credentials and broker verification

Queue login payloads are encrypted with the existing application master key;
normal API responses and audit records never include login secrets, node tokens
or encrypted blobs. The claim response is authenticated separately from app
roles and has Cache-Control: no-store. A random lease token is hashed in the DB
and expires after ten minutes. Acknowledgment or expiry reconciliation at the next worker claim erases pending
login credentials. An expired lease is displayed as review-required even if the
worker is unavailable; encrypted queued data remains until reconciliation. Lost leases fail rather than automatically deploying a second node.
A retried worker acknowledgment never repeats Docker commands.

Private per-instance host files remain mode 600 in mode-700 directories because
Gateway needs secrets for reconnects. A root initialization container copies the
login/VNC files to a project-scoped private volume with Gateway UID/GID 1000 and
mode 600. Secrets are not made world-readable. The bridge token stays in a
protected Docker secret file. No passwords are embedded in command arguments or
logs. Browser login forms clear after success/failure and use no local/session
storage. Protect worker files, Docker volumes and queue/database backups as
credentials. Removing a queue password does not remove host reconnect secrets.

The worker reports resources started, not broker login success. LOGIN_REQUIRED
means the owner must approve IBKR authentication. Some Gateway dialogs require
operator assistance through SSH-tunnelled loopback VNC; this release does not
expose a public browser VNC client or bypass broker authentication. The operator
can read the instance's loopback VNC port from private ports.json and its private
VNC secret locally. Do not paste them into chat or expose the ports publicly.

Verify checks connected=True, simulation=True and the exact expected Paper
account ID. Wrong identity/Live sessions never create a profile. A successful
profile is encrypted, owner-scoped, inactive/standby and uncertified; credentials
are not an authorization to trade. The manual template defaults to READ_ONLY_API=yes. The approved automated
worker explicitly enables the new Paper Gateway order API for later certification;
the ADMIN approval dialog states this. The app profile still starts uncertified
and in standby. Certification, activation and strategy setup remain separate
ADMIN actions, and setup itself submits no orders. Existing native protection and automation
are unchanged; Live stays disabled and ATR stays off.

## Operator installation and staged acceptance

1. Validate the immutable source in isolated containers. The release validator
   also checks the per-owner Compose configuration using dummy secret files,
   without starting any Gateway. Unit tests mock Docker; they are not evidence
   of a real authenticated Gateway or successful broker MFA.
2. Back up `atlas_markets` and capture the current image/commit. Build the merged
   source in an archive directory. Run Alembic upgrade head from the new image
   against the existing database before recreating app. Migration 20261027_0024
   only adds ibkr_onboarding and its indexes/foreign keys. It preserves all
   existing users, profiles, trades, statement evidence and research data.
3. Deploy app only with the current protection and Paper-delayed overlays,
   initially without the onboarding opt-in overlay. Verify health/schema and
   existing positions/protection. The new panel honestly reports service pending.
4. As the trusted Ubuntu operator, run
   `bash ops/ibkr-user/install-provisioner.sh MERGED_SHA` from the deployed clean
   main checkout. It installs pinned source under /opt, creates the worker system
   user/state directory, generates a private shared worker token into the
   protected existing .env.oracle and /etc/atlas-ibkr-provisioner.env, and installs
   the systemd unit without starting it. It refuses existing installations rather
   than overwriting tokens. Record a protected copy of .env.oracle before this
   one-time step. It does not deploy an additional Gateway or modify current ones.
5. Recreate app with all existing overlays plus
   `ops/docker-compose.ibkr-onboarding.yml`, supplying .env.oracle. Verify settings
   and health, then `sudo systemctl enable --now atlas-ibkr-provisioner.service`.
   Never print expanded Compose config, environment files or raw claim responses.
6. Check the worker service, then test a newly approved Paper owner end to end.
   Confirm an ordinary user cannot see another request, approve it, obtain worker
   jobs or change node assignments. Verify the expected account, standby profile,
   unchanged current IBKR holdings/protection and desktop/mobile status/error flows.
   Only then invite more owners. No new broker credentials are supplied by this PR.

Existing runtime settings are preserved except the explicit provisioning opt-in.
Operator source hashes/image IDs are pinned; software upgrades require reviewed
worker policy updates, not fetching arbitrary current code during a user request.
No Docker cleanup is exposed through the API. Failed/expired nodes may still
exist: inspect and reconcile their deterministic project before retry or manual
cleanup. Never delete resources from other projects or prune the Docker host.

## Recovery and rollback

Retain application and worker source hashes, environment, state root and Docker
volumes in protected backups. Restoring the DB without its master key loses
access to encrypted queue/profile credentials. A partial deployment/unknown ack
requires operator review; queue status is not proof that no resource was created.
The worker refuses altered manifests/source hashes and protects stable port
assignments during retries. Expiry needs a new owner submission or admin review.

To stop new provisioning, disable the app opt-in and stop the worker. This does
not remove connected accounts, Gateway resources or positions. A previous app
image may run with the additive 0024 table retained. Do not downgrade/drop the
queue table while a job or node is in use; downgrade discards onboarding audit
state and cannot clean up Docker resources. Connected nodes still use the normal
profile and protection machinery independently of the provisioning worker.
