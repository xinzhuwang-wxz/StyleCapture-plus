#!/usr/bin/env python3
"""Validate iOS privacy manifest declarations required by source usage."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
NAVIGATION_SOURCE = (
    ROOT
    / "apps/ios/StyleCaptureJourney/StyleCaptureJourney/Core/Navigation/NavigationSnapshotClient.swift"
)
PRIVACY_MANIFEST = (
    ROOT / "apps/ios/StyleCaptureJourney/StyleCaptureJourney/Resources/PrivacyInfo.xcprivacy"
)

USER_DEFAULTS_CATEGORY = "NSPrivacyAccessedAPICategoryUserDefaults"
USER_DEFAULTS_REASON = "CA92.1"


def source_uses_user_defaults() -> bool:
    return "UserDefaults" in NAVIGATION_SOURCE.read_text(encoding="utf-8")


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def load_manifest() -> dict[str, object]:
    with PRIVACY_MANIFEST.open("rb") as manifest_file:
        return cast("dict[str, object]", plistlib.load(manifest_file))


def declared_reasons(manifest: dict[str, object], category: str) -> list[str]:
    raw_api_types = manifest.get("NSPrivacyAccessedAPITypes", [])
    if not isinstance(raw_api_types, list):
        return []

    reasons: list[str] = []
    for raw_api_type in raw_api_types:
        if not isinstance(raw_api_type, dict):
            continue
        if raw_api_type.get("NSPrivacyAccessedAPIType") != category:
            continue
        reasons.extend(string_list(raw_api_type.get("NSPrivacyAccessedAPITypeReasons")))
    return reasons


def main() -> int:
    if not PRIVACY_MANIFEST.exists():
        print(f"missing iOS privacy manifest: {PRIVACY_MANIFEST}", file=sys.stderr)
        return 1

    if not source_uses_user_defaults():
        return 0

    reasons = declared_reasons(load_manifest(), USER_DEFAULTS_CATEGORY)
    if USER_DEFAULTS_REASON in reasons:
        return 0

    print(
        "iOS privacy manifest missing "
        f"{USER_DEFAULTS_CATEGORY} reason {USER_DEFAULTS_REASON} while "
        f"{NAVIGATION_SOURCE.relative_to(ROOT)} uses UserDefaults.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
