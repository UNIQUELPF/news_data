#!/usr/bin/env zsh

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
ADMIN_TOKEN="${ADMIN_API_TOKEN:-}"
ADMIN_ACTOR="${ADMIN_ACTOR:-codex}"
SPIDERS_CSV="${SPIDERS:-}"
TARGET_LANGUAGE="${TARGET_LANGUAGE:-zh-CN}"
TRANSLATE_LIMIT="${TRANSLATE_LIMIT:-50}"
EMBED_LIMIT="${EMBED_LIMIT:-50}"
FORCE_TRANSLATE="${FORCE_TRANSLATE:-false}"
FORCE_EMBED="${FORCE_EMBED:-false}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
POLL_TIMEOUT="${POLL_TIMEOUT:-300}"

if [[ -z "${ADMIN_TOKEN}" ]]; then
  echo "[run-pipeline] ADMIN_API_TOKEN is required" >&2
  exit 1
fi

echo "[run-pipeline] base url: ${BASE_URL}"
echo "[run-pipeline] actor: ${ADMIN_ACTOR}"

if [[ -n "${SPIDERS_CSV}" ]]; then
  echo "[run-pipeline] spiders: ${SPIDERS_CSV}"
else
  echo "[run-pipeline] spiders: <none>"
fi

export SPIDERS_CSV TARGET_LANGUAGE TRANSLATE_LIMIT EMBED_LIMIT FORCE_TRANSLATE FORCE_EMBED

PAYLOAD="$(python3 - <<'PY'
import json
import os

spiders = [item.strip() for item in os.environ.get("SPIDERS_CSV", "").split(",") if item.strip()]
payload = {
    "spiders": spiders,
    "target_language": os.environ.get("TARGET_LANGUAGE", "zh-CN"),
    "crawl_extra_args": {},
    "translate_limit": int(os.environ.get("TRANSLATE_LIMIT", "50")),
    "embed_limit": int(os.environ.get("EMBED_LIMIT", "50")),
    "force_translate": os.environ.get("FORCE_TRANSLATE", "false").lower() == "true",
    "force_embed": os.environ.get("FORCE_EMBED", "false").lower() == "true",
}
print(json.dumps(payload))
PY
)"

RESPONSE="$(curl -fsS \
  -X POST "${BASE_URL}/api/v1/pipeline/run" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -H "X-Admin-Actor: ${ADMIN_ACTOR}" \
  -d "${PAYLOAD}")"

TASK_ID="$(printf '%s' "${RESPONSE}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["task_id"])')"

echo "[run-pipeline] queued task: ${TASK_ID}"

SECONDS_WAITED=0
while (( SECONDS_WAITED < POLL_TIMEOUT )); do
  STATUS_JSON="$(curl -fsS \
    -H "X-Admin-Token: ${ADMIN_TOKEN}" \
    "${BASE_URL}/api/v1/pipeline/tasks/${TASK_ID}")"
  STATE="$(printf '%s' "${STATUS_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')"
  echo "[run-pipeline] state=${STATE} waited=${SECONDS_WAITED}s"

  case "${STATE}" in
    SUCCESS|FAILURE|REVOKED)
      printf '%s\n' "${STATUS_JSON}"
      exit 0
      ;;
  esac

  sleep "${POLL_INTERVAL}"
  (( SECONDS_WAITED += POLL_INTERVAL ))
done

echo "[run-pipeline] timed out after ${POLL_TIMEOUT}s" >&2
exit 1
