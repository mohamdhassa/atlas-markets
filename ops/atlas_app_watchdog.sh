#!/usr/bin/env bash
set -u

PROJECT="${ATLAS_PROJECT:-/home/ubuntu/atlas-markets}"
COMPOSE_FILE="${ATLAS_COMPOSE_FILE:-${PROJECT}/docker-compose.oracle.prod.yml}"
ENV_FILE="${ATLAS_ENV_FILE:-${PROJECT}/.env.oracle}"
HEALTH_URL="${ATLAS_HEALTH_URL:-http://127.0.0.1:8100/health}"
LOG_FILE="${ATLAS_WATCHDOG_LOG:-/var/log/atlas-app-watchdog.log}"

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "${LOG_FILE}"
}

for attempt in 1 2 3; do
  if curl --max-time 5 --fail --silent "${HEALTH_URL}" >/dev/null; then
    log "HEALTHY"
    exit 0
  fi
  log "HEALTH_CHECK_FAILED attempt=${attempt}"
  sleep 2
done

log "RECOVERY restarting_app"
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" restart app >>"${LOG_FILE}" 2>&1
sleep 15

if curl --max-time 10 --fail --silent "${HEALTH_URL}" >/dev/null; then
  log "RECOVERED"
  exit 0
fi

log "RECOVERY_FAILED"
exit 1
