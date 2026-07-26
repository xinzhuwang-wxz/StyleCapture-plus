#!/usr/bin/env bash
set -euo pipefail

repository_root="${STYLECAPTURE_REPOSITORY_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
environment_file="${STYLECAPTURE_ENV_FILE:-/srv/stylecapture/shared/.env}"
backup_root="${STYLECAPTURE_BACKUP_ROOT:-/srv/stylecapture/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_directory="${backup_root}/${timestamp}"
backup_uploads="${STYLECAPTURE_BACKUP_UPLOADS:-false}"

mkdir -p "${backup_directory}"
chmod 700 "${backup_root}" "${backup_directory}"
complete=false
cleanup() {
  if [[ "${complete}" != "true" ]]; then
    rm -rf -- "${backup_directory}"
  fi
}
trap cleanup EXIT

compose=(
  docker compose
  --env-file "${environment_file}"
  -f "${repository_root}/docker-compose.yml"
  -f "${repository_root}/docker-compose.production.yml"
)

"${compose[@]}" exec -T postgres \
  pg_dump --username=stylecapture --dbname=stylecapture --format=custom \
  > "${backup_directory}/stylecapture.dump"

api_container="$(${compose[@]} ps --quiet api)"
uploads_volume="$(docker inspect "${api_container}" --format '{{range .Mounts}}{{if eq .Destination "/data/uploads"}}{{.Name}}{{end}}{{end}}')"
if [[ -n "${uploads_volume}" ]]; then
  docker run --rm --volume "${uploads_volume}:/source:ro" alpine:3.21 \
    sh -c 'find /source -type f -exec stat -c "%n\t%s" {} + | sort' \
    > "${backup_directory}/upload-manifest.tsv"
fi

if [[ "${backup_uploads}" == "true" ]]; then
  upload_bytes="$(docker run --rm --volume "${uploads_volume}:/source:ro" alpine:3.21 du -sb /source | cut -f1)"
  available_bytes="$(df --output=avail -B1 "${backup_root}" | tail -1 | tr -d ' ')"
  minimum_free_bytes=$((20 * 1024 * 1024 * 1024))
  required_bytes=$((upload_bytes * 2 + minimum_free_bytes))
  if (( available_bytes < required_bytes )); then
    echo "refusing media backup: ${available_bytes} bytes free, ${required_bytes} required" >&2
    exit 1
  fi
  docker run --rm \
    --volume "${uploads_volume}:/source:ro" \
    --volume "${backup_directory}:/backup" \
    alpine:3.21 \
    tar -C /source -czf /backup/uploads.tar.gz .
fi

sha256sum "${backup_directory}"/* > "${backup_directory}/SHA256SUMS"
chmod 600 "${backup_directory}"/*

ln -sfn "${timestamp}" "${backup_root}/latest"
complete=true
echo "${backup_directory}"
