#!/usr/bin/env zsh

set -euo pipefail

ENV_FILE="${1:-.env}"
API_BASE_URL="${2:-http://127.0.0.1:8000}"
WEB_BASE_URL="${3:-http://127.0.0.1:18080}"

echo "[pre-release] env file: ${ENV_FILE}"
echo "[pre-release] api base url: ${API_BASE_URL}"
echo "[pre-release] web base url: ${WEB_BASE_URL}"

echo "[pre-release] step 1/4: strict preflight"
PRODUCTION_PIPELINE_REQUIRED=1 zsh scripts/preflight.sh "${ENV_FILE}"

echo "[pre-release] step 2/4: web smoke"
zsh scripts/smoke.sh "${WEB_BASE_URL}"

echo "[pre-release] step 3/4: production rollout checks"
zsh scripts/check_production_rollout.sh "${ENV_FILE}" "${API_BASE_URL}"

echo "[pre-release] step 4/4: search quality checks"
zsh scripts/check_search_quality.sh "${ENV_FILE}" "${API_BASE_URL}"

echo "[pre-release] all checks passed"
