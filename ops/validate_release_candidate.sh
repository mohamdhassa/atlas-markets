#!/usr/bin/env bash
# Validate a pinned Git commit in disposable containers. Never loads production .env.
set -Eeuo pipefail

candidate=${1:-}
if [[ ! $candidate =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Usage: bash ops/validate_release_candidate.sh <full-40-character-commit>' >&2
  exit 2
fi
command -v docker >/dev/null
docker info >/dev/null
repo=$(git rev-parse --show-toplevel)
git -C "$repo" cat-file -e "$candidate^{commit}"
scratch=$(mktemp -d /tmp/atlas-release-validation.XXXXXXXX)
run_name="atlas-verify-${candidate:0:10}-$$"
image="$run_name:verify"
app_image="$run_name:app"
network_id=''
image_built=false
app_image_built=false
owned_containers=()
cleanup() {
  result=$?
  trap - EXIT
  for container_id in "${owned_containers[@]}"; do
    docker rm -f -v "$container_id" >/dev/null 2>&1 || true
  done
  if [[ -n $network_id ]]; then docker network rm "$network_id" >/dev/null 2>&1 || true; fi
  if $image_built; then docker image rm "$image" >/dev/null 2>&1 || true; fi
  if $app_image_built; then docker image rm "$app_image" >/dev/null 2>&1 || true; fi
  rm -rf -- "$scratch"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir "$scratch/source" "$scratch/results"
git -C "$repo" archive "$candidate" | tar -x -C "$scratch/source"
echo "Validating immutable commit $candidate"
if [[ -f "$scratch/source/ops/ibkr-user/compose.yml" ]]; then
  mkdir "$scratch/template-secrets"
  for secret in tws_password vnc_password bridge_token; do
    : > "$scratch/template-secrets/$secret"
  done
  env IBKR_INSTANCE=validation TWS_USERID=validation IBKR_ACCOUNT_ID=DUVALIDATION \
    IBKR_SECRET_DIR="$scratch/template-secrets" \
    IBKR_BRIDGE_SOURCE="$scratch/source/tools/ibkr_bridge.py" \
    IBKR_VNC_HOST_PORT=19998 IBKR_BRIDGE_HOST_PORT=19999 \
    ATLAS_APP_IMAGE=python:3.12-slim ATLAS_APP_NETWORK=validation-only \
    docker compose --env-file /dev/null -p atlas-template-check \
      -f "$scratch/source/ops/ibkr-user/compose.yml" config --quiet
  echo 'IBKR per-owner Compose configuration validated without starting services'
fi

docker build --tag "$app_image" "$scratch/source"
app_image_built=true
docker build --build-arg "APP_IMAGE=$app_image" --tag "$image" \
  --file "$scratch/source/ops/Dockerfile.validation" "$scratch/source"
image_built=true
network_id=$(docker network create --internal "$run_name")

# Test credentials exist only for these containers; no host connection settings are reused.
POSTGRES_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_hex(24))')
export POSTGRES_PASSWORD
pg_id=$(docker create --network "$network_id" --network-alias verify-postgres \
  -e POSTGRES_USER=atlas_verify -e POSTGRES_DB=atlas_markets_verify \
  -e POSTGRES_PASSWORD postgres:17-alpine)
owned_containers+=("$pg_id")
redis_id=$(docker create --network "$network_id" --network-alias verify-redis redis:7-alpine)
owned_containers+=("$redis_id")
docker start "$pg_id" "$redis_id" >/dev/null
ready=false
for attempt in {1..30}; do
  if docker exec "$pg_id" pg_isready -U atlas_verify -d atlas_markets_verify >/dev/null 2>&1 \
    && docker exec "$redis_id" redis-cli ping >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if ! $ready; then echo 'Disposable database/Redis did not become ready.' >&2; exit 1; fi
DATABASE_URL="postgresql+psycopg://atlas_verify:$POSTGRES_PASSWORD@verify-postgres:5432/atlas_markets_verify"
TEST_DATABASE_URL=$DATABASE_URL
REDIS_URL='redis://verify-redis:6379/0'
TEST_REDIS_URL=$REDIS_URL
export DATABASE_URL TEST_DATABASE_URL REDIS_URL TEST_REDIS_URL
runtime_env=(-e DATABASE_URL -e TEST_DATABASE_URL -e REDIS_URL -e TEST_REDIS_URL \
  -e ALLOW_LIVE_TRADING=false -e ENVIRONMENT=release_validation)
docker run --rm --network "$network_id" "${runtime_env[@]}" "$app_image" alembic upgrade head
docker run --rm --network "$network_id" "${runtime_env[@]}" "$app_image" alembic current
docker run --rm --network "$network_id" "${runtime_env[@]}" \
  -v "$scratch/source/tools:/app/tools:ro" -v "$scratch/results:/validation" \
  "$image" python -m pytest -o addopts='' -q -rs --junitxml=/validation/results.xml
docker run --rm --network "$network_id" -v "$scratch/results:/validation:ro" "$image" \
  python -c 'import xml.etree.ElementTree as E; r=E.parse("/validation/results.xml"); suites=list(r.iter("testsuite")); assert suites; assert sum(int(s.get("skipped",0)) for s in suites)==0, "Skipped tests do not satisfy release acceptance"; print("Full suite completed without skipped tests")'

# Disable automation in the disposable DB before starting the web process.
docker run --rm --network "$network_id" "${runtime_env[@]}" "$app_image" python -c \
  'from app.db.session import SessionLocal; from app.services.automation import get_or_create_state; db=SessionLocal(); s=get_or_create_state(db); s.enabled=False; s.killed=True; s.auto_execute_paper=False; db.commit(); db.close()'
app_id=$(docker create --network "$network_id" "${runtime_env[@]}" "$app_image")
owned_containers+=("$app_id")
docker start "$app_id" >/dev/null
healthy=false
for attempt in {1..20}; do
  if docker exec "$app_id" python -c \
    'import httpx; c=httpx.Client(base_url="http://127.0.0.1:8000",timeout=2); h=c.get("/health"); h.raise_for_status(); assert h.json()["status"]=="ok"; s=c.get("/api/system"); s.raise_for_status(); assert s.json()["live_money_policy"]=="EXPLICITLY_GATED"' >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 1
done
if ! $healthy; then echo 'Isolated app health/system smoke failed.' >&2; exit 1; fi
echo "PASS: $candidate — clean migrations, full container suite with zero skips, app health/system smoke."
echo 'Production deployment, broker acceptance, production restore and live certification remain separate checks.'
