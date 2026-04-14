#!/usr/bin/env zsh

set -euo pipefail

ENV_FILE="${1:-.env}"
BASE_URL="${2:-http://127.0.0.1:8000}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[production-backfill] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

export PRODUCTION_PIPELINE_REQUIRED=1
zsh scripts/preflight.sh "${ENV_FILE}"

ADMIN_TOKEN="${ADMIN_API_TOKEN:-}"
ADMIN_ACTOR="${ADMIN_ACTOR:-production-backfill}"
TARGET_LANGUAGE="${TARGET_LANGUAGE:-zh-CN}"
ROLLOUT_STAGE="${ROLLOUT_STAGE:-small}"
TRANSLATE_LIMIT="${TRANSLATE_LIMIT:-}"
EMBED_LIMIT="${EMBED_LIMIT:-}"
FORCE_TRANSLATE="${FORCE_TRANSLATE:-false}"
FORCE_EMBED="${FORCE_EMBED:-false}"

read -r TRANSLATE_LIMIT_VALUE EMBED_LIMIT_VALUE < <(python3 - <<'PY'
import os

profiles = {
    "small": (25, 25),
    "medium": (100, 100),
    "large": (300, 300),
}
stage = os.environ.get("ROLLOUT_STAGE", "small").strip().lower()
translate_limit, embed_limit = profiles.get(stage, profiles["small"])
print(os.environ.get("TRANSLATE_LIMIT") or translate_limit, os.environ.get("EMBED_LIMIT") or embed_limit)
PY
)

export TRANSLATE_LIMIT_VALUE EMBED_LIMIT_VALUE

PAYLOAD="$(python3 - <<'PY'
import json
import os

payload = {
    "target_language": os.environ.get("TARGET_LANGUAGE", "zh-CN"),
    "translate_limit": int(os.environ["TRANSLATE_LIMIT_VALUE"]),
    "embed_limit": int(os.environ["EMBED_LIMIT_VALUE"]),
    "force_translate": os.environ.get("FORCE_TRANSLATE", "false").lower() == "true",
    "force_embed": os.environ.get("FORCE_EMBED", "false").lower() == "true",
}
print(json.dumps(payload))
PY
)"

echo "[production-backfill] rollout stage: ${ROLLOUT_STAGE}"
echo "[production-backfill] translate_limit=${TRANSLATE_LIMIT_VALUE} embed_limit=${EMBED_LIMIT_VALUE}"
echo "[production-backfill] triggering backfill against ${BASE_URL}"
curl -fsS \
  -X POST "${BASE_URL}/api/v1/pipeline/backfill" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -H "X-Admin-Actor: ${ADMIN_ACTOR}" \
  -d "${PAYLOAD}"
echo
