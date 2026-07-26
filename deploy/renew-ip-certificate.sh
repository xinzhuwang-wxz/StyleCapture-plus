#!/usr/bin/env bash
set -euo pipefail

repository_root="${STYLECAPTURE_REPOSITORY_ROOT:-/srv/stylecapture/app}"
environment_file="${STYLECAPTURE_ENV_FILE:-/srv/stylecapture/shared/.env}"
certificate_root="${STYLECAPTURE_LETSENCRYPT_DIR:-/srv/stylecapture/shared/letsencrypt}"
public_host="${STYLECAPTURE_PUBLIC_HOST:-119.45.216.38}"

compose=(
  docker compose
  --env-file "${environment_file}"
  -f "${repository_root}/docker-compose.yml"
  -f "${repository_root}/docker-compose.production.yml"
)

# Short-lived IP certificates are renewed with a bounded edge interruption.
# The application services remain running and Caddy is started again even when
# Certbot fails.
"${compose[@]}" stop edge
restart_edge() {
  chown -R root:root "${certificate_root}"
  find "${certificate_root}" -type d -exec chmod 700 {} +
  find "${certificate_root}" -type f -exec chmod 600 {} +
  "${compose[@]}" up -d edge
}
trap restart_edge EXIT

docker run --rm --network host \
  --volume "${certificate_root}:/etc/letsencrypt" \
  certbot/certbot:latest certonly \
  --non-interactive \
  --agree-tos \
  --register-unsafely-without-email \
  --standalone \
  --preferred-profile shortlived \
  --ip-address "${public_host}" \
  --keep-until-expiring
