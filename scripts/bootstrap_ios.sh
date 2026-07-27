#!/usr/bin/env bash
set -euo pipefail

REQUIRED_XCODE_MAJOR="26"
REQUIRED_SWIFT_MIN_MAJOR="6"
REQUIRED_SWIFT_MIN_MINOR="2"
REQUIRED_XCODEGEN="2.46.0"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/apps/ios/StyleCaptureJourney"
PROJECT="$APP_DIR/StyleCaptureJourney.xcodeproj"
RESOLVED_SOURCE="$APP_DIR/Config/Package.resolved"
RESOLVED_DEST="$PROJECT/project.xcworkspace/xcshareddata/swiftpm/Package.resolved"

fail() {
  echo "$1"
  echo "Required: Xcode ${REQUIRED_XCODE_MAJOR}.x, Swift ${REQUIRED_SWIFT_MIN_MAJOR}.${REQUIRED_SWIFT_MIN_MINOR}+, XcodeGen ${REQUIRED_XCODEGEN}."
  echo "Detected: Xcode ${DETECTED_XCODE:-missing}, Swift ${DETECTED_SWIFT:-missing}, XcodeGen ${DETECTED_XCODEGEN:-missing}."
  echo "Install/upgrade XcodeGen with: brew install xcodegen && brew upgrade xcodegen"
  exit 1
}

version_ge() {
  local major="$1"
  local minor="$2"
  [[ "$major" -gt "$REQUIRED_SWIFT_MIN_MAJOR" ]] || {
    [[ "$major" -eq "$REQUIRED_SWIFT_MIN_MAJOR" && "$minor" -ge "$REQUIRED_SWIFT_MIN_MINOR" ]]
  }
}

check_versions() {
  DETECTED_XCODE="$(xcodebuild -version | awk '/^Xcode / {print $2}')"
  [[ "$DETECTED_XCODE" == ${REQUIRED_XCODE_MAJOR}.* ]] || fail "Unsupported Xcode version."

  DETECTED_SWIFT="$(swift --version 2>&1 | sed -n 's/.*Apple Swift version \([0-9][0-9.]*\).*/\1/p')"
  swift_major="${DETECTED_SWIFT%%.*}"
  swift_rest="${DETECTED_SWIFT#*.}"
  swift_minor="${swift_rest%%.*}"
  version_ge "$swift_major" "$swift_minor" || fail "Unsupported Swift version."

  DETECTED_XCODEGEN="$(xcodegen --version 2>/dev/null | awk '{print $NF}' || true)"
  [[ "$DETECTED_XCODEGEN" == "$REQUIRED_XCODEGEN" ]] || fail "Unsupported XcodeGen version."
}

check_exact_swiftpm_requirements() {
  python3 - "$APP_DIR/project.yml" <<'PY'
from __future__ import annotations
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
bad = []
for forbidden in ("branch:", "from:", "upToNextMajorVersion:", "upToNextMinorVersion:"):
    if forbidden in text:
        bad.append(forbidden.rstrip(":"))
package_block = re.search(r"^packages:\n(?P<body>.*?)(?=^\S|\Z)", text, re.M | re.S)
if not package_block:
    bad.append("missing packages block")
else:
    entries = re.findall(r"^  [A-Za-z0-9_.-]+:\n(?P<body>(?:    .+\n)+)", package_block.group("body"), re.M)
    for body in entries:
        if "exactVersion:" not in body and "revision:" not in body:
            bad.append("package without exactVersion/revision")
if bad:
    print("Non-exact SwiftPM requirements are forbidden: " + ", ".join(sorted(set(bad))))
    raise SystemExit(1)
PY
}

generate_project() {
  xcodegen generate --spec "$APP_DIR/project.yml"
  if [[ -f "$RESOLVED_SOURCE" ]]; then
    mkdir -p "$(dirname "$RESOLVED_DEST")"
    cp "$RESOLVED_SOURCE" "$RESOLVED_DEST"
    echo "Seeded SwiftPM lock into generated workspace; post-resolution integrity is checked after xcodebuild."
  fi
}

check_package_resolved_integrity() {
  if [[ ! -f "$RESOLVED_SOURCE" ]]; then
    fail "Missing versioned SwiftPM lock: $RESOLVED_SOURCE"
  fi
  if [[ ! -f "$RESOLVED_DEST" ]]; then
    fail "Missing generated workspace SwiftPM lock: $RESOLVED_DEST"
  fi
  cmp "$RESOLVED_SOURCE" "$RESOLVED_DEST"
  echo "SwiftPM post-resolution lock integrity: ok"
}

if [[ "${1:-}" == "--check" ]]; then
  check_versions
  check_exact_swiftpm_requirements
  generate_project
  echo "iOS bootstrap check: ok"
elif [[ "${1:-}" == "--check-package-resolved" ]]; then
  check_package_resolved_integrity
else
  check_versions
  generate_project
fi
