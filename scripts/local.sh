#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=${STYLECAPTURE_REPOSITORY_ROOT:-$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)}

if [[ -n "${STYLECAPTURE_ENV_FILE:-}" ]]; then
  ENV_FILE=$STYLECAPTURE_ENV_FILE
elif [[ -f "$REPOSITORY_ROOT/.env.local" ]]; then
  ENV_FILE=$REPOSITORY_ROOT/.env.local
elif [[ -f "$REPOSITORY_ROOT/.env" ]]; then
  ENV_FILE=$REPOSITORY_ROOT/.env
else
  ENV_FILE=$REPOSITORY_ROOT/.env.local
fi

compose() {
  docker compose \
    --project-name "${STYLECAPTURE_COMPOSE_PROJECT_NAME:-stylecapture-local}" \
    --project-directory "$REPOSITORY_ROOT" \
    --env-file "$ENV_FILE" \
    -f "$REPOSITORY_ROOT/docker-compose.yml" \
    --profile "${STYLECAPTURE_COMPOSE_PROFILE:-core}" \
    "$@"
}

random_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return
  fi
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

init_env() {
  if [[ -f "$ENV_FILE" ]]; then
    printf 'Using existing local configuration: %s\n' "$ENV_FILE"
    return
  fi

  if [[ ! -f "$REPOSITORY_ROOT/.env.example" ]]; then
    printf 'Missing %s/.env.example\n' "$REPOSITORY_ROOT" >&2
    exit 1
  fi

  local gateway_secret upload_secret session_secret temporary_file line
  gateway_secret="local-$(random_hex)"
  upload_secret=$(random_hex)
  session_secret=$(random_hex)
  temporary_file="${ENV_FILE}.tmp.$$"
  umask 077
  mkdir -p "$(dirname -- "$ENV_FILE")"

  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      STYLECAPTURE_UPLOAD_SIGNING_SECRET=*)
        printf 'STYLECAPTURE_UPLOAD_SIGNING_SECRET=%s\n' "$upload_secret"
        ;;
      STYLECAPTURE_SESSION_SIGNING_SECRET=*)
        printf 'STYLECAPTURE_SESSION_SIGNING_SECRET=%s\n' "$session_secret"
        ;;
      STYLECAPTURE_LITELLM_API_KEY=*)
        printf 'STYLECAPTURE_LITELLM_API_KEY=%s\n' "$gateway_secret"
        ;;
      LITELLM_MASTER_KEY=*)
        printf 'LITELLM_MASTER_KEY=%s\n' "$gateway_secret"
        ;;
      *)
        printf '%s\n' "$line"
        ;;
    esac
  done < "$REPOSITORY_ROOT/.env.example" > "$temporary_file"

  mv "$temporary_file" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  printf 'Created local configuration: %s\n' "$ENV_FILE"
  printf 'Add a hosted provider key before using AI features. See README.md.\n'
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    printf 'Docker is required. Install Docker Desktop or Docker Engine with Compose v2.\n' >&2
    exit 1
  fi
  docker compose version >/dev/null
  docker info >/dev/null
}

env_value() {
  local key=$1
  local value
  value=$(awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "$ENV_FILE")
  printf '%s' "$value"
}

provider_status() {
  local provider_key text_model image_model
  provider_key=${STYLECAPTURE_AI_API_KEY:-$(env_value STYLECAPTURE_AI_API_KEY)}
  if [[ -z "$provider_key" ]]; then
    provider_key=${ARK_API_KEY:-$(env_value ARK_API_KEY)}
  fi
  text_model=${STYLECAPTURE_TEXT_MODEL:-$(env_value STYLECAPTURE_TEXT_MODEL)}
  image_model=${STYLECAPTURE_IMAGE_MODEL:-$(env_value STYLECAPTURE_IMAGE_MODEL)}

  if [[ -n "$provider_key" ]]; then
    printf 'AI provider: configured (credential hidden)\n'
  else
    printf 'AI provider: not configured; the UI and seeded wardrobe work, live AI calls will fail truthfully.\n'
  fi
  printf 'Text/vision model: %s\n' "${text_model:-Compose default}"
  printf 'Image model: %s\n' "${image_model:-Compose default}"
}

wait_for_url() {
  local name=$1 url=$2 attempts=${3:-90}
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl --fail --silent --show-error --max-time 3 "$url" >/dev/null 2>&1; then
      printf '%s is ready: %s\n' "$name" "$url"
      return
    fi
    sleep 2
  done
  printf '%s did not become ready: %s\n' "$name" "$url" >&2
  compose ps >&2 || true
  exit 1
}

compose_build() {
  local attempt
  for attempt in 1 2 3; do
    if compose build; then
      return
    fi
    if [[ "$attempt" -eq 3 ]]; then
      printf 'Docker build failed after %s attempts.\n' "$attempt" >&2
      exit 1
    fi
    printf 'Docker build attempt %s failed; retrying with the existing build cache...\n' "$attempt" >&2
    sleep 2
  done
}

doctor() {
  init_env
  require_docker
  compose config --quiet
  printf 'Docker Compose configuration: valid\n'
  printf 'Environment file: %s\n' "$ENV_FILE"
  provider_status
}

up() {
  doctor
  compose_build
  compose up -d
  wait_for_url 'Product API' 'http://127.0.0.1:8000/readyz'
  wait_for_url 'StyleCapture H5' 'http://127.0.0.1:5173/healthz'
  printf '\nStyleCapture is ready:\n'
  printf '  H5:       http://127.0.0.1:5173\n'
  printf '  API docs: http://127.0.0.1:8000/docs\n'
}

usage() {
  cat <<'EOF'
Usage: ./scripts/local.sh [up|init|doctor|status|logs|restart|down]

  up       Create local config when needed, build, start and wait for readiness.
  init     Create a private .env.local without overwriting existing configuration.
  doctor   Validate Docker, Compose and provider configuration.
  status   Show service health and container status.
  logs     Follow logs from the local stack.
  restart  Restart the existing local stack without deleting data.
  down     Stop containers while preserving database and upload volumes.

Set STYLECAPTURE_ENV_FILE to use another environment file. Set
STYLECAPTURE_COMPOSE_PROJECT_NAME to isolate another installation. Set
STYLECAPTURE_COMPOSE_PROFILE=ai-light only after measuring local resources.
EOF
}

case "${1:-up}" in
  up)
    up
    ;;
  init)
    init_env
    ;;
  doctor)
    doctor
    ;;
  status)
    init_env
    require_docker
    compose ps
    ;;
  logs)
    init_env
    require_docker
    compose logs --tail=200 --follow
    ;;
  restart)
    init_env
    require_docker
    # `docker compose restart` does not re-read environment or Compose changes.
    # Reconcile the existing stack so provider/model edits take effect while
    # preserving images and named volumes.
    compose up -d
    wait_for_url 'Product API' 'http://127.0.0.1:8000/readyz'
    wait_for_url 'StyleCapture H5' 'http://127.0.0.1:5173/healthz'
    ;;
  down)
    init_env
    require_docker
    compose down
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
