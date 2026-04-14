#!/usr/bin/env zsh

set -euo pipefail

ENV_FILE="${1:-.env}"
BASE_URL="${2:-http://127.0.0.1:8000}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[search-check] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

ADMIN_TOKEN="${ADMIN_API_TOKEN:-}"
PAGE_SIZE="${SEARCH_CHECK_PAGE_SIZE:-3}"

if [[ -z "${ADMIN_TOKEN}" ]]; then
  echo "[search-check] ADMIN_API_TOKEN is empty" >&2
  exit 1
fi

QUERIES=(
  "OpenAI 欧盟合规"
  "东盟 能源 转型 融资"
  "美联储 利率 通胀"
  "德国 人工智能 法案"
  "金砖 支付 体系"
)

for query in "${QUERIES[@]}"; do
  echo "[search-check] query=${query}"
  for mode in keyword semantic hybrid; do
    export SEARCH_CHECK_QUERY="${query}"
    export SEARCH_CHECK_MODE="${mode}"
    export SEARCH_CHECK_PAGE_SIZE="${PAGE_SIZE}"
    export SEARCH_CHECK_BASE_URL="${BASE_URL}"
    export SEARCH_CHECK_ADMIN_TOKEN="${ADMIN_TOKEN}"

    python3 - <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

query = os.environ["SEARCH_CHECK_QUERY"]
mode = os.environ["SEARCH_CHECK_MODE"]
page_size = os.environ["SEARCH_CHECK_PAGE_SIZE"]
base_url = os.environ["SEARCH_CHECK_BASE_URL"].rstrip("/")
admin_token = os.environ["SEARCH_CHECK_ADMIN_TOKEN"]

params = urllib.parse.urlencode(
    {
        "q": query,
        "search_mode": mode,
        "page": 1,
        "page_size": page_size,
    }
)
request = urllib.request.Request(
    f"{base_url}/api/v1/articles?{params}",
    headers={"X-Admin-Token": admin_token},
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
except Exception as exc:
    print(f"  mode={mode} status=error detail={exc}")
    sys.exit(1)

items = payload.get("items") or []
titles = [item.get("title") or item.get("title_original") or "—" for item in items[:3]]
print(f"  mode={mode} count={len(items)}")
for index, title in enumerate(titles, start=1):
    print(f"    {index}. {title}")

if not items:
    sys.exit(1)
PY
  done
done

echo "[search-check] passed"
