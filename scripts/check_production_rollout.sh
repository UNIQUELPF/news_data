#!/usr/bin/env zsh

set -euo pipefail

ENV_FILE="${1:-.env}"
BASE_URL="${2:-http://127.0.0.1:8000}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[rollout-check] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

ADMIN_TOKEN="${ADMIN_API_TOKEN:-}"
MAX_TRANSLATION_FAILED="${MAX_TRANSLATION_FAILED:-0}"
MAX_EMBEDDING_FAILED="${MAX_EMBEDDING_FAILED:-0}"

if [[ -z "${ADMIN_TOKEN}" ]]; then
  echo "[rollout-check] ADMIN_API_TOKEN is empty" >&2
  exit 1
fi

RUNTIME_JSON="$(curl -fsS \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  "${BASE_URL}/api/v1/pipeline/runtime")"

SUMMARY_JSON="$(curl -fsS \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  "${BASE_URL}/api/v1/pipeline/summary")"

MONITOR_JSON="$(curl -fsS \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  "${BASE_URL}/api/v1/pipeline/monitor")"

export RUNTIME_JSON SUMMARY_JSON MONITOR_JSON MAX_TRANSLATION_FAILED MAX_EMBEDDING_FAILED

python3 - <<'PY'
import json
import os
import sys

runtime = json.loads(os.environ["RUNTIME_JSON"])
summary = json.loads(os.environ["SUMMARY_JSON"])
monitor = json.loads(os.environ["MONITOR_JSON"])
max_translation_failed = int(os.environ["MAX_TRANSLATION_FAILED"])
max_embedding_failed = int(os.environ["MAX_EMBEDDING_FAILED"])

errors = []

if not runtime.get("production_ready"):
    errors.append("runtime.production_ready is false")

translation_mode = runtime.get("translation", {}).get("mode")
embedding_provider = runtime.get("embedding", {}).get("provider")

translation_failed = int(summary.get("translation_failed") or 0)
embedding_failed = int(summary.get("embedding_failed") or 0)
translation_processing = int(summary.get("translation_processing") or 0)
embedding_processing = int(summary.get("embedding_processing") or 0)

task_monitor = monitor.get("tasks") or {}
crawl_monitor = monitor.get("crawl") or {}
pending_tasks = int(task_monitor.get("pending_tasks") or 0)
retry_tasks = int(task_monitor.get("retry_tasks") or 0)
started_tasks = int(task_monitor.get("started_tasks") or 0)
crawl_running_now = int(crawl_monitor.get("crawl_running_now") or 0)

if translation_failed > max_translation_failed:
    errors.append(
        f"translation_failed={translation_failed} exceeds threshold {max_translation_failed}"
    )

if embedding_failed > max_embedding_failed:
    errors.append(
        f"embedding_failed={embedding_failed} exceeds threshold {max_embedding_failed}"
    )

print("[rollout-check] runtime")
print(
    f"  production_ready={runtime.get('production_ready')} "
    f"translation_mode={translation_mode} embedding_provider={embedding_provider}"
)
if runtime.get("warnings"):
    for warning in runtime["warnings"]:
        print(f"  warning={warning}")

print("[rollout-check] summary")
print(
    "  "
    f"translation_pending={summary.get('translation_pending', 0)} "
    f"translation_processing={translation_processing} "
    f"translation_completed={summary.get('translation_completed', 0)} "
    f"translation_failed={translation_failed}"
)
print(
    "  "
    f"embedding_pending={summary.get('embedding_pending', 0)} "
    f"embedding_processing={embedding_processing} "
    f"embedding_completed={summary.get('embedding_completed', 0)} "
    f"embedding_failed={embedding_failed}"
)

print("[rollout-check] tasks")
print(
    "  "
    f"pending={pending_tasks} retry={retry_tasks} started={started_tasks} "
    f"backfill_active={task_monitor.get('backfill_active', 0)} "
    f"pipeline_run_active={task_monitor.get('pipeline_run_active', 0)}"
)

print("[rollout-check] crawl")
print(
    "  "
    f"crawl_jobs_24h={crawl_monitor.get('crawl_jobs_24h', 0)} "
    f"crawl_failed_24h={crawl_monitor.get('crawl_failed_24h', 0)} "
    f"crawl_running_now={crawl_running_now}"
)

if errors:
    print("[rollout-check] failed")
    for error in errors:
        print(f"  {error}")
    sys.exit(1)

print("[rollout-check] passed")
PY
