#!/usr/bin/env zsh

set -euo pipefail

ENV_FILE="${1:-.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[preflight] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

echo "[preflight] using env file: ${ENV_FILE}"

source "${ENV_FILE}"

fail() {
  echo "[preflight] ${1}" >&2
  exit 1
}

warn() {
  echo "[preflight] warning: ${1}"
}

require_value() {
  local name="$1"
  local value="${(P)name:-}"

  if [[ -z "${value}" ]]; then
    fail "required variable ${name} is empty"
  fi
}

reject_placeholder() {
  local name="$1"
  local value="${(P)name:-}"

  case "${value}" in
    your_user|your_password|change-this-admin-token)
      fail "variable ${name} still uses placeholder value '${value}'"
      ;;
  esac
}

require_value POSTGRES_DB
require_value POSTGRES_USER
require_value POSTGRES_PASSWORD
require_value POSTGRES_HOST
require_value POSTGRES_PORT
require_value ADMIN_API_TOKEN

reject_placeholder ADMIN_API_TOKEN

warn_if_placeholder() {
  local name="$1"
  local value="${(P)name:-}"

  case "${value}" in
    your_user|your_password)
      warn "variable ${name} still uses development credential '${value}'"
      ;;
  esac
}

warn_if_placeholder POSTGRES_USER
warn_if_placeholder POSTGRES_PASSWORD

EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-openai}"
PRODUCTION_PIPELINE_REQUIRED="${PRODUCTION_PIPELINE_REQUIRED:-0}"
case "${EMBEDDING_PROVIDER}" in
  demo)
    require_value DEMO_EMBEDDING_MODEL
    ;;
  local)
    require_value LOCAL_EMBEDDING_MODEL
    require_value LOCAL_EMBEDDING_DEVICE
    require_value LOCAL_EMBEDDING_BATCH_SIZE
    ;;
  openai)
    require_value EMBEDDING_MODEL
    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
      warn "OPENAI_API_KEY is empty; embedding tasks will not call the remote provider"
    fi
    ;;
  *)
    fail "unsupported EMBEDDING_PROVIDER: ${EMBEDDING_PROVIDER}"
    ;;
esac

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  require_value OPENAI_BASE_URL
  require_value TRANSLATION_MODEL
fi

if [[ "${PRODUCTION_PIPELINE_REQUIRED}" == "1" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    fail "PRODUCTION_PIPELINE_REQUIRED=1 but OPENAI_API_KEY is empty; translation would run in placeholder mode"
  fi

  case "${EMBEDDING_PROVIDER}" in
    demo)
      fail "PRODUCTION_PIPELINE_REQUIRED=1 but EMBEDDING_PROVIDER=demo"
      ;;
    openai)
      require_value OPENAI_API_KEY
      require_value EMBEDDING_MODEL
      ;;
    local)
      require_value LOCAL_EMBEDDING_MODEL
      require_value LOCAL_EMBEDDING_DEVICE
      require_value LOCAL_EMBEDDING_BATCH_SIZE
      ;;
  esac
fi

echo "[preflight] validating docker compose configuration"
docker compose --env-file "${ENV_FILE}" config >/dev/null

echo "[preflight] all checks passed"
