#!/usr/bin/env python3
"""Validate the XcodeGen iOS dependency graph without requiring Package.swift."""

from __future__ import annotations

import json
import plistlib
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IOS_ROOT = ROOT / "apps/ios/StyleCaptureJourney"
PROJECT_YML = IOS_ROOT / "project.yml"
PACKAGE_RESOLVED = IOS_ROOT / "Config/Package.resolved"
PBXPROJ = IOS_ROOT / "StyleCaptureJourney.xcodeproj/project.pbxproj"
ENTITLEMENTS = IOS_ROOT / "StyleCaptureJourney/Resources/StyleCaptureJourney.entitlements"
THIRD_PARTY_NOTICES = IOS_ROOT / "StyleCaptureJourney/Resources/ThirdPartyNotices.txt"

EXPECTED_PINS = {
    "combine-schedulers": ("1.2.0", "dcccb979a2183b8df3334237e3dc1ae2b4116a86"),
    "grdb.swift": ("7.11.1", "b83108d10f42680d78f23fe4d4d80fc88dab3212"),
    "nuke": ("13.0.6", "63a8fcbd6621340a2410bc3e9575ac97058615f4"),
    "openapikit": ("6.2.0", "57b6318128e3f901c93f4fbf98d1c1464ec168d3"),
    "swift-algorithms": ("1.2.1", "87e50f483c54e6efd60e885f7f5aa946cee68023"),
    "swift-argument-parser": ("1.8.2", "6a52f3251125d74daf04fcbd5e6f08a75d074382"),
    "swift-case-paths": ("1.9.1", "794f4b0a9cf32042592388d014f6a1ea987d323a"),
    "swift-clocks": ("1.1.0", "72d749bf341b78851203066ab421869b783ec42a"),
    "swift-collections": ("1.6.0", "a0cb0954ecb21e4e31b0070e6ed5674e8556685a"),
    "swift-composable-architecture": (
        "1.26.1",
        "ead11e04e5011c437722c1990d22f80d87056978",
    ),
    "swift-concurrency-extras": (
        "1.4.1",
        "5fa253428866f2360c3754e88537f700ed2656b5",
    ),
    "swift-custom-dump": ("1.6.1", "a8cd6c976f335ed361dcecddb0dc39ebda51bc3e"),
    "swift-dependencies": ("1.14.1", "8dc1fbf2f6255a73dec53b4648164884898db4c5"),
    "swift-http-types": ("1.6.0", "db774a277f60063a32d854f2980299caf06da041"),
    "swift-identified-collections": (
        "1.1.1",
        "322d9ffeeba85c9f7c4984b39422ec7cc3c56597",
    ),
    "swift-navigation": ("2.10.3", "fad75807c596fecd724b0fc81cd61c94008faad4"),
    "swift-numerics": ("1.1.1", "0c0290ff6b24942dadb83a929ffaaa1481df04a2"),
    "swift-openapi-generator": ("1.13.0", "af9a2a1f5dcfb00a278d4bb29c6d75080932e99e"),
    "swift-openapi-runtime": ("1.11.0", "f039fa6d6338aab5164f3d1be16281524c9a8f89"),
    "swift-openapi-urlsession": ("1.1.0", "6fac6f7c428d5feea2639b5f5c8b06ddfb79434b"),
    "swift-perception": ("2.0.11", "de219a1cf34e958134e75a9ebb134cf09bf52fc6"),
    "swift-sharing": ("2.9.1", "8244fe63bf43e58188ab13851ad693eecf6a9e90"),
    "swift-syntax": ("603.0.2", "79e4b74a295b6eb74a8b585e3a39d29e70c1dbd1"),
    "xctest-dynamic-overlay": (
        "1.11.0",
        "8f6abcf4c8950e2679d5b2fee4ca284fd7c34886",
    ),
    "yams": ("6.2.2", "a27b21e0c81c5bf42049b897a62aaf387e80f279"),
}

EXPECTED_DIRECT_PINS = {
    "grdb.swift",
    "nuke",
    "swift-case-paths",
    "swift-clocks",
    "swift-composable-architecture",
    "swift-dependencies",
    "swift-http-types",
    "swift-openapi-generator",
    "swift-openapi-runtime",
    "swift-openapi-urlsession",
    "swift-sharing",
}

