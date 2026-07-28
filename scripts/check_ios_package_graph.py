#!/usr/bin/env python3
"""Validate the XcodeGen iOS dependency graph without requiring Package.swift."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IOS_ROOT = ROOT / "apps/ios/StyleCaptureJourney"
PROJECT_YML = IOS_ROOT / "project.yml"
PACKAGE_RESOLVED = IOS_ROOT / "Config/Package.resolved"
PBXPROJ = IOS_ROOT / "StyleCaptureJourney.xcodeproj/project.pbxproj"

EXPECTED_PINS = {
    "grdb.swift": ("7.11.1", "b83108d10f42680d78f23fe4d4d80fc88dab3212"),
    "nuke": ("13.0.6", "63a8fcbd6621340a2410bc3e9575ac97058615f4"),
    "swift-case-paths": ("1.9.1", "794f4b0a9cf32042592388d014f6a1ea987d323a"),
    "swift-clocks": ("1.1.0", "72d749bf341b78851203066ab421869b783ec42a"),
    "swift-composable-architecture": (
        "1.26.1",
        "ead11e04e5011c437722c1990d22f80d87056978",
    ),
    "swift-dependencies": ("1.14.1", "8dc1fbf2f6255a73dec53b4648164884898db4c5"),
    "swift-http-types": ("1.6.0", "db774a277f60063a32d854f2980299caf06da041"),
    "swift-openapi-generator": ("1.13.0", "af9a2a1f5dcfb00a278d4bb29c6d75080932e99e"),
    "swift-openapi-runtime": ("1.11.0", "f039fa6d6338aab5164f3d1be16281524c9a8f89"),
    "swift-openapi-urlsession": ("1.1.0", "6fac6f7c428d5feea2639b5f5c8b06ddfb79434b"),
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

    for identity, (version, _) in EXPECTED_PINS.items():
        package_name = "GRDB" if identity == "grdb.swift" else identity
        package_name = "Nuke" if identity == "nuke" else package_name
        if package_name not in text or f"exactVersion: {version}" not in text:
            return fail(f"project.yml missing exact package {package_name} {version}")
    return 0


def check_package_resolved() -> int:
    resolved = json.loads(PACKAGE_RESOLVED.read_text(encoding="utf-8"))
    pins = {pin["identity"]: pin["state"] for pin in resolved["pins"]}
    for identity, (version, revision) in EXPECTED_PINS.items():
        state = pins.get(identity)
        if state is None:
            return fail(f"Package.resolved missing {identity}")
        if state.get("version") != version or state.get("revision") != revision:
            return fail(
                f"Package.resolved drift for {identity}: expected {version}@{revision}, got {state}"
            )
    return 0


def check_generated_project() -> int:
    if not PBXPROJ.exists():
        return fail(f"generated Xcode project missing: {PBXPROJ.relative_to(ROOT)}")

    text = PBXPROJ.read_text(encoding="utf-8")
    for product in PROJECT_PRODUCT_REFERENCES:
        if product not in text:
            return fail(f"generated Xcode project missing product reference: {product}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = set(sys.argv[1:] if argv is None else argv)
    unknown_arguments = arguments - {"--require-generated-project"}
    if unknown_arguments:
        return fail(f"unknown arguments: {sorted(unknown_arguments)}")

    checks = [check_project_yml, check_package_resolved]
    if "--require-generated-project" in arguments:
        checks.append(check_generated_project)

    for check in checks:
        result = check()
        if result != 0:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
