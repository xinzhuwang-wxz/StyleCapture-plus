#!/usr/bin/env bash
set -euo pipefail

repository_root="${STYLECAPTURE_REPOSITORY_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
environment_file="${STYLECAPTURE_ENV_FILE:-/srv/stylecapture/shared/.env}"
backup_file="${1:-/srv/stylecapture/backups/latest/stylecapture.dump}"
verification_database="stylecapture_restore_verify"

test -s "${backup_file}"

compose=(
  docker compose
  --env-file "${environment_file}"
  -f "${repository_root}/docker-compose.yml"
  -f "${repository_root}/docker-compose.production.yml"
)

cleanup() {
  "${compose[@]}" exec -T postgres \
    dropdb --username=stylecapture --if-exists --force "${verification_database}" \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
"${compose[@]}" exec -T postgres \
  createdb --username=stylecapture "${verification_database}"
"${compose[@]}" exec -T postgres \
  pg_restore --username=stylecapture --dbname="${verification_database}" --exit-on-error \
  < "${backup_file}"

table_count="$(${compose[@]} exec -T postgres psql \
  --username=stylecapture \
  --dbname="${verification_database}" \
  --tuples-only --no-align \
  --command="select count(*) from information_schema.tables where table_schema = 'public';")"

if [[ ! "${table_count}" =~ ^[1-9][0-9]*$ ]]; then
  echo "restored database does not contain application tables" >&2
  exit 1
fi

echo "restore verified: ${table_count} public tables"
