#!/usr/bin/env zsh

set -euo pipefail

ENV_FILE="${1:-.env}"
SEED_MODE="${2:-}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

POSTGRES_USER_VALUE="${POSTGRES_USER:-your_user}"
POSTGRES_DB_VALUE="${POSTGRES_DB:-scrapy_db}"

echo "[bootstrap] root: ${ROOT_DIR}"
echo "[bootstrap] env file: ${ENV_FILE}"

zsh scripts/preflight.sh "${ENV_FILE}"

echo "[bootstrap] starting services"
docker compose --env-file "${ENV_FILE}" up -d \
  postgres redis api frontend web scheduler crawl-worker translation-worker embedding-worker

echo "[bootstrap] waiting for postgres"
until docker compose --env-file "${ENV_FILE}" exec -T postgres pg_isready -U "${POSTGRES_USER_VALUE}" -d "${POSTGRES_DB_VALUE}" >/dev/null 2>&1; do
  sleep 2
done

echo "[bootstrap] applying migrations"
docker compose --env-file "${ENV_FILE}" exec -T postgres psql -U "${POSTGRES_USER_VALUE}" -d "${POSTGRES_DB_VALUE}" < migrations/000001_unified_news_schema.sql
docker compose --env-file "${ENV_FILE}" exec -T postgres psql -U "${POSTGRES_USER_VALUE}" -d "${POSTGRES_DB_VALUE}" < migrations/000003_pipeline_task_runs.sql
docker compose --env-file "${ENV_FILE}" exec -T postgres psql -U "${POSTGRES_USER_VALUE}" -d "${POSTGRES_DB_VALUE}" < migrations/000004_pipeline_task_audit_columns.sql

if [[ "${SEED_MODE}" == "--with-demo-seed" ]]; then
  echo "[bootstrap] loading demo semantic seed"
  docker compose --env-file "${ENV_FILE}" exec -T postgres psql -U "${POSTGRES_USER_VALUE}" -d "${POSTGRES_DB_VALUE}" < migrations/000002_demo_semantic_seed.sql
fi

echo "[bootstrap] running smoke checks"
zsh scripts/smoke.sh

echo "[bootstrap] done"