PROJECT_PRODUCT_REFERENCES = (
    "ComposableArchitecture",
    "CasePaths",
    "Dependencies",
    "Clocks",
    "GRDB",
    "Nuke",
    "HTTPTypes",
    "OpenAPIRuntime",
    "OpenAPIURLSession",
    "OpenAPIGenerator",
    "Sharing",
)


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def check_project_yml() -> int:
    text = PROJECT_YML.read_text(encoding="utf-8")
    forbidden_tokens = ("branch:", "from:", "upToNextMajor", "upToNextMinor", "revision:")
    for token in forbidden_tokens:
        if token in text:
            return fail(f"forbidden non-exact SwiftPM requirement in project.yml: {token}")

    for identity in EXPECTED_DIRECT_PINS:
        version, _ = EXPECTED_PINS[identity]
        package_name = "GRDB" if identity == "grdb.swift" else identity
        package_name = "Nuke" if identity == "nuke" else package_name
        if package_name not in text or f"exactVersion: {version}" not in text:
            return fail(f"project.yml missing exact package {package_name} {version}")
    for release_token in (
        "CODE_SIGN_ENTITLEMENTS: StyleCaptureJourney/Resources/StyleCaptureJourney.entitlements",
        "SystemCapabilities:",
        "com.apple.SignInWithApple:",
        "enabled: 1",
        "patch_ios_system_capabilities.py",
    ):
        if release_token not in text:
            return fail(f"project.yml missing release token: {release_token}")
    return 0


def check_package_resolved() -> int:
    resolved = json.loads(PACKAGE_RESOLVED.read_text(encoding="utf-8"))
    pins = {pin["identity"]: pin["state"] for pin in resolved["pins"]}
    if set(pins) != set(EXPECTED_PINS):
        missing = sorted(set(EXPECTED_PINS) - set(pins))
        unexpected = sorted(set(pins) - set(EXPECTED_PINS))
        return fail(
            "Package.resolved identity drift: "
            f"missing={missing or 'none'}, unexpected={unexpected or 'none'}"
        )
    for identity, (version, revision) in EXPECTED_PINS.items():
        state = pins.get(identity)
        if state is None:
            return fail(f"Package.resolved missing {identity}")
        if state.get("version") != version or state.get("revision") != revision:
            return fail(
                f"Package.resolved drift for {identity}: expected {version}@{revision}, got {state}"
            )
    return 0


def check_release_resources() -> int:
    if not ENTITLEMENTS.exists():
        return fail(f"missing Sign in with Apple entitlements: {ENTITLEMENTS.relative_to(ROOT)}")
    with ENTITLEMENTS.open("rb") as entitlements_file:
        entitlements = plistlib.load(entitlements_file)
    if entitlements.get("com.apple.developer.applesignin") != ["Default"]:
        return fail("Sign in with Apple entitlement must contain the Default environment")

    if not THIRD_PARTY_NOTICES.exists():
        return fail(f"missing distributable notices: {THIRD_PARTY_NOTICES.relative_to(ROOT)}")
    notices = THIRD_PARTY_NOTICES.read_text(encoding="utf-8")
    for identity, (version, revision) in EXPECTED_PINS.items():
        if identity not in notices or version not in notices or revision not in notices:
            return fail(f"distributable notices missing exact pin metadata for {identity}")
    if "MIT License" not in notices or "Apache License\nVersion 2.0, January 2004" not in notices:
        return fail("distributable notices missing MIT or Apache-2.0 license terms")
    return 0


def check_generated_project() -> int:
    if not PBXPROJ.exists():
        return fail(f"generated Xcode project missing: {PBXPROJ.relative_to(ROOT)}")

    text = PBXPROJ.read_text(encoding="utf-8")
    for product in PROJECT_PRODUCT_REFERENCES:
        if product not in text:
            return fail(f"generated Xcode project missing product reference: {product}")
    for release_token in (
        "StyleCaptureJourney.entitlements",
        "ThirdPartyNotices.txt",
        "CODE_SIGN_ENTITLEMENTS",
        "SystemCapabilities = {",
        "com.apple.SignInWithApple = {",
    ):
        if release_token not in text:
            return fail(f"generated Xcode project missing release token: {release_token}")
    if 'SystemCapabilities = "' in text:
        return fail("generated Xcode project contains a stringified SystemCapabilities value")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = set(sys.argv[1:] if argv is None else argv)
    unknown_arguments = arguments - {"--require-generated-project"}
    if unknown_arguments:
        return fail(f"unknown arguments: {sorted(unknown_arguments)}")

    checks = [check_project_yml, check_package_resolved, check_release_resources]
    if "--require-generated-project" in arguments:
        checks.append(check_generated_project)

    for check in checks:
        result = check()
        if result != 0:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
