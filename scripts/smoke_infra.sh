#!/usr/bin/env bash
# Phase 1 infrastructure smoke checks.
set -euo pipefail

GATEWAY_BASE="${GATEWAY_BASE:-http://localhost:8000}"
LITELLM_BASE="${LITELLM_BASE:-http://localhost:4000}"
LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-}"

echo "==> Gateway liveness: ${GATEWAY_BASE}/api/v1/health/live"
curl -sf "${GATEWAY_BASE}/api/v1/health/live" | tee /tmp/ros_health_live.json
echo

echo "==> Gateway readiness: ${GATEWAY_BASE}/api/v1/health/ready"
# ready may be degraded (200) or not_ready (503) depending on env; accept both bodies
code=$(curl -s -o /tmp/ros_health_ready.json -w "%{http_code}" "${GATEWAY_BASE}/api/v1/health/ready" || true)
cat /tmp/ros_health_ready.json
echo
echo "ready HTTP ${code}"
if [[ "${code}" != "200" && "${code}" != "503" ]]; then
  echo "unexpected ready status: ${code}" >&2
  exit 1
fi

if curl -sf "${LITELLM_BASE}/health/liveliness" >/tmp/ros_litellm_live.json 2>/dev/null; then
  echo "==> LiteLLM up — chat smoke"
  auth_header=()
  if [[ -n "${LITELLM_MASTER_KEY}" ]]; then
    auth_header=(-H "Authorization: Bearer ${LITELLM_MASTER_KEY}")
  fi
  curl -sf "${LITELLM_BASE}/v1/chat/completions" \
    "${auth_header[@]}" \
    -H "Content-Type: application/json" \
    -d '{"model":"default","messages":[{"role":"user","content":"ping"}],"max_tokens":8}' \
    | tee /tmp/ros_litellm_chat.json
  echo
  echo "==> LiteLLM embedding smoke"
  curl -sf "${LITELLM_BASE}/v1/embeddings" \
    "${auth_header[@]}" \
    -H "Content-Type: application/json" \
    -d '{"model":"embed","input":"researchos smoke"}' \
    | tee /tmp/ros_litellm_embed.json
  echo
else
  echo "==> LiteLLM not reachable at ${LITELLM_BASE} — skipping chat/embed smoke"
fi

echo "OK: smoke_infra finished"
