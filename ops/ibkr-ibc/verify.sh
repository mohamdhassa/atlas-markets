#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${IBKR_IBC_COMPOSE_FILE:-/home/ubuntu/atlas-markets/ops/ibkr-ibc/compose.yml}"
ENV_FILE="${IBKR_IBC_ENV_FILE:-/home/ubuntu/.config/atlas/ibkr-ibc.env}"
HEALTH_URL="${IBKR_BRIDGE_HEALTH_URL:-http://127.0.0.1:8766/health}"
ACCOUNT_URL="${IBKR_BRIDGE_ACCOUNT_URL:-http://127.0.0.1:8766/account}"

if [[ ! -r "${COMPOSE_FILE}" || ! -r "${ENV_FILE}" ]]; then
  echo "STOP: IBC compose or protected environment file is missing"
  exit 1
fi

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config --quiet

container="$(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps -q ib-gateway)"
if [[ -z "${container}" ]]; then
  echo "STOP: IBC Gateway container was not found"
  exit 1
fi

state="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "${container}")"
echo "IBC_GATEWAY ${state}"

paper_port="$(sed -n 's/^IBKR_PAPER_HOST_PORT=//p' "${ENV_FILE}" | tail -1)"
paper_port="${paper_port:-14002}"
if timeout 3 bash -c "</dev/tcp/127.0.0.1/${paper_port}" 2>/dev/null; then
  echo "IBC_PAPER_API_READY port=${paper_port}"
else
  echo "IBC_PAPER_API_WAITING port=${paper_port}"
  exit 1
fi

if [[ "${paper_port}" == "4002" ]]; then
  curl --max-time 20 --fail --silent --show-error "${HEALTH_URL}"
  echo
  curl --max-time 20 --fail --silent --show-error "${ACCOUNT_URL}"
  echo
fi
