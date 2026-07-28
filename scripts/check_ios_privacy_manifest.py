#!/usr/bin/env python3
"""Validate iOS privacy manifest declarations required by source usage."""

from __future__ import annotations

import plistlib
import sys
from collections.abc import Sequence
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
DEPENDENCY_PRIVACY_EVIDENCE = (
    ROOT / "docs/evidence/journey/task-2/dependency-license-privacy-audit.md"
)

USER_DEFAULTS_CATEGORY = "NSPrivacyAccessedAPICategoryUserDefaults"
USER_DEFAULTS_REASON = "CA92.1"

AUDITED_PACKAGE_MANIFESTS = {
    "grdb.swift": ("GRDB.swift", "GRDB/PrivacyInfo.xcprivacy", {}),
    "swift-composable-architecture": (
        "swift-composable-architecture",
        "Sources/ComposableArchitecture/Resources/PrivacyInfo.xcprivacy",
        {USER_DEFAULTS_CATEGORY: {"C56D.1"}},
    ),
    "swift-sharing": (
        "swift-sharing",
        "Sources/Sharing/PrivacyInfo.xcprivacy",
        {
            "NSPrivacyAccessedAPICategoryFileTimestamp": {"C617.1"},
            USER_DEFAULTS_CATEGORY: {"C56D.1"},
        },
    ),
}


def source_uses_user_defaults() -> bool:
    return "UserDefaults" in NAVIGATION_SOURCE.read_text(encoding="utf-8")


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def load_manifest(path: Path = PRIVACY_MANIFEST) -> dict[str, object]:
    with path.open("rb") as manifest_file:
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


def declared_reason_map(manifest: dict[str, object]) -> dict[str, set[str]]:
    raw_api_types = manifest.get("NSPrivacyAccessedAPITypes", [])
    if not isinstance(raw_api_types, list):
        return {}

    reason_map: dict[str, set[str]] = {}
    for raw_api_type in raw_api_types:
        if not isinstance(raw_api_type, dict):
            continue
        category = raw_api_type.get("NSPrivacyAccessedAPIType")
        if isinstance(category, str):
            reason_map[category] = set(
                string_list(raw_api_type.get("NSPrivacyAccessedAPITypeReasons"))
            )
    return reason_map


def check_dependency_evidence() -> int:
    evidence = DEPENDENCY_PRIVACY_EVIDENCE.read_text(encoding="utf-8")
    for package, (_, manifest_path, categories) in AUDITED_PACKAGE_MANIFESTS.items():
        if package not in evidence or manifest_path not in evidence:
            print(
                f"dependency privacy evidence missing {package} manifest {manifest_path}",
                file=sys.stderr,
            )
            return 1
        for category, reasons in categories.items():
            for reason in reasons:
                if category not in evidence or reason not in evidence:
                    print(
                        f"dependency privacy evidence missing {package} {category} reason {reason}",
                        file=sys.stderr,
                    )
                    return 1
    return 0


def check_cached_package_manifests(source_packages: Path) -> int:
    checkouts = source_packages / "checkouts"
    for package, (
        checkout_name,
        relative_manifest,
        expected_categories,
    ) in AUDITED_PACKAGE_MANIFESTS.items():
        manifest_path = checkouts / checkout_name / relative_manifest
        if not manifest_path.exists():
            print(f"missing cached package privacy manifest: {manifest_path}", file=sys.stderr)
            return 1
        manifest = load_manifest(manifest_path)
        actual_categories = declared_reason_map(manifest)
        if actual_categories != expected_categories:
            print(
                f"cached package privacy manifest required-reason drift for {package}: "
                f"expected {expected_categories}, got {actual_categories}",
                file=sys.stderr,
            )
            return 1
        if manifest.get("NSPrivacyTracking") is not False:
            print(f"cached package privacy manifest enables tracking: {package}", file=sys.stderr)
            return 1
        if manifest.get("NSPrivacyCollectedDataTypes") != []:
            print(
                f"cached package privacy manifest declares collected data: {package}",
                file=sys.stderr,
            )
            return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    source_packages: Path | None = None
    if arguments:
        if len(arguments) != 2 or arguments[0] != "--source-packages":
            print(
                "usage: check_ios_privacy_manifest.py [--source-packages PATH]",
                file=sys.stderr,
            )
            return 1
        source_packages = Path(arguments[1])

    if not PRIVACY_MANIFEST.exists():
        print(f"missing iOS privacy manifest: {PRIVACY_MANIFEST}", file=sys.stderr)
        return 1

    if source_uses_user_defaults():
        reasons = declared_reasons(load_manifest(), USER_DEFAULTS_CATEGORY)
        if USER_DEFAULTS_REASON not in reasons:
            print(
                "iOS privacy manifest missing "
                f"{USER_DEFAULTS_CATEGORY} reason {USER_DEFAULTS_REASON} while "
                f"{NAVIGATION_SOURCE.relative_to(ROOT)} uses UserDefaults.",
                file=sys.stderr,
            )
            return 1

    if check_dependency_evidence() != 0:
        return 1
    if source_packages is not None:
        return check_cached_package_manifests(source_packages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
