#!/usr/bin/env bash
set -euo pipefail

BRIDGE_CONTAINER="${IBKR_BRIDGE_CONTAINER:-atlas-markets-ibkr-bridge}"
BRIDGE_HEALTH_URL="${IBKR_BRIDGE_HEALTH_URL:-http://127.0.0.1:8766/health}"
GATEWAY_CONTAINER="${IBKR_GATEWAY_CONTAINER:-atlas-ibkr-ibc-gateway}"
GATEWAY_HOST="${IBKR_GATEWAY_HOST:-127.0.0.1}"
GATEWAY_PORT="${IBKR_GATEWAY_PORT:-4002}"
GATEWAY_RECOVERY_WAIT_SECONDS="${IBKR_GATEWAY_RECOVERY_WAIT_SECONDS:-120}"
GATEWAY_RECOVERY_COOLDOWN_SECONDS="${IBKR_GATEWAY_RECOVERY_COOLDOWN_SECONDS:-600}"
GATEWAY_RECOVERY_STAMP="${IBKR_GATEWAY_RECOVERY_STAMP:-/run/atlas/ibkr-gateway-recovery.timestamp}"
WATCHDOG_LOG="${IBKR_WATCHDOG_LOG:-/var/log/atlas/ibkr-watchdog.log}"

log_event() {
  local message="$*"
  local line
  line="$(date -u '+%Y-%m-%dT%H:%M:%SZ') ${message}"
  echo "${line}"
  if [[ -d "$(dirname "${WATCHDOG_LOG}")" && -w "$(dirname "${WATCHDOG_LOG}")" ]]; then
    printf '%s\n' "${line}" >> "${WATCHDOG_LOG}"
  fi
}

gateway_status() {
  docker inspect --format '{{.State.Status}}' "${GATEWAY_CONTAINER}" 2>/dev/null || true
}

gateway_health() {
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${GATEWAY_CONTAINER}" 2>/dev/null || true
}

gateway_ready() {
  [[ "$(gateway_status)" == "running" && "$(gateway_health)" == "healthy" ]]
}

if ! docker inspect "${GATEWAY_CONTAINER}" >/dev/null 2>&1; then
  log_event "IBKR_GATEWAY_MISSING container=${GATEWAY_CONTAINER}"
  exit 1
fi

# The host port is a socat proxy and can stay open while the real Gateway API
# inside the container refuses connections. Container health is authoritative.
if ! gateway_ready; then
  status="$(gateway_status)"
  health="$(gateway_health)"
  if [[ "${status}" == "running" && "${health}" == "starting" ]]; then
    log_event "IBKR_GATEWAY_STARTING"
    exit 0
  fi

  now="$(date +%s)"
  last=0
  if [[ -r "${GATEWAY_RECOVERY_STAMP}" ]]; then
    read -r last < "${GATEWAY_RECOVERY_STAMP}" || last=0
  fi
  if [[ "${last}" =~ ^[0-9]+$ ]] && (( now - last < GATEWAY_RECOVERY_COOLDOWN_SECONDS )); then
    log_event "IBKR_GATEWAY_RECOVERY_COOLDOWN status=${status} health=${health}"
    exit 0
  fi

  install -d -m 755 "$(dirname "${GATEWAY_RECOVERY_STAMP}")"
  printf '%s\n' "${now}" > "${GATEWAY_RECOVERY_STAMP}"
  log_event "IBKR_GATEWAY_RECOVERY restarting=${GATEWAY_CONTAINER} status=${status} health=${health}"
  docker restart "${GATEWAY_CONTAINER}" >/dev/null

  waited=0
  while (( waited < GATEWAY_RECOVERY_WAIT_SECONDS )); do
    if gateway_ready; then
      rm -f "${GATEWAY_RECOVERY_STAMP}"
      log_event "IBKR_GATEWAY_RECOVERED waited_seconds=${waited}"
      break
    fi
    sleep 5
    waited=$((waited + 5))
  done

  if ! gateway_ready; then
    log_event "IBKR_AUTH_REQUIRED gateway_status=$(gateway_status) gateway_health=$(gateway_health)"
    exit 1
  fi
fi

if ! timeout 2 bash -c "</dev/tcp/${GATEWAY_HOST}/${GATEWAY_PORT}" 2>/dev/null; then
  log_event "IBKR_GATEWAY_ENDPOINT_UNAVAILABLE host=${GATEWAY_HOST} port=${GATEWAY_PORT}"
  exit 1
fi

health="$(curl --silent --show-error --max-time 4 "${BRIDGE_HEALTH_URL}" 2>/dev/null || true)"
if printf '%s' "${health}" | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("connected") is True else 1)' 2>/dev/null; then
  log_event "IBKR_HEALTHY"
  exit 0
fi

# A healthy local socket with a lost IBKR backend is a server outage, not a
# dead bridge. Preserve Gateway's automatic reconnection and authentication.
if printf '%s' "${health}" | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("socket_connected") is True and d.get("server_connected") is False else 1)' 2>/dev/null; then
  log_event "IBKR_SERVER_UNAVAILABLE waiting_for_gateway_reconnection"
  exit 0
fi

# Gateway is authenticated and healthy but the bridge is stale or unavailable.
if ! docker inspect "${BRIDGE_CONTAINER}" >/dev/null 2>&1; then
  log_event "IBKR_BRIDGE_MISSING"
  exit 1
fi

log_event "IBKR_BRIDGE_RECOVERY restarting=${BRIDGE_CONTAINER}"
docker restart "${BRIDGE_CONTAINER}" >/dev/null
sleep 5

health="$(curl --silent --show-error --max-time 4 "${BRIDGE_HEALTH_URL}" 2>/dev/null || true)"
if printf '%s' "${health}" | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("connected") is True else 1)' 2>/dev/null; then
  log_event "IBKR_RECOVERED"
  exit 0
fi

log_event "IBKR_RECOVERY_PENDING"
exit 1
