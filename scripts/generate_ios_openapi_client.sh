#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/apps/ios/StyleCaptureJourney"
SCHEMA="$APP_DIR/OpenAPI/openapi.json"
CONFIG="$APP_DIR/OpenAPI/openapi-generator-config.yaml"

if [[ ! -f "$SCHEMA" ]]; then
  echo "Missing iOS OpenAPI schema: $SCHEMA"
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "Missing iOS OpenAPI generator config: $CONFIG"
  exit 1
fi

python3 - "$SCHEMA" <<'PY'
from __future__ import annotations
import json
import sys
from pathlib import Path

schema = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not str(schema.get("openapi", "")).startswith("3."):
    print("OpenAPI schema must be 3.x")
    raise SystemExit(1)
if "paths" not in schema:
    print("OpenAPI schema is missing paths")
    raise SystemExit(1)

def contains_nullable_any_of(value: object) -> bool:
    if isinstance(value, list):
        return any(contains_nullable_any_of(item) for item in value)
    if not isinstance(value, dict):
        return False
    any_of = value.get("anyOf")
    if isinstance(any_of, list) and any(
        isinstance(member, dict) and member.get("type") == "null"
        for member in any_of
    ):
        return True
    return any(contains_nullable_any_of(item) for item in value.values())

if contains_nullable_any_of(schema):
    print("iOS OpenAPI schema still contains generator-unsupported nullable anyOf")
    raise SystemExit(1)
PY

if find "$APP_DIR" -path '*/DerivedSources/*' -type f | grep -q .; then
  echo "Generated OpenAPI sources must not be committed under DerivedSources."
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  echo "iOS OpenAPI build-plugin inputs: ok; generated client compile proof requires xcodebuild."
else
  echo "OpenAPI generation is performed by the Xcode build tool plugin."
fi
