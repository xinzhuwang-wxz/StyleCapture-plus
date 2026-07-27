#!/usr/bin/env bash
set -euo pipefail

REQUIRED_XCODEGEN="2.46.0"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
APP_DIR="$ROOT/apps/ios/StyleCaptureJourney"

detected="$(xcodegen --version 2>/dev/null | awk '{print $NF}' || true)"
if [[ "$detected" != "$REQUIRED_XCODEGEN" ]]; then
  echo "XcodeGen $REQUIRED_XCODEGEN required, detected ${detected:-missing}."
  echo "Install with: brew install xcodegen && brew upgrade xcodegen"
  exit 1
fi

bash "$ROOT/scripts/bootstrap_ios.sh" --check

if [[ ! -d "$APP_DIR/StyleCaptureJourney.xcodeproj" ]]; then
  echo "Expected generated project is missing: $APP_DIR/StyleCaptureJourney.xcodeproj"
  exit 1
fi

if [[ ! -f "$APP_DIR/StyleCaptureJourney.xcodeproj/xcshareddata/xcschemes/StyleCaptureJourney.xcscheme" ]]; then
  echo "Expected shared scheme is missing."
  exit 1
fi
