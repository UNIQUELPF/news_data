#!/usr/bin/env zsh

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:18080}"

echo "[smoke] base url: ${BASE_URL}"

check() {
  local name="$1"
  local url="$2"

  echo "[smoke] checking ${name}: ${url}"
  curl -fsS "${url}" >/dev/null
}

check "web index" "${BASE_URL}/"
check "api health" "${BASE_URL}/health"
check "article list" "${BASE_URL}/api/v1/articles?page=1&page_size=1"

echo "[smoke] all checks passed"
