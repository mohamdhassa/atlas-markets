#!/usr/bin/env bash
# One-time trusted operator installation after immutable commit acceptance and merge.
set -Eeuo pipefail
candidate=${1:-}
[[ $candidate =~ ^[0-9a-f]{40}$ ]] || { echo 'Usage: bash install-provisioner.sh MERGED_SHA';exit 2; }
repo=$(git rev-parse --show-toplevel)
git merge-base --is-ancestor "$candidate" origin/main
[[ $(git rev-parse HEAD) = "$candidate" ]] || { echo "Deploy the pinned accepted commit first";exit 1; }
command -v docker >/dev/null
command -v systemctl >/dev/null
command -v sudo >/dev/null
source_dir="/opt/atlas-ibkr-provisioner/releases/$candidate"
[[ ! -e /etc/atlas-ibkr-provisioner.env ]] || { echo 'Existing installation: review rather than overwrite';exit 1; }
# The app must be deployed at this exact accepted revision before installing its worker.
docker exec atlas-markets-prod-app python -c 'from app.api.routes_ibkr_onboarding import configured; print("ONBOARDING_API_PRESENT")'
image=$(docker inspect atlas-markets-prod-app --format '{{.Image}}')
network=$(docker inspect atlas-markets-prod-app --format '{{range $key, $_ := .NetworkSettings.Networks}}{{println $key}}{{end}}' | sed '/^$/d')
[[ $(printf '%s\n' "$network" | wc -l) = 1 ]] || { echo 'Select one app network explicitly before installation';exit 1; }
sudo install -d -m 0755 "$source_dir"
git archive "$candidate" | sudo tar -x -C "$source_dir"
sudo chmod -R a+rX "$source_dir"
id atlas-provisioner >/dev/null 2>&1 || sudo useradd --system --home-dir /var/lib/atlas-ibkr-provisioner --shell /usr/sbin/nologin atlas-provisioner
sudo install -d -m 0700 -o atlas-provisioner -g atlas-provisioner /var/lib/atlas-ibkr-provisioner
sudo -u atlas-provisioner -g docker docker compose version >/dev/null || { echo "Install Compose as a system-wide Docker plugin before continuing";exit 1; }
# No token is printed or passed in process argv.
sudo python3 - "$repo/.env.oracle" "$source_dir" "$image" "$network" <<'PY'
import hashlib,os,secrets,sys
from pathlib import Path
application,source,image,network=sys.argv[1:]
p=Path(application)
text=p.read_text()
if any(line.startswith('IBKR_PROVISIONER_TOKEN=') for line in text.splitlines()):
    raise SystemExit('Existing application provisioner token: manual review required')
token=secrets.token_urlsafe(48)
values={
 'ATLAS_PROVISION_API':'http://127.0.0.1:8100',
 'ATLAS_PROVISION_TOKEN':token,'ATLAS_PROVISION_ROOT':'/var/lib/atlas-ibkr-provisioner',
 'ATLAS_PROVISION_SOURCE':source,'ATLAS_PROVISION_IMAGE':image,
 'ATLAS_PROVISION_NETWORK':network,'ATLAS_PROVISION_MAX_INSTANCES':'1',
 'ATLAS_PROVISION_MIN_MEMORY_MB':'2048'}
for key,relative in [('ATLAS_PROVISION_COMPOSE_SHA256','ops/ibkr-user/compose.yml'),('ATLAS_PROVISION_BRIDGE_SHA256','tools/ibkr_bridge.py')]:
    values[key]=hashlib.sha256((Path(source)/relative).read_bytes()).hexdigest()
if any('\n' in v or '\r' in v for v in values.values()):raise SystemExit('Invalid operator configuration')
fd=os.open('/etc/atlas-ibkr-provisioner.env',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(''.join(k+'='+v+'\n' for k,v in values.items()))
with p.open('a') as f:f.write('\nIBKR_PROVISIONER_TOKEN='+token+'\n')
os.chmod(p,0o600)
PY
sudo sed "s|/opt/atlas-ibkr-provisioner/ops|$source_dir/ops|" "$source_dir/ops/ibkr-user/provisioner.service" | sudo tee /etc/systemd/system/atlas-ibkr-provisioner.service >/dev/null
sudo systemctl daemon-reload
# Operator starts/enables only after the app's opt-in overlay and migration are verified.
echo 'WORKER_INSTALLED_NOT_STARTED'
echo 'Next: enable the app onboarding overlay, verify health, then enable/start atlas-ibkr-provisioner.service.'
