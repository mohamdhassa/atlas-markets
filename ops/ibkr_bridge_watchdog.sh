#!/usr/bin/env bash
set -euo pipefail

BRIDGE_CONTAINER="${IBKR_BRIDGE_CONTAINER:-atlas-markets-ibkr-bridge}"
BRIDGE_HEALTH_URL="${IBKR_BRIDGE_HEALTH_URL:-http://127.0.0.1:8766/health}"
GATEWAY_HOST="${IBKR_GATEWAY_HOST:-127.0.0.1}"
GATEWAY_PORT="${IBKR_GATEWAY_PORT:-4002}"

# Never attempt recovery until IB Gateway is actually accepting API connections.
# This intentionally does not and cannot bypass IBKR login or 2FA.
if ! timeout 2 bash -c "</dev/tcp/${GATEWAY_HOST}/${GATEWAY_PORT}" 2>/dev/null; then
  echo "IBKR_AUTH_REQUIRED gateway_api_unavailable"
  exit 0
fi

health="$(curl --silent --show-error --max-time 4 "${BRIDGE_HEALTH_URL}" 2>/dev/null || true)"
if printf '%s' "${health}" | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("connected") is True else 1)' 2>/dev/null; then
  echo "IBKR_HEALTHY"
  exit 0
fi

# Gateway is authenticated/listening but the bridge is stale or unavailable.
# Restart only the dedicated bridge container; never Gateway, ATLAS, or databases.
if ! docker inspect "${BRIDGE_CONTAINER}" >/dev/null 2>&1; then
  echo "IBKR_BRIDGE_MISSING"
  exit 1
fi

echo "IBKR_BRIDGE_RECOVERY restarting=${BRIDGE_CONTAINER}"
docker restart "${BRIDGE_CONTAINER}" >/dev/null
sleep 5

health="$(curl --silent --show-error --max-time 4 "${BRIDGE_HEALTH_URL}" 2>/dev/null || true)"
if printf '%s' "${health}" | python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("connected") is True else 1)' 2>/dev/null; then
  echo "IBKR_RECOVERED"
  exit 0
fi

echo "IBKR_RECOVERY_PENDING"
exit 1
